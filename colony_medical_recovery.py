"""Observed bedside recovery prerequisites, independent of elective colony work."""
import math
import rimworld_laya as bridge
from colony_retry import failure_record, recent

CARE_JOBS = {"tendpatient", "rescue", "feedpatient"}


def refresh_competing_tend_context(client, snapshot):
    """A stand-down refresh must not discard the next finite clinical review.

    Only new competing-care decisions need this read. It never changes a job,
    shortens existing care, or treats an unavailable patient list as empty.
    """
    people = [p for p in (snapshot.get('combat') or {}).get('colonists') or []
              if p.get('id') is not None and not p.get('is_dead')]
    rates = [p['bleeding_rate'] for p in people
             if isinstance(p.get('bleeding_rate'), (int, float))
             and not isinstance(p['bleeding_rate'], bool)
             and math.isfinite(p['bleeding_rate']) and p['bleeding_rate'] >= .1]
    tendable = [p for p in people if p.get('tendable_now') is True]
    initial_drafted_care = (not bridge.combat_planner.live_hostiles(snapshot)
                            and any(p.get('is_downed') and bridge.first_number(p.get('bleeding_rate')) >= 1.5 for p in people)
                            and any(p.get('is_drafted') for p in people))
    # One remaining minor bleed still needs a fresh competing-care context.
    # A former >=1.5 gate let stale stable-patient treatment run indefinitely.
    if not rates and not tendable:
        return None
    dev = snapshot.setdefault('development', {})
    tick = snapshot.get('game', {}).get('tick')
    old = dev.get('competing_tend_context_read')
    if tick is not None and isinstance(old, dict) and old.get('snapshot_tick') == tick:
        return old
    try:
        context = client.get('/api/v1/resilience/context', map_id=int(snapshot.get('map', {}).get('id') or 0))
        if not isinstance(context, dict):
            context = {'available': False, 'error': 'invalid_native_clinical_context'}
        else:
            context = dict(context)
            patients = context.get('patients')
            if context.get('available') is True:
                expected = {p['id'] for p in people if p.get('tendable_now') is True
                            or isinstance(p.get('bleeding_rate'), (int, float))
                            and not isinstance(p['bleeding_rate'], bool) and p['bleeding_rate'] >= .1}
                observed = {p.get('pawn_id') for p in patients or [] if isinstance(p, dict)} if isinstance(patients, list) else set()
                if not isinstance(patients, list) or not expected.issubset(observed):
                    context['read_errors'] = {**(context.get('read_errors') if isinstance(context.get('read_errors'), dict) else {}),
                                              'patient_coverage': sorted(expected - observed)}
                incomplete = [p.get('pawn_id') for p in patients or [] if isinstance(p, dict)
                              and p.get('pawn_id') in expected
                              and p.get('bleeding_evidence_complete') is not True]
                if incomplete:
                    context['read_errors'] = {**(context.get('read_errors') if isinstance(context.get('read_errors'), dict) else {}),
                                              'incomplete_bleeding_evidence': sorted(incomplete)}
            context['patients'] = [{**p, 'conditions': [h for h in p.get('conditions') or []
                                                       if isinstance(h, dict) and h.get('visible', True)]}
                                   for p in patients or [] if isinstance(p, dict)] if isinstance(patients, list) else []
    except bridge.RimApiError as error:
        context = {'available': False, 'error': str(error)}
    dev['resilience'] = context
    available = context.get('available') is True and not any(context.get(k) for k in ('error', 'errors', 'read_errors'))
    info = {'snapshot_tick': tick, 'attempted': True, 'available': available}
    if not available:
        info['error'] = next((context[k] for k in ('error', 'errors', 'read_errors', 'reason') if context.get(k)),
                             'native_clinical_context_unavailable')
        snapshot.setdefault('warnings', []).append('Current native comparison between patients is unavailable; existing care remains protected.')
    dev['competing_tend_context_read'] = info
    return info


