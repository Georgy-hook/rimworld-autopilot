"""Food production, preservation, diets and animal welfare through loaded vanilla policies."""
from laya_decisions import ask_laya_choice

_KINDS = {"food_batch": {"bill", "job", "kitchenhome", "fish", "fishzone", "fishpolicy"}, "food_policy": {"diet", "customdiet"}, "preservation": {"cooler", "storage", "stockpile", "stockfood"}, "animal_welfare": {"care", "area", "pen", "gather"}, "herd_policy": {"herd", "sterilize", "release"}}
DESCRIPTIONS = {
    "sustenance_food_batch": "Choose one loaded food, preservation or butcher recipe batch at a usable table with skilled enabled workers and fresh reachable ingredients. Compare human reserves, animal feed, ingredient efficiency, spoilage, kitchen cleanliness and poisoning; production remains ordinary work.",
    "sustenance_food_policy": "Choose an existing food policy for one colonist. Compare allowed reachable foods, scarcity, raw-food poisoning, ideology and mood; changing policy does not feed the pawn.",
    "sustenance_preservation": "Choose an existing cooler target or food-storage priority. Compare power, room temperature, spoiling stock, hauling and access; a setpoint is not proof of a frozen room.",
    "sustenance_animal_welfare": "Choose one animal medicine policy or existing allowed area. Compare illness, pregnancy, nutrition, rest, reachable feed, beds and human medicine reserves. Pen animals use pens rather than allowed areas.",
    "sustenance_herd_policy": "Choose an existing species total population limit, sterilization bill or release-to-wild designation, preserving pregnant and bonded animals. Compare pasture demand, stored feed, breeding sex/age structure, veneration and explosive death hazards; vanilla handlers may slaughter excess animals."}
LABELS = {"sustenance_food_batch": "производство и сохранение пищи", "sustenance_food_policy": "пищевые ограничения", "sustenance_preservation": "холодильник и хранение пищи", "sustenance_animal_welfare": "питание и лечение животных", "sustenance_herd_policy": "размер стада и размножение"}
ACTIONS = set(DESCRIPTIONS)
DOMAINS = {a: "work_orders" for a in ACTIONS}


def collect(client, snapshot):
    result = client.get("/api/v1/sustenance/context", map_id=snapshot["map"]["id"])
    if not isinstance(result, dict) or result.get("available") is False:
        raise ValueError("Sustenance live context unavailable")
    return result


def options(context, action):
    kinds = _KINDS.get(action.removeprefix("sustenance_"), set())
    return {p["key"]: p for p in context.get("options") or [] if isinstance(p, dict) and p.get("kind") in kinds and isinstance(p.get("key"), str)}


def prepare(snapshot, map_state):
    context = snapshot.get("development", {}).get("sustenance", {})
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    return [a for a in sorted(ACTIONS) if options(context, a) and tick - (map_state.get("issued") or {}).get(a, -1000000) >= 15000]


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
    if kind in {"care", "sterilize"}:
        medicine_count = sum(int(m.get("count") or 0) for m in context.get("medicines") or [])
        evidence = f"meds={medicine_count} doctor_skills={[d.get('medicine_skill') for d in context.get('doctors') or []][:4]} " + evidence
    return {"benefit": str(plan.get("label") or kind), "risk": risks.get(kind, str(plan.get("risk") or "Vanilla consequences remain")),
            "cost": evidence + "; " + str(plan.get("cost") or "labor/resources"), "inaction": "Hunger/rot/breeding/current policies continue",
            "uncertainty": "Live option; normal work/outcome still pending"}


def _stage(agent, context, rows, question, instructions):
    # Short aliases leave head/state budget for independently retained consequences.
    indexed = {f"o{i}": row for i, row in enumerate(rows)}
    choices = {alias: row[1] for alias, row in indexed.items()}
    effects = {alias: row[2] for alias, row in indexed.items()}
    choices["defer"] = "Keep current policy; defer"
    effects["defer"] = {"benefit": "Preserve resources/current services", "risk": "Hunger/rot/illness/breeding continue", "cost": "No added labor/resources", "inaction": "Current policy continues", "uncertainty": "No completed care or production"}
    selected, raw = ask_laya_choice(agent, {"decision_facts": {"domain": "production" if question.startswith("production_") else "sustenance", "purpose": question}, "option_effects": effects}, question, instructions, choices, detailed=True)
    if selected not in choices:
        raise ValueError("Unverified sustenance choice")
    return (None if selected == "defer" else indexed[selected][0]), raw


