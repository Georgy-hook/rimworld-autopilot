"""Observed bedside recovery prerequisites, independent of elective colony work."""
import rimworld_laya as bridge
from colony_retry import failure_record, recent

CARE_JOBS = {"tendpatient", "rescue", "feedpatient"}


def helpers(snapshot, patient_id, doctor=False):
    combat = {str(p.get("id")): p for p in snapshot.get("combat", {}).get("colonists") or []}
    rows = []
    for pawn in snapshot.get("colonists") or []:
        live = combat.get(str(pawn.get("id"))) or {}
        if (str(pawn.get("id")) == str(patient_id) or pawn.get("downed") or pawn.get("dead")
                or pawn.get("in_mental_state") or live.get("is_in_mental_state")
                or pawn.get("is_drafted") or live.get("is_drafted")
                or float((pawn.get("capacities") or {}).get("moving", 1)) <= 0
                or float((pawn.get("capacities") or {}).get("manipulation", 1)) <= 0
                or str(pawn.get("current_job") or live.get("current_job") or "").lower() in CARE_JOBS):
            continue
        work = (pawn.get("work_priorities") or {}).get("Doctor")
        if doctor and (not isinstance(work, dict) or work.get("disabled")):
            continue
        rows.append(pawn)
    return rows


def care_order_fields(row):
    """Only native offered exact-current-care bindings authorize a scoped replacement."""
    job, target = row.get("expected_current_job"), row.get("expected_care_patient_id")
    if job not in {"TendPatient", "Rescue"} or not isinstance(target, int) or isinstance(target, bool):
        return {}
    return {"expected_current_job": job, "expected_care_patient_id": target}


def offered_care_yield(snapshot, row):
    binding = care_order_fields(row)
    if not binding or not row.get("care_yield_reason") or row.get("kind") not in {"feed", "rescue"}:
        return None
    if row.get("food_feasible") is not True:
        return None
    detail = next((p for p in snapshot.get("colonists") or [] if str(p.get("id")) == str(row.get("worker_id"))), None)
    live = next((p for p in snapshot.get("combat", {}).get("colonists") or [] if str(p.get("id")) == str(row.get("worker_id"))), {})
    worker = {**(detail or {}), **live}
    # GET facts must still agree with the offered binding. Native POST repeats all clinical/route gates.
    work = (detail or {}).get("work_priorities", {}).get("Doctor")
    if isinstance(work, dict) and work.get("disabled"):
        return None
    if detail is None or worker.get("current_job") != binding["expected_current_job"]:
        return None
    if str(worker.get("care_target_id") or worker.get("current_job_target_id")) != str(binding["expected_care_patient_id"]):
        return None
    if any(worker.get(k) for k in ("dead", "is_dead", "downed", "is_downed", "in_mental_state", "is_in_mental_state", "is_drafted", "carried_thing_id")):
        return None
    if str(worker.get("id")) == str(row.get("target_id")):
        return None
    old = next((p for p in snapshot.get("colonists") or []
                if str(p.get("id")) == str(binding["expected_care_patient_id"])), None)
    native_patients = snapshot.get("development", {}).get("resilience", {}).get("patients") or []
    old_native = next((p for p in native_patients if str(p.get("pawn_id")) == str(binding["expected_care_patient_id"])), {})
    if old is None:
        return None
    conditions = old.get("health_conditions", old_native.get("conditions"))
    if not isinstance(conditions, list) or any(not isinstance(h, dict) for h in conditions):
        return None
    if any(h.get("def_name") not in {"BloodLoss", "Malnutrition"} and (
            (h.get("immunity") is not None and float(h["immunity"]) < 1)
            or h.get("life_threatening") or h.get("tendable_now") and (
                float(h.get("lethal_severity") or 0) > 0 or "infection" in str(h.get("def_name") or "").lower()))
           for h in conditions):
        return None
    rate = old.get("bleeding_rate", old_native.get("bleeding_total"))
    if not isinstance(rate, (int, float)) or isinstance(rate, bool):
        return None
    if binding["expected_current_job"] == "TendPatient" and rate > 0:
        return None
    if rate > 0 and not (rate < .1 and old_native.get("bleeding_evidence_complete") is True):
        deadline = triage(old)[1]
        if deadline is None:
            deadline = old_native.get("bleedout_ticks")
        next_native = next((p for p in native_patients if str(p.get("pawn_id")) == str(row.get("target_id"))), {})
        starvation = row.get("starvation_ticks", next_native.get("starvation_ticks"))
        if not isinstance(deadline, (int, float)) or not isinstance(starvation, (int, float)) or deadline <= starvation * 2 + 600:
            return None
    return detail


