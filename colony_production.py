"""Live fuel allocation and electricity choices; policy changes use vanilla controls."""
from laya_decisions import ask_laya_choice
from colony_retry import failure_record, recent as retry_recent

DESCRIPTIONS = {"production_utilities": "Choose a building's power switch or automatic refueling policy. Compare fuel stocks, production, room temperature and loss of service. Switches require colonist work; disabling refueling preserves unallocated fuel but does not extinguish existing fuel.",
                "production_feed_batch": "Choose an existing usable table for one researched kibble batch, or defer to preserve food. Uses live protein/greens nutrition and produces the loaded recipe's animal feed. A bill is accepted work, not produced food; loaded recipe filters can consume human meat or fertilized eggs; compare ideology and breeding costs."}
DESCRIPTIONS["production_recipe_batch"] = "Choose one loaded non-food recipe/material at an available completed worktable: medicines, components, equipment, drugs, subcores, mech gestation or loaded recycling. Enabled skilled worker, prerequisites and reachable ingredients checked; one finite vanilla bill."
DESCRIPTIONS["production_material_logistics"] = "Choose a real material logistics workflow: allow one forbidden safe-site resource stack, permit a missing material in existing storage, create an actual roofed indoor stockpile near a completed table, or start a vanilla hauling job. Compare exposure, floor space and competing labor; delivery remains ordinary work."
LABELS = {"production_utilities": "распределение топлива и энергии", "production_feed_batch": "ограниченный заказ корма"}
LABELS["production_recipe_batch"] = "производство по доступным рецептам"
LABELS["production_material_logistics"] = "material storage and delivery"
ACTIONS = set(DESCRIPTIONS)
DOMAINS = {a: "work_orders" for a in ACTIONS}

ENDPOINTS = {"context": "/api/v1/production/context", "recipes": "/api/v1/production/recipes", "logistics": "/api/v1/production/logistics"}
BACKOFF_TICKS = 250


def _read(client, snapshot, endpoint):
    data = client.get(ENDPOINTS[endpoint], map_id=snapshot["map"]["id"])
    if not isinstance(data, dict):
        raise ValueError(f"Production {endpoint}: invalid_response")
    if data.get("available") is False:
        raise ValueError(f"Production {endpoint}: {data.get('reason') or 'unavailable'}")
    field = "buildings" if endpoint == "context" else "options"
    if not isinstance(data.get(field), list):
        raise ValueError(f"Production {endpoint}: invalid_response_missing_{field}")
    return data


def collect(client, snapshot):
    observed, statuses = {}, {}
    for endpoint in ENDPOINTS:
        try:
            observed[endpoint] = _read(client, snapshot, endpoint)
            statuses[endpoint] = {"available": True}
        except Exception as exc:
            error = str(exc)[:240]
            observed[endpoint] = {"available": False, "reason": error}
            statuses[endpoint] = {"available": False, "error": error}
    if not any(status["available"] for status in statuses.values()):
        raise ValueError("; ".join(status["error"] for status in statuses.values()))
    context = dict(observed["context"])
    # Domain availability means at least one independent endpoint succeeded.
    # Detailed endpoint failures remain visible, never converted to empty success.
    context["available"] = True
    context["endpoint_status"] = statuses
    context["recipe_context"] = observed["recipes"]
    context["logistics_context"] = observed["logistics"]
    return context


def _backoff(map_state, snapshot, action, key, reason):
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    entries = map_state.setdefault("production_option_backoff", {}).setdefault(action, {})
    for old_key in list(entries):
        if not retry_recent(entries[old_key], tick, BACKOFF_TICKS):
            del entries[old_key]
    entries[str(key)] = {**failure_record(tick), "reason": str(reason)[:240]}


def _ready_plans(plans, map_state, action, tick):
    entries = (map_state.get("production_option_backoff") or {}).get(action) or {}
    for old_key in list(entries):
        if not retry_recent(entries[old_key], tick, BACKOFF_TICKS):
            del entries[old_key]
    return {key: plan for key, plan in plans.items() if str(key) not in entries}


def _thermal_band(building):
    temperature = building.get("temperature")
    if not isinstance(temperature, (int, float)) or isinstance(temperature, bool):
        return "unknown"
    return "cold" if temperature < 10 else "hot" if temperature > 32 else "normal"