def combat_release_tend_options(snapshot):
    """Native offered first aid for exact selected jobs, before broad undraft."""
    context = (snapshot.get('development') or {}).get('resilience') or {}
    if (context.get('available') is not True
            or context.get('combat_release_tends_available') is not True
            or not isinstance(context.get('combat_release_tends'), list)
            or any(context.get(k) for k in ('error', 'errors', 'read_errors'))
            or bridge.combat_planner.live_hostiles(snapshot)
            or any(p.get('active_threat') for p in (snapshot.get('combat') or {}).get('hostile_buildings') or [])):
        return {}
    people = {p.get('id'): p for p in (snapshot.get('combat') or {}).get('colonists') or []}
    capable = bridge.combat_planner.medically_capable_ids(snapshot)
    options = {}
    for offer in context['combat_release_tends']:
        if not isinstance(offer, dict):
            continue
        did, pid, jid = (offer.get(k) for k in ('doctor_id', 'patient_id', 'release_combat_job_id'))
        if any(type(x) is not int for x in (did, pid, jid)) or did == pid:
            continue
        doctor, patient = people.get(did), people.get(pid)
        if (not doctor or not patient or did not in capable
                or doctor.get('is_drafted') is not True or doctor.get('has_care_job') is not False
                or type(doctor.get('queued_job_count')) is not int or doctor['queued_job_count'] != 0
                or doctor.get('carrying_pawn_id') or doctor.get('carrying_player_pawn')
                or any(doctor.get(k) for k in ('is_dead', 'is_downed', 'is_in_mental_state'))
                or offer.get('expected_current_job') not in {'AttackStatic', 'Wait_Combat'}
                or doctor.get('current_job') != offer['expected_current_job']
                or patient.get('is_downed') is not True or patient.get('is_dead')
                or patient.get('has_care_job') or patient.get('carrying_pawn_id')
                or patient.get('carrying_player_pawn')
                or bridge.first_number(patient.get('bleeding_rate')) < 1.5):
            continue
        values = [offer.get(k) for k in ('travel_ticks', 'locked_ticks', 'medical_tend_speed', 'medical_tend_quality')]
        if (any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v < 0 for v in values)
                or offer['medical_tend_speed'] <= 0):
            continue
        deadline = offer.get('bleedout_ticks')
        if deadline is not None and (not isinstance(deadline, (int, float))
                or isinstance(deadline, bool) or not math.isfinite(deadline) or deadline < 0):
            continue
        name = f'tend_{pid}_{did}'
        options[name] = dict(kind='tend', doctor_id=did, patient_id=pid, self_tend=False,
            release_combat_job_id=jid, expected_combat_job=offer['expected_current_job'],
            estimated_bleedout_ticks=deadline, native_travel_ticks=offer['travel_ticks'],
            native_locked_ticks=offer['locked_ticks'],
            summary=(f"First aid after observed combat: {offer.get('doctor') or did} -> {offer.get('patient') or pid}. "
                     f"Native approach {offer['travel_ticks']:.0f} ticks plus current lock {offer['locked_ticks']:.0f}; "
                     f"native tend speed {offer['medical_tend_speed']:.0%}, quality {offer['medical_tend_quality']:.0%}. "
                     + (f"Remaining bleedout estimate {deadline:.0f} ticks. " if deadline is not None else "Bleedout deadline unknown. ")
                     + "Choose this initial patient before releasing the doctor to ordinary work. "
                     "Native POST rechecks this exact combat job, no active threat, medical ability, patient and route; "
                     "only this doctor is undrafted and assigned a normal tend job. Arrival and completed treatment remain unverified."))
    return options


def competing_tend_review(snapshot, row):
    """Complete one native tend, then re-read a competing bleeding triage."""
    context = (snapshot.get('development') or {}).get('resilience') or {}
    if (row.get('kind') != 'tend' or context.get('available') is not True
            or any(context.get(k) for k in ('error', 'errors', 'read_errors'))):
        return False
    living = {str(p.get('id')) for p in (snapshot.get('combat') or {}).get('colonists') or []
              if not p.get('is_dead')}
    rates = []
    for patient in context.get('patients') or []:
        rate = patient.get('bleeding_total')
        if (str(patient.get('pawn_id')) not in living
                or patient.get('bleeding_evidence_complete') is not True
                or patient.get('tendable_now') is not True
                or not isinstance(rate, (int, float)) or isinstance(rate, bool)
                or not math.isfinite(rate)):
            continue
        if rate >= .1:
            rates.append(rate)
    selected = row.get('patient_id')
    if type(selected) is int:
        patient = next((p for p in context.get('patients') or [] if p.get('pawn_id') == selected), {})
        if (str(selected) not in living or patient.get('bleeding_evidence_complete') is not True
                or patient.get('tendable_now') is not True):
            return False
        # Routine injury treatment has a native completion boundary even for
        # the last bleeding patient. Independent acute disease care keeps its
        # existing protection, rather than yielding on a guessed deadline.
        for h in patient.get('conditions') or []:
            if h.get('def_name') in {'BloodLoss', 'Malnutrition'}:
                continue
            immunity = h.get('immunity')
            if (h.get('life_threatening') is True
                    or h.get('immunity_can_develop') is True and isinstance(immunity, (int,float)) and immunity < 1
                    or h.get('tendable_now') and (float(h.get('lethal_severity') or 0)>0
                        or 'infection' in str(h.get('def_name') or '').lower())):
                return False
        return True
    return len(rates) >= 2