def active_patients(snapshot, context=None):
    context = context if context is not None else snapshot.get("development", {}).get("resilience", {})
    targets = {str(row.get("target_id")) for row in context.get("active_orders") or []
               if row.get("kind") in {"rescue", "feed", "tend"}}
    for row in snapshot.get("combat", {}).get("colonists") or []:
        job = str(row.get("current_job") or "").lower()
        target = row.get("care_target_id") or (row.get("current_job_target_id_b") if job == "feedpatient" else row.get("current_job_target_id"))
        if job in CARE_JOBS and target:
            targets.add(str(target))
    return targets


def build_options(client, snapshot, map_state):
    dev = snapshot["development"]
    context = dev.get("resilience") or {}
    active = active_patients(snapshot, context)
    patients = {str(p.get("id")): p for p in [*snapshot.get("colonists", []), *snapshot.get("animals", [])]}
    actions = {a: {} for a in ("prepare_patient_bed", "rescue_downed_colonist", "tend_colonist", "feed_hungry_colonist")}
    mapping = {"rescue": "rescue_downed_colonist", "tend": "tend_colonist", "feed": "feed_hungry_colonist",
               "bed_prerequisite": "prepare_patient_bed"}
    pending = map_state.get("patient_spot_pending")
    if not isinstance(pending, dict):
        pending = {}
    map_state["patient_spot_pending"] = pending
    for pid in list(pending):
        record = pending[pid]
        if (pid not in patients or not isinstance(record, dict) or not isinstance(record.get("position"), dict)
                or not all(isinstance(record["position"].get(k), (int, float)) for k in ("x", "z"))
                or record.get("def_name") not in {"SleepingSpot", "AnimalSleepingSpot"}):
            pending.pop(pid, None)
            continue
        present = any(b.get("def") == record["def_name"] and
                      (b.get("position") or {}).get("x") == record["position"]["x"] and
                      (b.get("position") or {}).get("z") == record["position"]["z"]
                      for b in dev.get("buildings") or [])
        if present or not recent(record, int(snapshot["game"].get("tick") or 0), 180):
            pending.pop(pid, None)
    dev["patient_spot_waiting"] = [pid for pid in pending if any(str(row.get("target_id")) == pid
        and row.get("food_feasible") is True for row in context.get("options") or [])]
    for row in context.get("options") or []:
        action = mapping.get(row.get("kind"))
        pid = str(row.get("target_id"))
        patient = patients.get(pid)
        yield_worker = offered_care_yield(snapshot, row)
        if (row.get("expected_current_job") is not None or row.get("expected_care_patient_id") is not None) and yield_worker is None:
            continue
        if action is None or patient is None or (pid in active and not (yield_worker and row.get("kind") == "feed"
                and str(row.get("expected_care_patient_id")) == pid)):
            continue
        eligible = {str(p["id"]): p for p in helpers(snapshot, pid, doctor=action in {"tend_colonist", "feed_hungry_colonist", "rescue_downed_colonist"})}
        worker = eligible.get(str(row.get("worker_id"))) or yield_worker
        if worker is None:
            continue
        if action != "prepare_patient_bed" and pid not in {str(p.get("id")) for p in snapshot.get("colonists", [])}:
            continue  # Existing animal actions use their native animal-specific workgivers.
        if action == "prepare_patient_bed":
            if client is None or pid in pending:
                continue
            if pid not in actions[action]:
                try:
                    checked = client.post("/api/v1/builder/site-options", body={"map_id": snapshot["map"]["id"],
                        "def_name": row["giver"], "near": patient["position"], "radius": 3, "limit": 12})
                except bridge.RimApiError as error:
                    dev.setdefault("patient_recovery_blockers", []).append(str(error))
                    continue
                sites = [site for site in checked.get("sites") or []
                         if site.get("position") and not bridge.combat_planner.errand_exposed(snapshot, site["position"])]
                if not sites:
                    dev.setdefault("patient_recovery_blockers", []).append(f"{patient.get('name')}: no safe verified temporary bed site")
                    continue
                site = min(sites, key=lambda s: (s["position"]["x"]-patient["position"]["x"])**2
                           + (s["position"]["z"]-patient["position"]["z"])**2)
                actions[action][pid] = {"patient": patient, "helpers": {}, "site": site,
                                        "def_name": row["giver"]}
        native_patient = next((p for p in context.get("patients") or [] if str(p.get("pawn_id")) == pid), {})
        enriched = {**patient, **{k: v for k, v in native_patient.items() if k in {
            "starvation_ticks", "malnutrition_severity", "lethal_margin", "bleedout_ticks", "bleeding_evidence_complete"}}}
        plan = actions[action].setdefault(pid, {"patient": enriched, "helpers": {}})
        plan["helpers"][str(worker["id"])] = row
    dev["medical_action_options"] = actions
    return actions


