"""Food production, preservation, diets and animal welfare through loaded vanilla policies."""
from laya_decisions import ask_laya_choice
from colony_retry import failure_record, recent as retry_recent
from colony_capabilities import food_planning_facts

_KINDS = {"food_batch": {"bill", "job", "kitchenhome", "fish", "fishzone", "fishpolicy", "pausefeed"}, "food_policy": {"diet", "customdiet"}, "preservation": {"cooler", "storage", "stockpile", "stockfood"}, "animal_welfare": {"care", "area", "pen", "gather"}, "herd_policy": {"herd", "sterilize", "release"}}
DESCRIPTIONS = {
    "sustenance_food_batch": "Choose a feasible food or butcher recipe batch, fishing workflow, or explicit kitchen preparation. Preparation cleans or configures a kitchen and produces no food; a food bill still requires a usable table, enabled skilled worker and reachable ingredients. Compare human reserves, animal feed, fuel, spoilage and poisoning. Existing unused feed bills can be paused deliberately.",
    "sustenance_food_policy": "Choose an existing food policy for one colonist. Compare allowed reachable foods, scarcity, raw-food poisoning, ideology and mood; changing policy does not feed the pawn.",
    "sustenance_preservation": "Choose an existing cooler target or food-storage priority. Compare power, room temperature, spoiling stock, hauling and access; a setpoint is not proof of a frozen room.",
    "sustenance_animal_welfare": "Choose one animal medicine policy or existing allowed area. Compare illness, pregnancy, nutrition, rest, reachable feed, beds and human medicine reserves. Pen animals use pens rather than allowed areas.",
    "sustenance_herd_policy": "Choose an existing species total population limit, sterilization bill or release-to-wild designation, preserving pregnant and bonded animals. Compare pasture demand, stored feed, breeding sex/age structure, veneration and explosive death hazards; vanilla handlers may slaughter excess animals."}
LABELS = {"sustenance_food_batch": "производство и сохранение пищи", "sustenance_food_policy": "пищевые ограничения", "sustenance_preservation": "холодильник и хранение пищи", "sustenance_animal_welfare": "питание и лечение животных", "sustenance_herd_policy": "размер стада и размножение"}
ACTIONS = set(DESCRIPTIONS)
DOMAINS = {a: "work_orders" for a in ACTIONS}


BACKOFF_TICKS = 250
POLICY_DWELL_TICKS = 15000
DEFER_TICKS = 30000
DEFER_SECONDS = 120


def collect(client, snapshot):
    result = client.get("/api/v1/sustenance/context", map_id=snapshot["map"]["id"])
    if not isinstance(result, dict):
        raise ValueError("Sustenance invalid_response")
    if result.get("available") is False:
        raise ValueError(str(result.get("reason") or "Sustenance unavailable"))
    if not isinstance(result.get("options"), list):
        raise ValueError("Sustenance invalid_response_missing_options")
    return {k: v for k, v in result.items() if k != "prepared_options"}


def options(context, action):
    if action in (context.get("prepared_options") or {}):
        return context["prepared_options"][action]
    kinds = _KINDS.get(action.removeprefix("sustenance_"), set())
    return {p["key"]: p for p in context.get("options") or [] if isinstance(p, dict) and p.get("kind") in kinds and isinstance(p.get("key"), str)}


def _scope(plan):
    kind = plan["kind"]
    family = "diet" if kind in {"diet", "customdiet"} else kind
    target = plan.get("target_id")
    if target is None or kind == "herd":
        target = str(plan.get("value") or "").split(":")[0]
    suffix = ":" + str(plan.get("value")) if kind in {"bill", "stockfood"} else ""
    if kind == "pen": suffix = ":" + str(plan.get("value") or "").split(":")[0]
    return f"{family}:{target}{suffix}"


def _clinical(pawn):
    level = pawn.get("food")
    return {"downed": bool(pawn.get("downed")), "pregnant": bool(pawn.get("pregnant")),
            "food_band": "unknown" if level is None else "hungry" if float(level) < .3 else "fed",
            "health_stages": sorted([{ "def_name": h.get("def_name"), "stage": h.get("stage_index"),
                "life_threatening": bool(h.get("life_threatening"))} for h in pawn.get("health") or []],
                key=lambda h: (str(h["def_name"]), str(h["stage"]), h["life_threatening"]))}


