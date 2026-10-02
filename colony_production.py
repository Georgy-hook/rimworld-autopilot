"""Live fuel allocation and electricity choices; policy changes use vanilla controls."""
from laya_decisions import ask_laya_choice

DESCRIPTIONS = {"production_utilities": "Choose a building's power switch or automatic refueling policy. Compare fuel stocks, production, room temperature and loss of service. Switches require colonist work; disabling refueling preserves unallocated fuel but does not extinguish existing fuel.",
                "production_feed_batch": "Choose an existing usable table for one researched kibble batch, or defer to preserve food. Uses live protein/greens nutrition and produces the loaded recipe's animal feed. A bill is accepted work, not produced food; human meat and fertilized eggs are excluded."}
LABELS = {"production_utilities": "распределение топлива и энергии", "production_feed_batch": "ограниченный заказ корма"}
ACTIONS = set(DESCRIPTIONS)
DOMAINS = {a: "work_orders" for a in ACTIONS}

def collect(client, snapshot):
    context = client.get("/api/v1/production/context", map_id=snapshot["map"]["id"])
    if not isinstance(context, dict) or context.get("available") is False:
        raise ValueError("Production live context unavailable")
    return context

def options(context):
    plans = {}
    for b in context.get("buildings") or []:
        policies = []
        if isinstance(b.get("switch_on"), bool) and not b.get("flick_pending"):
            policies.append("switch_off" if b["switch_on"] else "switch_on")
        if b.get("can_set_auto_refuel") and isinstance(b.get("auto_refuel"), bool):
            policies.append("disable_refuel" if b["auto_refuel"] else "enable_refuel")
        for policy in policies:
            plans[f"{b['id']}:{policy}"] = {"building": b, "policy": policy}
    return plans

def prepare(snapshot, map_state):
    context = snapshot.setdefault("development", {}).setdefault("production", {})
    context["options"] = options(context)
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    stocks = {s["def_name"]: float(s.get("eligible_nutrition") or 0) for s in context.get("stocks") or []}
    cooks = [p for p in snapshot.get("colonists") or [] if not any(p.get(k) for k in ("dead", "downed", "is_drafted", "in_mental_state"))
             and p.get("current_job") not in {"DoBill", "TendPatient", "Rescue", "FeedPatient"}
             and "Cooking" in (p.get("work_priorities") or {}) and not (p["work_priorities"]["Cooking"] or {}).get("disabled")
             and int((p["work_priorities"]["Cooking"] or {}).get("priority") or 0) > 0]
    suitable_animals = [a for a in context.get("animals") or [] if a.get("can_eat_kibble")]
    context["feed_options"] = {str(t["id"]): {"building": t, "policy": "kibble_batch"} for t in context.get("feed_tables") or []
        if suitable_animals and any(p.get("id") in (t.get("eligible_worker_ids") or []) for p in cooks)
        and t.get("usable") and not t.get("existing_bill") and t.get("ingredients")
        and all(sum(stocks.get(d, 0) for d in i.get("allowed_defs") or []) >= float(i["count"]) for i in t["ingredients"])}
    available = ["production_utilities"] if context["options"] else []
    if context["feed_options"]:
        available.append("production_feed_batch")
    return [a for a in available if tick - (map_state.get("issued") or {}).get("production:" + a, -1000000) >= 15000]