def triage(patient):
    conditions = patient.get("health_conditions") or []
    blood = next((float(h.get("severity") or 0) for h in conditions if h.get("def_name") == "BloodLoss"), None)
    rate = float(patient.get("bleeding_rate") or 0)
    ticks = max(0, (1-blood)*60000/rate) if blood is not None and rate > 0 else None
    return blood, ticks


def clinical_deadline(patient, native_option=None):
    """Minimum known death estimate; missing evidence stays unknown, not zero."""
    import math
    facts = {**patient, **(native_option or {})}
    bleeding = patient.get("bleeding_rate", patient.get("bleeding_total"))
    native_healing = facts.get("bleeding_evidence_complete") is True and isinstance(bleeding, (int, float)) and bleeding < .1
    values = [None if native_healing else triage(patient)[1], facts.get("bleedout_ticks"), facts.get("starvation_ticks")]
    known = [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)
             and math.isfinite(v) and v >= 0]
    return min(known) if known else None


def stable_tend_patient(patient):
    """Residual blood loss is not ongoing bleeding; preserve active disease care."""
    return float(patient.get("bleeding_rate") or 0) <= 0 and not any(
        h.get("def_name") not in {"BloodLoss", "Hypothermia", "Heatstroke", "Frostbite"}
        and h.get("tendable_now") and (h.get("life_threatening")
            or h.get("immunity") is not None or float(h.get("lethal_severity") or 0) > 0
            or "infection" in str(h.get("def_name") or "").lower())
        for h in patient.get("health_conditions") or [])


def patient_summary(patient):
    blood, ticks = triage(patient)
    native_healing = patient.get('bleeding_evidence_complete') is True and isinstance(patient.get('bleeding_rate'), (int, float)) and patient['bleeding_rate'] < .1
    if native_healing:
        ticks = None
    critical = [f"{h.get('def_name')} {float(h.get('severity') or 0):.3f}" for h in patient.get("health_conditions") or []
                if h.get("def_name") in {"BloodLoss", "Malnutrition"} or h.get("life_threatening")
                or float(h.get("lethal_severity") or 0) > 0]
    return (f"{patient.get('name')}; " + ('Native BloodLoss healing; no finite bleedout; ' if native_healing else f"bleedout ~{round(ticks)} ticks; " if ticks is not None else "bleedout unknown; ")
            + ", ".join(critical[:4]) + (f"; starvation ~{round(patient['starvation_ticks'])} ticks" if isinstance(patient.get("starvation_ticks"), (int, float)) else "; starvation deadline unknown")
            + (f"; lethal margin {patient['lethal_margin']:.3f}" if isinstance(patient.get("lethal_margin"), (int, float)) else "") + f"; bleeding {patient.get('bleeding_rate')}; hunger {patient.get('hunger')}; rate/day estimate")


def patient_comparison(plans):
    """State relative deadlines explicitly; an unknown loss is never zero loss."""
    estimates = {pid: clinical_deadline(plan["patient"]) for pid, plan in plans.items()}
    known = [ticks for ticks in estimates.values() if ticks is not None]
    earliest = min(known) if known else None
    criteria = {}
    for pid in sorted(plans, key=str):
        ticks = estimates[pid]
        others = [value for other, value in estimates.items() if other != pid and value is not None]
        if ticks is None:
            consequence = "Death deadline unknown; cannot assume safe to delay. "
        elif others and ticks < min(others):
            consequence = "Shortest estimated survival; delaying this patient risks death first. "
        elif earliest is not None and ticks > earliest:
            consequence = "More estimated time than the earliest-death patient; treating this one first delays someone closer to death. "
        else:
            consequence = "Earliest estimated death deadline among known estimates; time-sensitive treatment. "
        criteria[pid] = consequence + patient_summary(plans[pid]["patient"])
    context = ("Choose the next patient to prevent imminent death. Existing BloodLoss and remaining survival time matter more than bleeding rate alone. "
               "Ordering care for one patient delays the others. Estimates assume unchanged bleeding/starvation and normal native need intervals; unknown estimates are not safety. Ground patients need normal rescue to a bed before feeding.")
    return context, criteria