def _guard(context, plan):
    kind, target = plan["kind"], plan.get("target_id")
    if kind == "pausefeed":
        return {"compatible_animals": sum(bool(a.get("can_eat_kibble")) for a in context.get("animals") or []), "identity": plan.get("value")}
    if kind in {"care", "area", "sterilize", "release", "gather", "diet", "customdiet"}:
        pawns = context.get("food_pawns") if kind in {"diet", "customdiet"} else context.get("animals")
        pawn = next((p for p in pawns or [] if p.get("id") == target), {})
        return _clinical(pawn)
    if kind == "herd":
        species = str(plan.get("value") or "").split(":")[0]
        herd = [p for p in context.get("animals") or [] if p.get("species") == species]
        return {"count": len(herd), "pregnant": sum(bool(p.get("pregnant")) for p in herd),
                "hungry": sum(p.get("food") is not None and float(p["food"]) < .3 for p in herd)}
    if kind == "pen":
        pen = next((p for p in context.get("pens") or [] if p.get("id") == target), {})
        demand = pen.get("consumption_per_day")
        pasture = pen.get("pasture_nutrition_per_day")
        stored = pen.get("stockpiled_nutrition")
        return {"enclosed": pen.get("enclosed"),
                "pasture_short": None if demand is None or pasture is None else pasture < demand,
                "stored_short": None if demand is None or stored is None else stored < demand}
    if kind == "cooler":
        cooler = next((c for c in context.get("coolers") or [] if c.get("id") == target), {})
        temperature = cooler.get("temperature")
        band = "unknown" if temperature is None else "frozen" if temperature <= 0 else "chilled" if temperature < 10 else "hot" if temperature > 32 else "normal"
        return {"temperature_band": band, "powered": cooler.get("powered")}
    return {}


def _defer_guard(context, plan):
    scope = _scope(plan)
    # Only meaningful availability/policy changes reopen a declined subject.
    identities = sorted([p.get("key"), str(p.get("value"))] for p in context.get("options") or []
                        if isinstance(p, dict) and p.get("kind") and _scope(p) == scope)
    guard = {"subject": _guard(context, plan), "available": identities}
    if plan["kind"] in {"cooler", "storage", "stockpile", "stockfood"}:
        rows = context.get("stockpiles") if plan["kind"] in {"stockpile", "stockfood"} else context.get("storages")
        target = next((r for r in rows or [] if r.get("id") == plan.get("target_id")), {})
        guard["storage"] = {k: target.get(k) for k in ("priority", "allowed_food", "roofed_fraction")}
        rot = [r.get("ticks_until_rot") for r in context.get("perishables") or []
               if r.get("eligible") is True and isinstance(r.get("ticks_until_rot"), (int, float))]
        guard["rot_urgent"] = bool(rot and min(rot) < 2500)
    return guard


def _prune(history, tick):
    for key in list(history):
        entry = history[key]
        valid = isinstance(entry, dict) and all(isinstance(entry.get(k), (int, float)) and not isinstance(entry.get(k), bool) for k in ("tick", "duration"))
        if not valid or not retry_recent(entry, tick, entry["duration"]):
            del history[key]


def _remember(map_state, snapshot, context, plans, duration, *, deferred=False):
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    history = map_state.setdefault("sustenance_subject_history", {})
    _prune(history, tick)
    for plan in plans:
        history[_scope(plan)] = {**(failure_record(tick, DEFER_SECONDS) if deferred else {"tick": tick}), "duration": duration, "guard": _guard(context, plan), **({"defer_guard": _defer_guard(context, plan)} if deferred else {})}


def _failure(map_state, snapshot, action, key, reason, **details):
    history = map_state.setdefault("sustenance_option_backoff", {}).setdefault(action, {})
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    _prune(history, tick)
    history[str(key)] = {**failure_record(tick), "duration": BACKOFF_TICKS, "reason": str(reason)[:240]}
    return {"applied": False, "reason": reason, **details}