def _utility_scope(plan):
    family = "switch" if plan["policy"] in {"switch_on", "switch_off"} else "refuel"
    return f"{plan['building']['id']}:{family}"


def _remember_utility(map_state, snapshot, plans, duration):
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    history = map_state.setdefault("production_utility_dwell", {})
    for plan in plans:
        history[_utility_scope(plan)] = {"tick": tick, "duration": duration,
            "thermal_band": _thermal_band(plan["building"]), "policy": plan["policy"]}


def _utility_ready(plans, map_state, tick):
    history = map_state.get("production_utility_dwell") or {}
    for scope in list(history):
        entry = history[scope]
        if tick < entry["tick"] or tick - entry["tick"] >= entry["duration"]:
            del history[scope]
    ready = {}
    for key, plan in plans.items():
        scope = _utility_scope(plan)
        entry = history.get(scope)
        if entry and entry["thermal_band"] != _thermal_band(plan["building"]):
            del history[scope]
            entry = None
        if entry is None:
            ready[key] = plan
    return ready

def recipe_options(context):
    if "recipe_options" in context:
        return context["recipe_options"]
    return {p["key"]: p for p in (context.get("recipe_context") or {}).get("options") or [] if isinstance(p, dict) and isinstance(p.get("key"), str) and p.get("worker_ids") and p.get("recipe")}

def _facts(state, question):
    state = state or {}
    # The caller supplies compact requirements. Goal facts precede stage names
    # in the bounded adapter; catalogs and inventory stay outside this envelope.
    return {"endgame": state.get("endgame"), "goal_requirements": state.get("goal_requirements") or {}, "purpose": question}


def _stage(agent, state, rows, question, instructions):
    indexed = {f"o{i}": row for i, row in enumerate(rows)}
    choices = {alias: row[1] for alias, row in indexed.items()}
    effects = {alias: row[2] for alias, row in indexed.items()}
    choices["defer"] = "Keep current stock and work; defer"
    effects["defer"] = {"benefit": "Preserve resources/current services", "risk": "Goal shortages and current delays continue",
                        "cost": "No added labor/resources", "inaction": "Current policy continues", "uncertainty": "No completed production or delivery"}
    selected, raw = ask_laya_choice(agent, {"decision_facts": _facts(state, question), "option_effects": effects},
                                    question, instructions, choices, detailed=True)
    if selected not in choices:
        raise ValueError("Unverified production choice")
    return (None if selected == "defer" else indexed[selected][0]), raw


def recipe_choose(agent, context, state=None):
    plans = recipe_options(context)
    stages = []
    def effect(p):
        return {"benefit": f"{p.get('products') or p.get('recipe')} material={p.get('material') or 'default'} table={p.get('building_id')}", "cost": p.get("cost", "Ingredients/labor"),
                "risk": p.get("risk") or ("Bandwidth/waste/power" if p.get("gestation_cycles") else "Consumes scarce stock; biological/social cost if applicable"),
                "inaction": "No products; stocks/labor preserved", "uncertainty": "Bill accepted only; normal work pending"}
    groups = {}
    for key, plan in plans.items(): groups.setdefault(plan.get("category") or "other", []).append((key, plan))
    group, raw = _stage(agent, state, [(category, category, effect(items[0][1])) for category, items in groups.items()], "production_purpose", "Choose production purpose or defer; compare scarcity, bandwidth, waste and costs.")
    stages.append(raw)
    if group is None: return {"production_policy":"defer"}, {"stages":stages}
    recipes = {}
    for key, plan in groups[group]: recipes.setdefault(plan['recipe'], []).append((key,plan))
    recipe, raw = _stage(agent, state, [(r, items[0][1].get('label'), effect(items[0][1])) for r,items in recipes.items()], "production_recipe", "Choose loaded feasible recipe or defer. Work, materials and autonomous cycles remain pending.")
    stages.append(raw)
    if recipe is None: return {"production_policy":"defer"}, {"stages":stages}
    key, raw = _stage(agent, state, [(key, plan.get('label'), effect(plan)) for key, plan in recipes[recipe]], "production_table_material", "Choose actual table/material or defer. Competing resources and labor are real costs.")
    stages.append(raw)
    return {"production_policy":key or "defer"}, {"stages":stages}