def helper_frontier(snapshot, patient, helpers):
    """Discard only known Pareto inferior idle doctors; keep unknown opportunity costs."""
    import math
    pawns = {str(p.get("id")): p for p in snapshot.get("colonists") or []}
    for p in snapshot.get("combat", {}).get("colonists") or []:
        pawns[str(p.get("id"))] = {**pawns.get(str(p.get("id")), {}), **p}
    target = patient.get("position") or {}
    vectors = {}
    idle_jobs = {"wait", "wait_wander", "standing", "idle"}
    def number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    for key, row in helpers.items():
        pawn = pawns.get(str(row.get("worker_id", row.get("id", key))), {})
        pawn = {**pawn, **row}
        job = str(pawn.get("current_job") or "").lower()
        if (job not in idle_jobs or pawn.get("reassign_from_patient_id") is not None
                or any(pawn.get(k) for k in ("dead", "is_dead", "downed", "is_downed", "is_drafted", "in_mental_state", "is_in_mental_state"))):
            continue
        values = [pawn.get("medical_tend_quality"), pawn.get("medical_tend_speed"), pawn.get("medicine_skill")]
        origin = pawn.get("position") or {}
        distance = pawn.get("travel_distance")
        if not number(distance) and all(number(pos.get(c)) for pos in (target, origin) for c in ("x", "z")):
            distance = sum((origin[c]-target[c])**2 for c in ("x", "z"))**.5
        if not all(number(v) for v in [*values, distance]):
            continue
        vectors[key] = (values[0], values[1], -distance, values[2])
    removed = {}
    for key, vector in vectors.items():
        dominators = [other for other, better in vectors.items() if other != key
                      and all(a >= b for a,b in zip(better, vector))
                      and any(a > b for a,b in zip(better, vector))]
        if dominators:
            removed[key] = {"dominated_by": sorted(dominators, key=str),
                "reason": "Known idle doctor has no better tend quality, speed, distance or medicine, and is strictly worse in at least one."}
    return {key: row for key,row in helpers.items() if key not in removed}, removed


def helper_comparison(snapshot, plan, action):
    helpers = plan["helpers"]
    if action == "tend_colonist":
        helpers, excluded = helper_frontier(snapshot, plan["patient"], helpers)
        plan["helper_frontier_exclusions"] = excluded
        snapshot.setdefault("development", {}).setdefault("medical_helper_frontier_exclusions", {})[str(plan["patient"].get("id"))] = excluded
    medicine = {key: float(row.get("medicine_skill") or 0) for key, row in helpers.items()}
    highest = max(medicine.values(), default=0)
    quality = {key: row.get("medical_tend_quality") for key, row in helpers.items()}
    speed = {key: row.get("medical_tend_speed") for key, row in helpers.items()}
    known_quality = [value for value in quality.values() if isinstance(value, (int, float))]
    known_speed = [value for value in speed.values() if isinstance(value, (int, float))]
    colonists = {str(p.get("id")): p for p in snapshot.get("colonists") or []}
    target = plan["patient"].get("position") or {}
    criteria = {}
    for key in sorted(helpers, key=str):
        row = helpers[key]
        origin = (colonists.get(key) or {}).get("position") or {}
        distance = (sum((float(origin[c])-float(target[c]))**2 for c in ("x", "z"))**.5
                    if all(c in origin and c in target for c in ("x", "z")) else None)
        skill = medicine[key]
        relative = ("Highest available medicine skill; stronger expected treatment quality. " if skill == highest
                    else "Lower medicine skill than another feasible doctor; weaker expected treatment quality. ") if action == "tend_colonist" else ""
        if action == "tend_colonist" and isinstance(quality[key], (int, float)):
            q = quality[key]
            relative = f"Tend quality stat {q:.0%}; "
            relative += ("highest available expected quality; " if q == max(known_quality) else "poorer expected quality than another doctor; ")
            if isinstance(speed[key], (int, float)):
                s = speed[key]
                relative += f"tend speed {s:.0%}, " + ("fastest available. " if s == max(known_speed) else "slower than another doctor. ")
            else:
                relative += "tend speed unknown. "
        travel = f"straight-line distance ~{round(distance)} cells; route length unknown" if distance is not None else "travel distance unknown"
        yield_note = (f"Scoped yield from {row.get('expected_current_job')} patient {row.get('expected_care_patient_id')}: {row.get('care_yield_reason')}; old job will be interrupted only if fresh native clinical gates still agree. "
                      if care_order_fields(row) else "")
        criteria[key] = (f"Assign {row.get('worker') or key} to help this patient: " + yield_note + relative
                         + f"medicine {skill:g}; {travel}; native route and reservation feasible")
    context = ("Choose which DOCTOR will treat the patient. Prefer higher treatment quality and speed at similar travel distance. "
               "The options describe caregivers, not patients. Compare actual tend quality and speed before medicine skill: better quality improves treatment and reduces infection risk; "
               "faster tending reduces bleeding delay. When travel is similar, a poorer slower doctor offers weaker care. A much longer trip can miss the death deadline. "
               "Quality stats are expectations, not completed treatment. Existing care stays protected except an explicitly offered, freshly validated clinical yield; feeding and carrying are never interrupted.")
    if action == "tend_colonist" and plan.get("helper_frontier_exclusions"):
        context += " Known dominated idle helpers excluded: " + str(plan["helper_frontier_exclusions"])
    if action != "tend_colonist":
        context = ("Choose an available caregiver to carry or feed this patient. Compare travel delay and native feasibility. "
                   "Medical treatment quality does not measure carrying or feeding ability. Existing care stays protected except an explicitly offered, freshly validated clinical yield; feeding and carrying are never interrupted.")
    return context, criteria