def _food_crisis_plan_ready(snapshot, context, plan):
    """Policy availability alone does not make it useful during starvation.

    Keep actual food production and urgent animal care. Cleaning an empty
    kitchen, rearranging empty shelves and a healthy animal's medicine ceiling
    cannot bridge the shortage. Reconsider them when the observed stock, bill
    readiness or patient changes; this is not a persisted category lock.
    """
    if not food_planning_facts(snapshot)["immediate_food_gap"]:
        return True
    kind = plan.get("kind")
    animal = next((a for a in context.get("animals") or []
                   if a.get("id") == plan.get("target_id")), {})
    if kind == "care":
        return bool(animal.get("health") or animal.get("downed"))
    if kind == "area":
        return bool(animal.get("health") or animal.get("downed")
                    or animal.get("food") is not None and float(animal["food"]) < .3)
    if kind in {"storage", "stockpile", "stockfood", "cooler", "diet", "customdiet"}:
        # Missing stock observations are unknown; known empty human stock is
        # not repaired by increasing a shelf priority or admitting raw hops.
        nutrition = human_nutrition(context)
        return nutrition is None or nutrition > 0 or kind == "cooler" and any(
            p.get("eligible") is True for p in context.get("perishables") or [])
    if kind == "kitchenhome" or kind == "job" and str(plan.get("value") or "").startswith("CleanFilth:"):
        return any(t.get("usable") is True and any(
            b.get("requested") is True and b.get("block_reason") in {
                "ready_for_ordinary_work", "ordinary_job_in_progress"}
            for b in t.get("bills") or []) for t in context.get("tables") or [])
    return True


def prepare(snapshot, map_state):
    context = snapshot.get("development", {}).get("sustenance", {})
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    history = map_state.get("sustenance_subject_history") or {}
    _prune(history, tick)
    context.pop("prepared_options", None)
    prepared = {}
    for action in sorted(ACTIONS):
        # Retire older category-wide locks, which starved newly urgent subjects.
        (map_state.get("issued") or {}).pop(action, None)
        failures = (map_state.get("sustenance_option_backoff") or {}).get(action) or {}
        _prune(failures, tick)
        plans = {}
        for key, plan in options(context, action).items():
            if key in failures: continue
            if not _food_crisis_plan_ready(snapshot, context, plan): continue
            scope = _scope(plan)
            old = history.get(scope)
            if old and (old["guard"] != _guard(context, plan) or "defer_guard" in old and old["defer_guard"] != _defer_guard(context, plan)):
                del history[scope]
                old = None
            cancel = plan["kind"] == "sterilize" and plan.get("value") == "cancel" or plan["kind"] == "release" and str(plan.get("value")).lower() == "false"
            if old is None or cancel: plans[key] = plan
        prepared[action] = plans
    context["prepared_options"] = prepared
    return [a for a in sorted(ACTIONS) if prepared[a]]