def logistics_options(context):
    if "logistics_options" in context:
        return context["logistics_options"]
    return {p["key"]: p for p in (context.get("logistics_context") or {}).get("options") or [] if isinstance(p, dict) and isinstance(p.get("key"), str) and p.get("kind") in {"allow", "shelf", "stockpile", "zone", "haul"}}

def logistics_choose(agent, context, state=None):
    plans = logistics_options(context)
    stages = []
    def effect(plan):
        return {"benefit": str(plan.get("label")), "risk": str(plan.get("risk")), "cost": str(plan.get("cost")), "inaction": "Forbidden/exposed/unstored stock and delivery delays continue", "uncertainty": "Ordinary policy/job only; no delivered materials yet"}
    groups = {}
    for key, plan in plans.items(): groups.setdefault(plan["kind"], []).append((key, plan))
    kind, raw = _stage(agent, state, [(kind, kind, effect(items[0][1])) for kind, items in groups.items()], "production_logistics_purpose", "Choose ordinary material logistics purpose or defer; compare labor, exposure and lost floor space.")
    stages.append(raw)
    if kind is None: return {"production_policy":"defer"}, {"stages":stages}
    subjects = {}
    for key, plan in groups[kind]: subjects.setdefault(str(plan["target_id"]), []).append((key, plan))
    subject, raw = _stage(agent, state, [(subject, str(items[0][1].get('label')), effect(items[0][1])) for subject, items in subjects.items()], "production_logistics_subject", "Choose actual storage, table or material stack; do not claim permission equals delivery.")
    stages.append(raw)
    if subject is None: return {"production_policy":"defer"}, {"stages":stages}
    key, raw = _stage(agent, state, [(key, str(plan.get('label')), effect(plan)) for key, plan in subjects[subject]], "production_logistics_policy", "Choose actual material or enabled hauler, or defer to preserve labor/floor space.")
    stages.append(raw)
    return {"production_policy":key or "defer"}, {"stages":stages}

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
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    context["options"] = _ready_plans(_utility_ready(options(context), map_state, tick), map_state, "production_utilities", tick)
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
    context["feed_options"] = _ready_plans(context["feed_options"], map_state, "production_feed_batch", tick)
    # Filter only the selection projection; keep native endpoint observation intact.
    context["recipe_options"] = _ready_plans(recipe_options({k: v for k, v in context.items() if k != "recipe_options"}), map_state, "production_recipe_batch", tick)
    context["logistics_options"] = _ready_plans(logistics_options({k: v for k, v in context.items() if k != "logistics_options"}), map_state, "production_material_logistics", tick)
    available = ["production_utilities"] if context["options"] else []
    if context["feed_options"]:
        available.append("production_feed_batch")
    if recipe_options(context):
        available.append("production_recipe_batch")
    if logistics_options(context):
        available.append("production_material_logistics")
    # Retire old category utility locks when loading a persisted pre-scope state.
    (map_state.get("issued") or {}).pop("production:production_utilities", None)
    return [a for a in available if tick - (map_state.get("issued") or {}).get("production:" + a, -1000000) >= 15000]