def focus(snapshot, actions):
    dev = snapshot["development"]
    plans = dev.get("medical_action_options") or {}
    food = float((snapshot.get("map", {}).get("resources") or {}).get("food") or 0) > 0
    hungry = {str(p.get("id")) for p in [*snapshot.get("colonists", []), *snapshot.get("animals", [])]
              if p.get("downed") and float(p.get("hunger", p.get("food_level", 1))) < .35}
    recovery = {action for action in ("prepare_patient_bed", "rescue_downed_colonist", "feed_hungry_colonist")
                if any(pid in hungry and any(row.get("food_feasible") is True for row in plan["helpers"].values())
                       for pid, plan in (plans.get(action) or {}).items()) and action in actions}
    waiting = hungry.intersection(dev.get("patient_spot_waiting") or [])
    active = hungry.intersection(active_patients(snapshot))
    if not food or not (recovery or waiting or active):
        return actions
    dev["patient_recovery_focus"] = sorted(recovery)
    urgent = recovery | {"resilience_tend", "tend_colonist", "care_for_injured_animal", "feed_hungry_animal",
                         "rescue_downed_animal", "open_blocked_food_path", "resilience_rescue", "resilience_feed",
                         "prioritize_firefighting", "resilience_temperature", "hold_survival"}
    filtered = [action for action in actions if action in urgent]
    return filtered or ["hold_survival"]


def prepare_bed(client, snapshot, map_state, details, place):
    pid = str(details.get("medical_patient") or "")
    worker = str(details.get("care_helper") or "")
    plan = (snapshot["development"].get("medical_action_options", {}).get("prepare_patient_bed") or {}).get(pid)
    if plan is None or worker not in plan["helpers"]:
        return {"applied": False, "reason": "No verified patient bed and helper selected"}
    fresh = client.get("/api/v1/resilience/context", map_id=snapshot["map"]["id"])
    if pid in active_patients({"development": {}}, fresh) or not any(
            row.get("kind") == "bed_prerequisite" and str(row.get("target_id")) == pid
            and str(row.get("worker_id")) == worker for row in fresh.get("options") or []):
        return {"applied": False, "reason": "Bed prerequisite is no longer feasible"}
    site = plan["site"]
    checked = client.post("/api/v1/builder/site-options", body={"map_id": snapshot["map"]["id"],
        "def_name": plan["def_name"], "near": site["position"], "radius": 1, "limit": 12})
    verified = next((s for s in checked.get("sites") or [] if
        s["position"]["x"] == site["position"]["x"] and s["position"]["z"] == site["position"]["z"]), None)
    if verified is None:
        return {"applied": False, "reason": "Selected temporary bed site is no longer placeable"}
    layout = {"width": 1, "height": 1, "floors": [], "buildings": [{"def_name": plan["def_name"],
              "rel_x": 0, "rel_z": 0, "rotation": int(verified.get("rotation") or 0)}]}
    result = place(client, snapshot["map"]["id"], site["position"], layout)
    if result.get("applied"):
        map_state.setdefault("patient_spot_pending", {}).pop(pid, None)
    elif isinstance(result.get("response"), dict) and result["response"].get("success") is True:
        map_state.setdefault("patient_spot_pending", {})[pid] = {
            **failure_record(int(snapshot["game"].get("tick") or 0), seconds=15),
            "position": site["position"], "def_name": plan["def_name"]}
        result["pending"] = True
    return {**result, "patient_id": int(pid), "helper_id": int(worker), "site": site["position"]}