def _effects(context, plan):
    kind = plan.get("kind")
    target = plan.get("target_id")
    animal = next((a for a in context.get("animals") or [] if a.get("id") == target), {})
    table = next((t for t in context.get("tables") or [] if t.get("id") == target), {})
    storage_rows = context.get("stockpiles") if kind in {"stockpile", "stockfood"} else context.get("storages")
    storage = next((t for t in storage_rows or [] if t.get("id") == target), {})
    pen = next((p for p in context.get("pens") or [] if p.get("id") == target), {})
    area = next((a for a in context.get("areas") or [] if str(a.get("id")) == str(plan.get("value"))), {})
    health = ",".join(str(h.get("def_name")) for h in animal.get("health") or [])[:45]
    risks = {"bill": "Human meat/corpses or fertilized eggs may be consumed; ideology/poisoning", "diet": "Raw food/mood/ideology; does not feed", "cooler": "Power/heat; target is not frozen food", "storage": f"linked_shelves={storage.get('linked_storage_count')} priority shared; warm storage rots", "stockpile": "Hauling may divert feed; warm storage rots", "stockfood": "May attract scarce food; access uncertain", "care": f"health={health}; pregnant={animal.get('pregnant')}; medicine competes", "area": f"fire={area.get('fire_cells')} temp={area.get('min_temperature')}/{area.get('max_temperature')}; access uncertain", "job": "Interrupts labor; cleaning remains pending", "kitchenhome": "Expands cleaning/fire labor and travel", "pen": "Transfer route/feed not assured", "herd": "Irreversible slaughter; retained sex limits", "sterilize": "Permanent sterility; surgery failure", "release": "Ownership/products lost; wildlife remains"}
    evidence = (f"food={animal.get('food')} rest={animal.get('rest')} medicine={animal.get('medical_care')}" if animal else
                f"cleanliness={table.get('cleanliness')}" if table else
                f"temperature={storage.get('temperature')} priority={storage.get('priority')}" if storage else "")
    if kind == "pausefeed":
        evidence = "Compatible owned animals=0; requested existing bill; human emergency kibble remains a possible use"
    if kind in {"bill", "pausefeed"}:
        relevant = [b for b in table.get("bills") or [] if b.get("recipe") == plan.get("value") or b.get("identity") == plan.get("value")]
        evidence += "; " + ",".join(f"{b.get('recipe')}:{b.get('block_reason')} count={b.get('repeat_count')}" for b in relevant)
    if kind == "fish":
        zone_id = str(plan.get("value") or "").split(":")[-1]
        zone = next((z for z in context.get("fishing") or [] if str(z.get("id")) == zone_id), {})
        evidence = f"population={zone.get('population')} floor={zone.get('population_floor')} frozen={zone.get('frozen')} mode={zone.get('mode')} count={zone.get('repeat')} stock={zone.get('owned_fish')}"
    if kind == "pen":
        evidence = f"pasture={pen.get('pasture_nutrition_per_day')} demand={pen.get('consumption_per_day')} stored={pen.get('stockpiled_nutrition')}"
    if kind == "herd":
        species = str(plan.get("value") or "").split(":")[0]
        herd = [a for a in context.get("animals") or [] if a.get("species") == species]
        male = sum(a.get("gender") == "Male" for a in herd)
        female = sum(a.get("gender") == "Female" for a in herd)
        pregnant = sum(bool(a.get("pregnant")) for a in herd)
        limits = next((h for h in context.get("herds") or [] if h.get("species") == species), {})
        evidence = f"males={male} females={female} pregnant={pregnant} retained={limits.get('males')}/{limits.get('females')}"
    clinical_risk = None
    if kind in {"care", "sterilize"}:
        clinical = sorted(animal.get("health") or [], key=lambda h: (not bool(h.get("life_threatening")), -float(h.get("severity") or 0)))
        health_facts = ";".join(f"{h.get('def_name')}:{h.get('severity')}{'!' if h.get('life_threatening') else ''}" for h in clinical)
        clinical_risk = f"health={health_facts or 'none'}; " + str(plan.get("risk") or risks.get(kind))
        medicine_count = sum(int(m.get("count") or 0) for m in context.get("medicines") or [])
        doctor_skills = [d["medicine_skill"] for d in context.get("doctors") or [] if isinstance(d.get("medicine_skill"), (int, float))]
        evidence = (f"food={animal.get('food')} downed={animal.get('downed')} pregnant={animal.get('pregnant')} meds={medicine_count}; "
                    f"eligible_doctors={len(doctor_skills)} best_skill={max(doctor_skills) if doctor_skills else None}; " + evidence)
    if kind == "cooler":
        cooler = next((c for c in context.get("coolers") or [] if c.get("id") == target), {})
        evidence = f"temperature={cooler.get('temperature')} powered={cooler.get('powered')} current_target={cooler.get('target')} requested={plan.get('value')}"
    if kind == "diet":
        diet = next((d for d in context.get("diets") or [] if str(d.get("id")) == str(plan.get("value"))), {})
        allowed = set(diet.get("allowed") or [])
        usable = [f"{f.get('def_name')}:{f.get('fresh_eligible_nutrition')}" for f in context.get("human_food", context.get("food")) or [] if f.get("def_name") in allowed and f.get("food_type") != "Plant"]
        evidence = "allowed_fresh_nutrition=" + ",".join(usable)
    return {"benefit": str(plan.get("label") or kind), "risk": clinical_risk or str(plan.get("risk") or risks.get(kind) or "Vanilla consequences remain"),
            "cost": evidence + "; " + str(plan.get("cost") or "labor/resources"), "inaction": "Hunger/rot/breeding/current policies continue",
            "uncertainty": "Live option; normal work/outcome still pending"}