def choose(agent, state, action, snapshot):
    context = snapshot["development"]["production"]
    if action == "production_recipe_batch":
        return recipe_choose(agent, context, state)
    if action == "production_material_logistics":
        return logistics_choose(agent, context, state)
    plans = context.get("feed_options" if action == "production_feed_batch" else "options", {})
    stages = []
    shown_utilities = []
    def effect(plan):
        building, policy = plan["building"], plan["policy"]
        if policy == "kibble_batch":
            hungry = sum(a.get("food_level") is not None and float(a["food_level"]) < .3 for a in context.get("animals") or [] if a.get("can_eat_kibble"))
            return {"benefit": f"Kibble batch at {building.get('label')} hungry compatible animals={hungry}",
                    "risk": "Human meat/fertilized eggs may be consumed; feed access uncertain",
                    "cost": "; ".join(f"nutrition={i.get('count')}" for i in building.get('ingredients') or []),
                    "inaction": "Hunger/grazing/current feed and spoilage continue", "uncertainty": "Bill accepted only; normal cooking/hauling/feed pending"}
        risk = {"switch_off":"Freezing/heating/defense service may stop", "switch_on":"Consumes network power/fuel", "disable_refuel":"Service fails after remaining fuel burns", "enable_refuel":"Consumes shared future hauled fuel"}[policy]
        return {"benefit": f"{policy} {building.get('def_name')} #{building.get('id')}",
                "risk": risk + f"; temperature={building.get('temperature')}",
                "cost": f"net_gain={building.get('net_energy_gain_per_tick')} stored={building.get('net_stored_energy')} fuel={building.get('fuel')}/{building.get('capacity')}",
                "inaction": "Current consumption and service/refueling continue", "uncertainty": "Native flick/hauling work required; actual service not completed"}
    def stage(rows, question):
        if action == "production_utilities":
            shown_utilities.extend(f"{plan['building']['id']}:{plan['policy']}" for _, plan in rows)
        indexed={f"o{i}": (key,plan) for i,(key,plan) in enumerate(rows)}
        choices={alias: str(plan['building'].get('label'))+' '+plan['policy'] for alias,(_,plan) in indexed.items()}
        effects={alias:effect(plan) for alias,(_,plan) in indexed.items()}
        choices['defer']='Keep current services, fuel and food; defer'
        effects['defer']={"benefit":"Preserve services/resources", "risk":"Existing shortages/rot/fuel burn continue", "cost":"No added labor/resources", "inaction":"Current policies continue", "uncertainty":"No produced feed/restored service"}
        selected,raw=ask_laya_choice(agent,{"decision_facts":_facts(state, question),"option_effects":effects},question,DESCRIPTIONS[action],choices,detailed=True)
        stages.append(raw)
        if selected not in choices: raise ValueError('Unverified production policy')
        return None if selected=='defer' else indexed[selected][0]
    if action == 'production_utilities':
        buildings={}
        for key,plan in plans.items():buildings.setdefault(str(plan['building']['id']),[]).append((key,plan))
        subject=stage([(subject,items[0][1]) for subject,items in buildings.items()],'production_utility_building')
        if subject is None:return {'production_policy':'defer', 'shown_utility_options':list(dict.fromkeys(shown_utilities))},{'stages':stages}
        key=stage(buildings[subject],'production_utility_policy')
    else:
        key=stage(list(plans.items()),'production_feed_table')
    return {'production_policy':key or 'defer', **({'shown_utility_options':list(dict.fromkeys(shown_utilities))} if action == 'production_utilities' and key is None else {})},{'stages':stages}