def critical_caregiver_self_tend(snapshot, row):
    """Keep validated major caregiver bleeding in a new care comparison."""
    actor_id = row.get('doctor_id')
    if (row.get('kind') != 'tend' or row.get('self_tend') is not True
            or type(actor_id) is not int or type(row.get('patient_id')) is not int
            or row['patient_id'] != actor_id):
        return False
    actor = next((p for p in (snapshot.get('combat') or {}).get('colonists') or []
                  if p.get('id') == actor_id), None)
    if actor is None:
        return False
    binding = bridge.combat_planner.stable_patient_self_tend_binding(snapshot, actor)
    if binding is not None:
        return (type(row.get('reassign_from_patient_id')) is int
                and all(row.get(key) == value for key, value in binding.items()))
    # A completed finite tend leaves a genuinely free doctor. Do not require
    # an old patient binding at that boundary, or drop self-care again solely
    # because another patient's death deadline is earlier. This does not
    # authorize interrupting treatment or a later queued instruction.
    context = (snapshot.get('development') or {}).get('resilience') or {}
    if (context.get('available') is not True
            or any(context.get(k) for k in ('error', 'errors', 'read_errors'))
            or any(row.get(k) is not None for k in ('reassign_from_patient_id',
                   'reassign_from_rescue_patient_id', 'care_yield_reason'))
            or actor_id not in bridge.combat_planner.medically_capable_ids(snapshot)
            or not isinstance(actor.get('current_job'), str) or not actor['current_job']
            or bridge.combat_planner.active_clinical_care(actor)
            or actor.get('has_care_job') is True
            or type(actor.get('queued_job_count')) is not int or actor['queued_job_count'] != 0
            or actor.get('is_drafted') or actor.get('carrying_pawn_id')
            or actor.get('carrying_player_pawn')
            or actor_id in bridge.combat_planner.protected_care_retreat_ids(snapshot)
            or not bridge.combat_planner.safe_new_self_tend(snapshot, actor)):
        return False
    own = bridge.combat_planner.native_care_patient(snapshot, actor)
    rate = own.get('bleeding_total')
    return (own.get('bleeding_evidence_complete') is True and own.get('tendable_now') is True
            and isinstance(rate, (int, float)) and not isinstance(rate, bool)
            and math.isfinite(rate) and rate >= 1.5)


def clinical_order_frontier(snapshot, plans):
    """Compare new assignments for the same free doctor using native deadlines.

    Running care is untouched. A validated critically bleeding caregiver may
    self-tend instead of taking a new patient: death deadlines do not predict
    when the last mobile doctor will become incapable. Both choices remain.
    Unknown deadlines and independent acute disease, starvation or thermal
    crises remain alternatives rather than assumed safe.
    Call after rejected assignments are removed so a blocked patient cannot
    exclude the doctor's feasible care for everybody else.
    """
    patients = {str(p.get('pawn_id')): p for p in
                (snapshot.get('development') or {}).get('resilience', {}).get('patients') or []}

    def deadline(pid):
        p = patients.get(str(pid), {})
        value, rate = p.get('bleedout_ticks'), p.get('bleeding_total')
        return (value if p.get('bleeding_evidence_complete') is True
                and isinstance(rate, (int, float)) and rate >= .1
                and isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 else None)

    def independent_crisis(pid, earliest):
        p = patients.get(str(pid), {})
        starvation = p.get('starvation_ticks')
        if isinstance(starvation, (int, float)) and math.isfinite(starvation) and starvation <= earliest + 1800:
            return True
        for h in p.get('conditions') or []:
            if not isinstance(h, dict) or h.get('def_name') == 'BloodLoss':
                continue
            if h.get('life_threatening') is True:
                return True
            immunity = h.get('immunity')
            if (h.get('tendable_now') and h.get('immunity_can_develop') is True
                    and isinstance(immunity, (int, float)) and 0 <= immunity < 1):
                return True
        return False

    earliest = {}
    for row in plans.values():
        limit = deadline(row.get('patient_id'))
        if row.get('kind') == 'tend' and limit is not None:
            actor = str(row.get('doctor_id'))
            earliest[actor] = min(earliest.get(actor, float('inf')), limit)
    result, excluded = {}, {}
    for key, row in plans.items():
        actor = str(row.get('doctor_id')); first = earliest.get(actor)
        limit = deadline(row.get('patient_id'))
        native = patients.get(str(row.get('patient_id')), {})
        rate = native.get('bleeding_total')
        stable_bleeding = (native.get('bleeding_evidence_complete') is True
                           and isinstance(rate, (int, float)) and math.isfinite(rate) and 0 <= rate < .1)
        if (first is not None and row.get('kind') in {'tend', 'rescue', 'rest'}
                and row.get('thermal_rescue') is not True
                and not critical_caregiver_self_tend(snapshot, row)
                and (stable_bleeding if limit is None else limit > first + 1800)
                and not independent_crisis(row.get('patient_id'), first)):
            excluded[key] = dict(doctor_id=row.get('doctor_id'), patient_id=row.get('patient_id'),
                                 earliest_native_bleedout_ticks=first, this_native_bleedout_ticks=limit)
        else:
            result[key] = row
    snapshot.setdefault('development', {})['clinical_order_frontier'] = excluded
    return result