def human_nutrition(context):
    food = context.get("human_food", context.get("food"))
    if food is None: return None
    # Legacy observations cannot turn known rough grazing items into human food.
    food = [f for f in food if f.get("food_type") != "Plant"]
    if not all(isinstance(f.get("fresh_eligible_nutrition"), (int, float)) for f in food): return None
    return sum(float(f["fresh_eligible_nutrition"]) for f in food)


def _stage(agent, context, rows, question, instructions, state=None):
    # Short aliases leave head/state budget for independently retained consequences.
    indexed = {f"o{i}": row for i, row in enumerate(rows)}
    choices = {alias: row[1] for alias, row in indexed.items()}
    effects = {alias: row[2] for alias, row in indexed.items()}
    choices["defer"] = "Keep current policy; defer"
    effects["defer"] = {"benefit": "Preserve resources/current services", "risk": "Hunger/rot/illness/breeding continue", "cost": "No added labor/resources", "inaction": "Current policy continues", "uncertainty": "No completed care or production"}
    # Preserve aggregate supply and rot urgency before purpose text in the small facts budget.
    nutrition = human_nutrition(context)
    rot = [p["ticks_until_rot"] for p in context.get("perishables") or []
           if isinstance(p.get("ticks_until_rot"), (int, float)) and p.get("eligible") is True]
    state = state or {}
    facts = {"endgame": state.get("endgame"), "fresh_nutrition": nutrition, "first_rot_ticks": min(rot) if rot else None,
             "feed_access": [{"id": p.get("pawn_id"), "self": p.get("self_reachable_nutrition"), "feeder": p.get("feeder_reachable_nutrition")} for p in sorted(context.get("human_food_access") or [], key=lambda p: (not bool(p.get("downed")), float(p.get("food_level") or 0)))][:2],
             "goal_requirements": state.get("goal_requirements") or {}, "purpose": question}
    selected, raw = ask_laya_choice(agent, {"decision_facts": facts, "option_effects": effects}, question, instructions, choices, detailed=True)
    if selected not in choices:
        raise ValueError("Unverified sustenance choice")
    return (None if selected == "defer" else indexed[selected][0]), raw


def choose(agent, state, action, snapshot):
    context = snapshot["development"]["sustenance"]
    plans = options(context, action)
    stages, shown = [], []
    def stage(rows, question, instructions):
        shown.extend(row[3] for row in rows)
        answer, raw = _stage(agent, context, rows, question, instructions, state)
        stages.append(raw)
        return answer
    def selection(key):
        return {"sustenance_policy": key or "defer", **({"shown_sustenance_options": list(dict.fromkeys(shown))} if key is None else {})}, {"stages": stages}
    kinds = sorted({p["kind"] for p in plans.values()})
    rows = []
    for kind in kinds:
        key, plan = next((key, p) for key, p in plans.items() if p["kind"] == kind)
        purpose = {"job": "Kitchen preparation: cleaning only; produces no food",
                   "kitchenhome": "Kitchen preparation: home area only; produces no food"}.get(kind, kind)
        rows.append((kind, purpose, _effects(context, plan), key))
    kind = stage(rows, "sustenance_purpose", "Choose purpose or defer. Compare independently retained cost, risk and waiting.")
    if kind is None:
        shown.extend(plans)
        return selection(None)
    shown.clear()
    plans = {k: p for k, p in plans.items() if p["kind"] == kind}
    subjects = {}
    for key, plan in plans.items():
        subject = str(plan.get("target_id")) if plan.get("target_id") else str(plan.get("value", "")).split(":")[0]
        subjects.setdefault(subject, []).append((key, plan))
    rows = [(subject, str(items[0][1].get("label")), _effects(context, items[0][1]), items[0][0]) for subject, items in subjects.items()]
    subject = stage(rows, "sustenance_subject", "Choose actual subject or defer; health, hunger, cleanliness and temperature evidence belongs to each subject.")
    if subject is None:
        shown.extend(plans)
        return selection(None)
    shown.clear()
    rows = [(key, str(plan.get("label")), _effects(context, plan), key) for key, plan in subjects[subject]]
    return selection(stage(rows, "sustenance_policy", DESCRIPTIONS[action] + " Choose actual policy/operator or defer; normal work remains pending."))