def execute(client, snapshot, map_state, action, selected):
    if action not in ACTIONS:
        return {"applied": False, "reason": "unsupported_action"}
    key = selected.get("production_policy")
    if key == "defer":
        if action == "production_utilities":
            observed = snapshot.get("development", {}).get("production", {}).get("options", {})
            shown = selected.get("shown_utility_options") or []
            _remember_utility(map_state, snapshot, [observed[k] for k in shown if k in observed], BACKOFF_TICKS)
        else:
            map_state.setdefault("issued", {})["production:" + action] = int(snapshot.get("game", {}).get("tick") or 0)
        return {"applied": False, "reason": "laya_deferred_production"}

    context = snapshot.get("development", {}).get("production", {})
    if action == "production_material_logistics":
        original = logistics_options(context).get(key)
        endpoint = "logistics"
    elif action == "production_recipe_batch":
        original = recipe_options(context).get(key)
        endpoint = "recipes"
    else:
        original = context.get("feed_options" if action == "production_feed_batch" else "options", {}).get(key)
        endpoint = "context"
    if not original:
        return {"applied": False, "reason": "unverified_policy"}

    def failed(reason, **details):
        _backoff(map_state, snapshot, action, key, reason)
        return {"applied": False, "reason": reason, **details}

    try:
        current = _read(client, snapshot, endpoint)
    except Exception as exc:
        return failed("production_observation_failed", error=str(exc)[:240], endpoint=endpoint)
    if endpoint == "logistics":
        live = logistics_options({"logistics_context": current}).get(key)
        fields = ("kind", "target_id", "value", "worker_id", "cells")
        if not live or any(live.get(k) != original.get(k) for k in fields):
            return failed("logistics_no_longer_available")
        path = "/api/v1/production/logistics"
        body = {"map_id": snapshot["map"]["id"], "key": key}
    elif endpoint == "recipes":
        live = recipe_options({"recipe_context": current}).get(key)
        if not live or any(live.get(k) != original.get(k) for k in ("building_id", "recipe", "material")):
            return failed("recipe_no_longer_available")
        path = "/api/v1/production/recipe-bill"
        body = {"map_id": snapshot["map"]["id"], "key": key}
    else:
        if action == "production_feed_batch":
            refreshed = {**snapshot, "development": {**snapshot.get("development", {}), "production": current}}
            prepare(refreshed, {})
            live = current.get("feed_options", {}).get(key)
        else:
            live = options(current).get(key)
        if not live or live["building"].get("def_name") != original["building"].get("def_name"):
            return failed("policy_no_longer_available")
        path = "/api/v1/production/policy"
        body = {"map_id": snapshot["map"]["id"], "building_id": live["building"]["id"], "policy": live["policy"]}
    try:
        response = client.post(path, body=body)
    except Exception as exc:
        # POST transport failure can have an unknown native outcome. Reobserve
        # before retrying; never assume either successful delivery or no mutation.
        return failed("production_transport_failed", error=str(exc)[:240], outcome_unknown=True)
    if not isinstance(response, dict) or not isinstance(response.get("applied"), bool):
        return failed("invalid_response", response=response, outcome_unknown=True)
    if not response["applied"]:
        return failed(response.get("reason") or "production_not_applied", response=response)
    if action == "production_utilities":
        _remember_utility(map_state, snapshot, [live], 15000)
    else:
        map_state.setdefault("issued", {})["production:" + action] = int(snapshot.get("game", {}).get("tick") or 0)
    return {"applied": True, "reason": response.get("reason"), "response": response}

def assess(action, snapshot):
    if action == "production_material_logistics":
        return {"benefit": "Make actual stored materials available and route ordinary hauling.", "cost": "Hauling work, storage capacity and indoor floor space.", "risk": "Forbidden intention, route exposure and competing human care/labor.", "inaction": "Materials stay forbidden, exposed or without allowed destination.", "uncertainty": "Native job validation and exact footprint revalidation; delivery remains pending."}
    if action == "production_recipe_batch":
        return {"benefit": "One loaded finite production batch with actual material alternatives.", "cost": "Loaded ingredients, labor, power and mech bandwidth/waste.", "risk": "Competes with medicine, repairs and construction; gestation may stall.", "inaction": "No new production or resource consumption.", "uncertainty": "Fresh reachable/reservable estimate; normal bill job checks exact execution."}
    if action == "production_feed_batch":
        return {"benefit": "Queue one loaded kibble recipe batch for animal feed.", "cost": "Protein and greens nutrition plus cooking work.", "risk": "May consume food needed by humans; species diet and feed access must be checked.", "inaction": "Current feed stocks, grazing and spoilage continue.", "uncertainty": "Stock totals do not prove reachability; accepted bill is not completed production."}
    return {"benefit": "Allocate fuel or restore/suspend an actual utility.", "cost": "Flick work and possible service interruption; refueling consumes stock later.", "risk": "Heating, food storage, cooking and defenses can depend on this building.", "inaction": "Current consumption and automatic refueling continue.", "uncertainty": "Map totals do not establish reachable fuel; generation and consumption vary with actual use."}


def summary(snapshot):
    context = (snapshot.get("development") or {}).get("production") or {}
    blocked = (context.get("logistics_context") or {}).get("blocked") or []
    return {"production_storage_no_hauler": sum(p.get("reason") == "storage_capacity_exists_no_eligible_hauler" for p in blocked),
            "production_storage_route_blocked": sum(p.get("reason") == "storage_capacity_exists_route_reservation_or_priority_blocked" for p in blocked),
            "production_endpoint_failures": sum(status.get("available") is False for status in (context.get("endpoint_status") or {}).values())}