def helpers(snapshot, patient_id, doctor=False):
    combat = {str(p.get("id")): p for p in snapshot.get("combat", {}).get("colonists") or []}
    retreating = bridge.combat_planner.protected_care_retreat_ids(snapshot)
    rows = []
    for pawn in snapshot.get("colonists") or []:
        live = combat.get(str(pawn.get("id"))) or {}
        if (str(pawn.get("id")) == str(patient_id) or pawn.get("downed") or live.get("is_downed") or pawn.get("dead") or live.get("is_dead")
                or pawn.get("id") in retreating
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
    thermal = (row.get("thermal_rescue") is True and row.get("kind") == "rescue"
               and row.get("care_yield_reason") == "nonbleeding_tend_to_thermal_rescue_same_patient"
               and binding["expected_current_job"] == "TendPatient"
               and binding["expected_care_patient_id"] == row.get("target_id"))
    if row.get("food_feasible") is not True and not thermal:
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
    if any(worker.get(k) for k in ("dead", "is_dead", "downed", "is_downed", "in_mental_state", "is_in_mental_state", "is_drafted", "carried_thing_id", "carrying_pawn_id", "carrying_player_pawn")):
        return None
    if any(str(active.get('worker_id')) == str(row.get('worker_id')) and active.get('carried_thing_id')
           for active in snapshot.get('development', {}).get('resilience', {}).get('active_orders') or []):
        return None
    if str(worker.get("id")) == str(row.get("target_id")):
        return None
    patients = list(snapshot.get("colonists") or [])
    if thermal:
        patients += list(snapshot.get("animals") or [])  # This collection contains owned animals; wildlife is separate.
    old = next((p for p in patients
                if str(p.get("id")) == str(binding["expected_care_patient_id"])), None)
    native_patients = snapshot.get("development", {}).get("resilience", {}).get("patients") or []
    old_native = next((p for p in native_patients if str(p.get("pawn_id")) == str(binding["expected_care_patient_id"])), {})
    if old is None:
        return None
    conditions = old.get("health_conditions", old_native.get("conditions"))
    if not isinstance(conditions, list) or any(not isinstance(h, dict) for h in conditions):
        return None
    exempt = {"BloodLoss", "Malnutrition"} | ({"Hypothermia", "Heatstroke", "Frostbite"} if thermal else set())
    if any(h.get("def_name") not in exempt and (
            (h.get("immunity_can_develop") is not False and h.get("immunity") is not None and float(h["immunity"]) < 1)
            or h.get("life_threatening") or h.get("tendable_now") and (
                float(h.get("lethal_severity") or 0) > 0 or "infection" in str(h.get("def_name") or "").lower()))
           for h in conditions):
        return None
    rate = old.get("bleeding_rate", old_native.get("bleeding_total"))
    if not isinstance(rate, (int, float)) or isinstance(rate, bool):
        return None
    if thermal and (rate != 0 or float(worker.get('bleeding_rate') or 0) > 0 or not (old.get("downed") or old_native.get("downed"))
                    or row.get("bed_id") == old_native.get("current_bed_id")
                    or not any(h.get("def_name") in {"Hypothermia", "Heatstroke"} and float(h.get("severity") or 0) >= .1 for h in conditions)
                    or not isinstance(row.get("bed_id"), int)
                    or not all(isinstance(row.get(k), (int, float)) for k in ("current_temperature", "destination_temperature"))
                    or abs(row["destination_temperature"] - row["current_temperature"]) < 5):
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
        if action is None or patient is None or (pid in active and not (yield_worker and (row.get("kind") == "feed" or row.get("thermal_rescue") is True)
                and str(row.get("expected_care_patient_id")) == pid)):
            continue
        if action == "tend_colonist" and not bridge.combat_planner.new_treatment_window(snapshot, patient):
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
            or (h.get("immunity") is not None and h.get('immunity_can_develop') is not False)
            or float(h.get("lethal_severity") or 0) > 0
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
    # A care job owns its actor, not every worker on the map. Once the
    # required care is already underway, let spare workers replenish food.
    # Every executor still protects the exact active clinical job.
    if not recovery and helpers(snapshot, None):
        dev["patient_recovery_parallel_work"] = True
        return actions
    urgent = recovery | {"resilience_tend", "tend_colonist", "care_for_injured_animal", "feed_hungry_animal",
                         "rescue_downed_animal", "open_blocked_food_path", "resilience_rescue", "resilience_feed",
                         "prioritize_firefighting", "resilience_temperature", "hold_survival"}
    if dev.get("cold_start_focus") == "refuel_occupied_room":
        urgent.add("refuel_building")
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


def post_combat_job_observed(combat, plan):
    actor = next((p for p in combat.get('colonists') or [] if p.get('id') == plan.get('doctor_id')), {})
    job = {'tend': 'TendPatient', 'rescue': 'Rescue', 'rest': 'LayDown'}.get(plan.get('kind'))
    target = plan.get('bed_id') if plan.get('kind') == 'rest' else plan.get('patient_id')
    return (bool(actor) and actor.get('current_job') == job and actor.get('current_job_target_id') == target
            and (plan.get('kind') != 'rescue' or actor.get('current_job_target_id_b') == plan.get('bed_id')))


def care_failure_state(snapshot, plan):
    """Material clinical changes reopen a failed pair; walking and tiny severity changes do not."""
    live = {str(p.get('id')): p for p in snapshot.get('combat', {}).get('colonists') or []}
    detail = {str(p.get('id')): p for p in snapshot.get('colonists') or []}
    people = []
    for pid in (plan.get('patient_id'), plan.get('doctor_id')):
        p = {**detail.get(str(pid), {}), **live.get(str(pid), {})}
        people.append((pid, *(bool(p.get(k)) for k in ('downed', 'is_downed', 'dead', 'is_dead', 'is_drafted', 'is_in_mental_state')),
                       p.get('current_job'), p.get('current_job_target_id'), p.get('carrying_pawn_id'),
                       float(p.get('bleeding_rate') or 0) > 0,
                       int(float(p.get('bleeding_rate') or 0) * 2),
                       tuple(sorted((h.get('def_name') or '', bool(h.get('tendable_now')), bool(h.get('life_threatening')))
                                    for h in detail.get(str(pid), {}).get('health_conditions') or []))))
    return repr((snapshot.get('map', {}).get('id'), people, plan.get('bed_id')))


def validate_post_combat_plan(client, snapshot, plan, options_for):
    """Repeat the existing planner with fresh combat facts; preserve an exact current job."""
    combat = client.get('/api/v1/combat/state', map_id=snapshot['map']['id'])
    if not isinstance(combat, dict) or not isinstance(combat.get('colonists'), list):
        raise bridge.RimApiError('Incomplete care readback')
    actor = next((p for p in combat['colonists'] if p.get('id') == plan.get('doctor_id')), {})
    patient = next((p for p in combat['colonists'] if p.get('id') == plan.get('patient_id')), {})
    initial_release = (plan.get('kind') == 'tend' and plan.get('self_tend') is False
                       and type(plan.get('release_combat_job_id')) is int)
    if (not actor or not patient or patient.get('is_dead') or actor.get('is_dead')
            or actor.get('is_downed') or actor.get('is_in_mental_state')
            or actor.get('is_drafted') and not initial_release):
        return {'applied': False, 'assignment_accepted': False, 'reason': 'care_actor_or_patient_changed'}, combat
    if actor.get('id') in bridge.combat_planner.protected_care_retreat_ids({'combat': combat}):
        return {'applied': False, 'assignment_accepted': False, 'job_observed': False,
                'escape_job_observed': True, 'in_progress': True, 'completion': 'unverified',
                'reason': 'care_escape_in_progress'}, combat
    if post_combat_job_observed(combat, plan):
        return {'applied': False, 'assignment_accepted': False, 'job_observed': True,
                'in_progress': True, 'completion': 'unverified', 'reason': 'exact_care_job_in_progress'}, combat
    if (str(actor.get('current_job') or '').casefold() in CARE_JOBS
            and not (plan.get('kind') == 'tend' and actor.get('current_job') == 'TendPatient'
                     and plan.get('reassign_from_patient_id') is not None
                     and actor.get('current_job_target_id') == plan['reassign_from_patient_id'])
                 and not (plan.get('kind') == 'tend' and actor.get('current_job') == 'Rescue'
                          and plan.get('reassign_from_rescue_patient_id') == patient.get('id')
                          and actor.get('current_job_target_id') == patient.get('id')
                          and not actor.get('carrying_pawn_id') and not actor.get('carrying_player_pawn'))):
        return {'applied': False, 'assignment_accepted': False, 'reason': 'care_actor_is_providing_other_care'}, combat
    fresh = {**snapshot, 'combat': combat}
    identity = ('kind', 'patient_id', 'doctor_id', 'bed_id', 'self_tend', 'reassign_from_patient_id', 'reassign_from_rescue_patient_id', 'release_combat_job_id')
    if not any(all(row.get(k) == plan.get(k) for k in identity) for row in options_for(fresh).values()):
        return {'applied': False, 'assignment_accepted': False, 'reason': 'care_selection_changed'}, combat
    return None, combat


def ordinary_bed_candidate(bed, pawn_id):
    """Native ownership and body compatibility; a missing DTO is not a free bed."""
    owners = bed.get('bed_owner_ids')
    compatible = bed.get('bed_compatible_pawn_ids')
    return (type(pawn_id) is int and isinstance(owners, list) and isinstance(compatible, list)
            and all(type(owner) is int and owner == pawn_id for owner in owners)
            and any(type(actor) is int and actor == pawn_id for actor in compatible)
            and not bed.get('medical') and not bed.get('for_prisoners'))


def bound_native_refusal(response, identities):
    """An explicit unchanged-state refusal bound to this command, never acceptance."""
    native = response.get('data', response) if isinstance(response, dict) else {}
    if (not isinstance(native, dict) or native.get('applied') is not False
            or native.get('blocked') is not True or not isinstance(native.get('reason'), str)
            or not native['reason'].strip()):
        return None
    for key, value in identities.items():
        actual = native.get(key)
        if (value is None and actual is not None
                or value is not None and (type(actual) is not int or actual != value)):
            return None
    return native


def observe_post_combat_assignment(client, snapshot, plan, result):
    """Acceptance is an assignment result; exact observation still is not treatment completion."""
    response = result.get('response')
    endpoint = {'tend': '/api/v1/pawn/medical/tend', 'rest': '/api/v1/pawn/medical/bed-rest'}.get(plan.get('kind'), '/api/v1/pawn/job')
    accepted = bridge.command_acceptance({'endpoint': endpoint}, response)
    result.update(applied=accepted is True, assignment_accepted=accepted, completion='unverified')
    native = bound_native_refusal(response, {'patient_pawn_id': plan.get('patient_id'),
                                           'doctor_pawn_id': plan.get('doctor_id')})
    refusal = plan.get('kind') == 'tend' and accepted is False and native is not None
    if refusal:
        result.update(blocked=True, native_refusal=native['reason'], reason=native['reason'])
    try:
        combat = client.get('/api/v1/combat/state', map_id=snapshot['map']['id'])
        if not isinstance(combat, dict) or not isinstance(combat.get('colonists'), list):
            raise bridge.RimApiError('Incomplete care readback')
        result['job_observed'] = post_combat_job_observed(combat, plan)
        if result['job_observed']:
            result['in_progress'] = True
        elif not refusal:
            result['reason'] = 'care_job_not_observed'
    except bridge.RimApiError:
        result.update(job_observed=None, outcome_unknown=True, reason='care_readback_unknown')
    return result