def choose(agent, state, action, snapshot):
    context = snapshot["development"]["production"]
    plans = context.get("feed_options" if action == "production_feed_batch" else "options", {})
    choices = {}
    for key, plan in plans.items():
        b, policy = plan["building"], plan["policy"]
        if policy == "kibble_batch":
            choices[key] = f"target {b.get('label')} #{b['id']}; risk human food loss, animal diet/access unknown; one batch; product {b.get('product')}; cost {b.get('ingredients')}"
        else:
            effect = {"switch_off": "stop service after worker flick; risk heat/cold/storage/defense loss", "switch_on": "restore service after worker flick; consumes power/fuel", "disable_refuel": "save future hauled fuel; existing fuel burns; risk later service outage", "enable_refuel": "allow future fuel hauling; risk consume shared reserves"}[policy]
            choices[key] = f"target {b.get('label')} #{b['id']}; policy {policy}; effect {effect}; on {b.get('switch_on')}; net {b.get('connected')}; watts {b.get('power_output')}; fuel {b.get('fuel')}/{b.get('capacity')}; temp {b.get('temperature')}"
    choices["defer"] = "Keep current services and fuel allocation; no work or service disruption. Existing fuel consumption continues."
    instruction = ("Choose one existing table for one kibble batch or defer. Compare animals' actual diets and access to feed, grazing, current feed stocks, human food reserves and perishables. Kibble uses protein plus greens nutrition; it preserves feed but consumes food and cooking labor. A bill does not feed animals, guarantee ingredient reachability or complete production. Never assume every species eats kibble."
        if action == "production_feed_batch" else "Choose one actual building policy or defer. Switching off may lose cooking, heating, refrigeration, defenses or production. Fuel stocks are total map stocks, not proof of safe access. Auto-refuel changes only future hauling; switches need an ordinary flick job. Do not assume a building's importance from its name alone.")
    facts = {"decision_facts": "Bills are accepted work, not production. Switches need ordinary flick work. Map stock totals do not prove reachability.",
             "animals": [{k: a.get(k) for k in ("species", "food_level", "diet", "can_eat_kibble", "can_graze", "downed")} for a in context.get("animals") or []][:8],
             "stocks": [s for s in context.get("stocks") or [] if s.get("nutrition") or any(s.get("def_name") in (p["building"].get("fuel_defs") or []) for p in plans.values())][:12],
             "perishables": sorted(context.get("perishables") or [], key=lambda item: item.get("ticks_until_rot", 2147483647))[:8],
             "colony": state}
    selected, raw = ask_laya_choice(agent, {"choice_context": facts}, "production_policy", instruction, choices, detailed=True)
    if selected not in choices:
        raise ValueError("Unverified production policy")
    return {"production_policy": selected}, raw

def execute(client, snapshot, map_state, action, selected):
    if action not in ACTIONS:
        return {"applied": False, "reason": "unsupported_action"}
    key = selected.get("production_policy")
    if key == "defer":
        map_state.setdefault("issued", {})["production:" + action] = int(snapshot.get("game", {}).get("tick") or 0)
        return {"applied": False, "reason": "laya_kept_current_utilities"}
    plan_key = "feed_options" if action == "production_feed_batch" else "options"
    original = snapshot.get("development", {}).get("production", {}).get(plan_key, {}).get(key)
    if not original:
        return {"applied": False, "reason": "unverified_policy"}
    current = collect(client, snapshot)
    if action == "production_feed_batch":
        refreshed = {**snapshot, "development": {**snapshot.get("development", {}), "production": current}}
        prepare(refreshed, {})
        live = current.get("feed_options", {}).get(key)
    else:
        live = options(current).get(key)
    if not live or live["building"].get("def_name") != original["building"].get("def_name"):
        return {"applied": False, "reason": "policy_no_longer_available"}
    response = client.post("/api/v1/production/policy", body={"map_id": snapshot["map"]["id"], "building_id": live["building"]["id"], "policy": live["policy"]})
    map_state.setdefault("issued", {})["production:" + action] = int(snapshot.get("game", {}).get("tick") or 0)
    return {"applied": bool(response.get("applied", False)), "reason": response.get("reason"), "response": response}

def assess(action, snapshot):
    if action == "production_feed_batch":
        return {"benefit": "Queue one loaded kibble recipe batch for animal feed.", "cost": "Protein and greens nutrition plus cooking work.", "risk": "May consume food needed by humans; species diet and feed access must be checked.", "inaction": "Current feed stocks, grazing and spoilage continue.", "uncertainty": "Stock totals do not prove reachability; accepted bill is not completed production."}
    return {"benefit": "Allocate fuel or restore/suspend an actual utility.", "cost": "Flick work and possible service interruption; refueling consumes stock later.", "risk": "Heating, food storage, cooking and defenses can depend on this building.", "inaction": "Current consumption and automatic refueling continue.", "uncertainty": "Map totals do not establish reachable fuel; generation and consumption vary with actual use."}