def execute(client, snapshot, map_state, action, selected):
    if action not in ACTIONS:
        return {"applied": False, "reason": "unsupported_action"}
    key = selected.get("sustenance_policy")
    context = snapshot.get("development", {}).get("sustenance", {})
    observed = options(context, action)
    if key == "defer":
        shown = selected.get("shown_sustenance_options") or []
        _remember(map_state, snapshot, context, [observed[k] for k in shown if k in observed], DEFER_TICKS, deferred=True)
        return {"applied": False, "reason": "laya_deferred_sustenance"}
    original = observed.get(key)
    if not original:
        return {"applied": False, "reason": "unverified_policy"}
    try:
        current_context = collect(client, snapshot)
    except Exception as exc:
        return _failure(map_state, snapshot, action, key, "sustenance_observation_failed", error=str(exc)[:240])
    current = options(current_context, action).get(key)
    if not current or any(current.get(k) != original.get(k) for k in ("kind", "target_id", "value")):
        return _failure(map_state, snapshot, action, key, "policy_no_longer_available")
    if not _food_crisis_plan_ready(snapshot, current_context, current):
        return _failure(map_state, snapshot, action, key, "food_crisis_prerequisite_changed")
    try:
        result = client.post("/api/v1/sustenance/policy", body={"map_id": snapshot["map"]["id"], "key": key})
    except Exception as exc:
        return _failure(map_state, snapshot, action, key, "sustenance_transport_failed", error=str(exc)[:240], outcome_unknown=True)
    if not isinstance(result, dict) or not isinstance(result.get("applied"), bool):
        return _failure(map_state, snapshot, action, key, "invalid_response", response=result, outcome_unknown=True)
    if not result["applied"]:
        return _failure(map_state, snapshot, action, key, result.get("reason") or "sustenance_not_applied", response=result)
    duration = BACKOFF_TICKS if current["kind"] in {"bill", "job", "gather", "fish", "fishzone", "fishpolicy", "kitchenhome", "stockfood"} else POLICY_DWELL_TICKS
    _remember(map_state, snapshot, current_context, [current], duration)
    return {"applied": True, "reason": result.get("reason"), "response": result}

def assess(action, snapshot):
    benefit = DESCRIPTIONS.get(action, "unsupported")
    if action == "sustenance_food_batch":
        plans = options(snapshot.get("development", {}).get("sustenance", {}), action)
        if plans and all(p.get("kind") in {"job", "kitchenhome"} for p in plans.values()):
            benefit = "Kitchen preparation only: clean local filth or include the enclosed kitchen in home area. No feasible food recipe or fishing workflow is currently offered; this action produces no food."
    return {"benefit": benefit, "cost": "Ingredients, hauling, electricity, medicine or retained animal products depending on selected policy.", "risk": "Food poisoning, inaccessible feed, power interruption or irreversible ordinary slaughter; inspect loaded alternatives.", "inaction": "Current hunger, spoilage, illness, breeding and consumption continue.", "uncertainty": "Fresh context and server revalidation establish policy availability; ordinary work and biological outcomes remain pending."}


def summary(snapshot):
    c = snapshot.get("development", {}).get("sustenance", {})
    animals = c.get("animals") or []
    return {"hungry_animals": {"count": sum(a.get("food") is not None and float(a["food"]) < .3 for a in animals)}, "underfed_pens": {"count": sum(float(p.get("consumption_per_day") or 0) > float(p.get("pasture_nutrition_per_day") or 0) and float(p.get("stockpiled_nutrition") or 0) < float(p.get("consumption_per_day") or 0) for p in c.get("pens") or [])}}