def choose(agent, state, action, snapshot):
    context = snapshot["development"]["sustenance"]
    plans = options(context, action)
    stages = []
    kinds = sorted({p["kind"] for p in plans.values()})
    rows = [(kind, kind, _effects(context, next(p for p in plans.values() if p["kind"] == kind))) for kind in kinds]
    kind, raw = _stage(agent, context, rows, "sustenance_purpose", "Choose purpose or defer. Compare independently retained cost, risk and waiting.")
    stages.append(raw)
    if kind is None:
        return {"sustenance_policy": "defer"}, {"stages": stages}
    plans = {k: p for k, p in plans.items() if p["kind"] == kind}
    subjects = {}
    for key, plan in plans.items():
        subject = str(plan.get("target_id")) if plan.get("target_id") else str(plan.get("value", "")).split(":")[0]
        subjects.setdefault(subject, []).append((key, plan))
    rows = [(subject, str(items[0][1].get("label")), _effects(context, items[0][1])) for subject, items in subjects.items()]
    subject, raw = _stage(agent, context, rows, "sustenance_subject", "Choose actual subject or defer; health, hunger, cleanliness and temperature evidence belongs to each subject.")
    stages.append(raw)
    if subject is None:
        return {"sustenance_policy": "defer"}, {"stages": stages}
    rows = [(key, str(plan.get("label")), _effects(context, plan)) for key, plan in subjects[subject]]
    key, raw = _stage(agent, context, rows, "sustenance_policy", DESCRIPTIONS[action] + " Choose actual policy/operator or defer; normal work remains pending.")
    stages.append(raw)
    return {"sustenance_policy": key or "defer"}, {"stages": stages}


def execute(client, snapshot, map_state, action, selected):
    if action not in ACTIONS:
        return {"applied": False, "reason": "unsupported_action"}
    key = selected.get("sustenance_policy")
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    if key == "defer":
        map_state.setdefault("issued", {})[action] = tick
        return {"applied": False, "reason": "laya_deferred_sustenance"}
    original = options(snapshot.get("development", {}).get("sustenance", {}), action).get(key)
    if not original:
        return {"applied": False, "reason": "unverified_policy"}
    current = options(collect(client, snapshot), action).get(key)
    if not current or any(current.get(k) != original.get(k) for k in ("kind", "target_id", "value")):
        return {"applied": False, "reason": "policy_no_longer_available"}
    result = client.post("/api/v1/sustenance/policy", body={"map_id": snapshot["map"]["id"], "key": key})
    applied = isinstance(result, dict) and result.get("applied") is True
    if applied:
        map_state.setdefault("issued", {})[action] = tick
    return {"applied": applied, "reason": result.get("reason") if isinstance(result, dict) else "invalid_response", "response": result}


def assess(action, snapshot):
    return {"benefit": DESCRIPTIONS.get(action, "unsupported"), "cost": "Ingredients, hauling, electricity, medicine or retained animal products depending on selected policy.", "risk": "Food poisoning, inaccessible feed, power interruption or irreversible ordinary slaughter; inspect loaded alternatives.", "inaction": "Current hunger, spoilage, illness, breeding and consumption continue.", "uncertainty": "Fresh context and server revalidation establish policy availability; ordinary work and biological outcomes remain pending."}


def summary(snapshot):
    c = snapshot.get("development", {}).get("sustenance", {})
    animals = c.get("animals") or []
    return {"hungry_animals": {"count": sum(a.get("food") is not None and float(a["food"]) < .3 for a in animals)}, "underfed_pens": {"count": sum(float(p.get("consumption_per_day") or 0) > float(p.get("pasture_nutrition_per_day") or 0) and float(p.get("stockpiled_nutrition") or 0) < float(p.get("consumption_per_day") or 0) for p in c.get("pens") or [])}}
