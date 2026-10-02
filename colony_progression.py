"""Measured progression; a doctrine is a preference, never proof of victory."""
from __future__ import annotations

from laya_decisions import ask_laya_choice

DESCRIPTIONS = {"progression_research": "Resolve missing prerequisite frontier for a measured ship route, comparing other research and defer.",
                "progression_ship": "Compare ordinary ship reactor startup or launch against defer using actual engine blockers and survival facts.",
                "progression_boardship": "Choose one passenger/casket or downed-passenger carrier, preserving defenders and doctors; or defer."}
LABELS = {"progression_research": "Следующий шаг исследований", "progression_ship": "Реактор и запуск корабля", "progression_boardship": "Посадка пассажира в корабль"}
ACTIONS = set(DESCRIPTIONS)
DOMAINS = {key: "strategy" for key in ACTIONS}
SHIP_RESEARCH = ("ShipBasics", "ShipCryptosleep", "ShipReactor", "ShipEngine", "ShipComputerCore", "ShipSensorCluster")
APPLIED_RETRY_TICKS = {"progression_research": 30000, "progression_ship": 15000, "progression_boardship": 600}


def _record_cooldown(snapshot, map_state, action, *, deferred=False):
    map_state.setdefault("progression_cooldowns", {})[f"progression:{action}"] = {
        "tick": int((snapshot.get("game") or {}).get("tick") or 0),
        "retry_ticks": 15000 if deferred else APPLIED_RETRY_TICKS[action]}


def _cooling(snapshot, map_state, action):
    cooldowns = map_state.setdefault("progression_cooldowns", {})
    key = f"progression:{action}"
    prior = cooldowns.get(key)
    if not isinstance(prior, dict):
        return False
    delta = int((snapshot.get("game") or {}).get("tick") or 0) - int(prior.get("tick") or 0)
    if delta < 0:
        cooldowns.pop(key, None)  # Reloaded timeline must never retain a future cooldown.
        return False
    return delta < int(prior.get("retry_ticks") or 0)


def _rows(value):
    if isinstance(value, dict):
        value = value.get("projects", [])
    return [r for r in value or [] if isinstance(r, dict)]


def research_frontier(tree, targets):
    """Walk all prerequisites, including hidden ones, without invented shortcuts."""
    by_name = {r.get("name"): r for r in _rows(tree)}
    frontier, blocked, seen = [], [], set()

    def visit(name):
        if name in seen:
            return
        seen.add(name)
        row = by_name.get(name)
        if not row:
            blocked.append({"name": name, "reason": "definition unavailable"})
            return
        if row.get("is_finished"):
            return
        if row.get("can_start_now") is True and row.get("player_has_any_appropriate_research_bench") is True:
            frontier.append(name)
            return
        prereqs = list(row.get("prerequisites") or []) + list(row.get("hidden_prerequisites") or [])
        missing = [p for p in prereqs if not by_name.get(p, {}).get("is_finished")]
        blocked.append({"name": name, "missing": missing, "bench": row.get("player_has_any_appropriate_research_bench"),
                        "analysis_remaining": max(0, int(row.get("required_analyzed_thing_count") or 0) - int(row.get("analyzed_things_completed") or 0))})
        for prerequisite in missing:
            visit(prerequisite)

    for name in targets:
        visit(name)
    return {"frontier": frontier, "blockers": blocked, "complete": bool(targets) and all(by_name.get(n, {}).get("is_finished") for n in targets)}


def collect(client, snapshot):
    result = {"errors": {}, "victory_verified": False}
    development = snapshot.get("development") or {}
    for key, endpoint in (("research_tree", "/api/v1/research/tree"), ("current", "/api/v1/research/progress"),
                          ("native_milestones", "/api/v1/colony/progression")):
        try:
            shared = "current_research" if key == "current" else key
            if shared in development:
                result[key] = development[shared]
            elif key == "native_milestones" and (snapshot.get("map") or {}).get("id") is not None:
                result[key] = client.get(endpoint, map_id=snapshot["map"]["id"])
            else:
                result[key] = client.get(endpoint)
        except Exception as exc:
            result["errors"][key] = str(exc)
    result["ship_research"] = research_frontier(result.get("research_tree"), SHIP_RESEARCH)
    map_id = (snapshot.get("map") or {}).get("id")
    if map_id is not None:
        result["native_milestones"] = [r for r in result.get("native_milestones") or [] if isinstance(r, dict) and str(r.get("map_id")) == str(map_id)]
    return result


def _options(context):
    current = (context.get("current") or {}).get("name")
    frontier = set((context.get("ship_research") or {}).get("frontier") or [])
    options = {}
    for row in _rows(context.get("research_tree")):
        name = row.get("name")
        if not name or name == current or row.get("is_finished") or row.get("can_start_now") is not True or row.get("player_has_any_appropriate_research_bench") is not True:
            continue
        options[name] = {"name": name, "label": row.get("label") or name,
                         "remaining_points": max(0, float(row.get("research_points") or 0) - float(row.get("progress") or 0)),
                         "unlocks": row.get("required_by_this") or [], "ship_prerequisite": name in frontier,
                         "description": row.get("description") or "", "time": "Depends on assigned researchers, bench speed and interruptions; research points are work, not days."}
    return options


def prepare(snapshot, map_state):
    cooling = {action: _cooling(snapshot, map_state, action) for action in ACTIONS}
    context = snapshot.setdefault("development", {}).setdefault("progression", {})
    context["options"] = _options(context)
    doctrine = (map_state or {}).get("doctrine") or snapshot.get("development", {}).get("doctrine") or {}
    pursuing_ship = (doctrine.get("primary_direction") == "research_starflight"
                     or doctrine.get("endgame") == "ship_escape"
                     or doctrine.get("technology") == "starflight")
    # Only add a decision when the route exposes an actionable prerequisite.
    # Ordinary research selection already belongs to the director.
    actions = ["progression_research"] if pursuing_ship and any(r["ship_prerequisite"] for r in context["options"].values()) else []
    if ship_options(context):
        actions.append("progression_ship")
    if boarding_options(context):
        actions.append("progression_boardship")
    return [action for action in actions if not cooling[action]]


def boarding_options(context):
    options = {}
    for ship in context.get("native_milestones") or []:
        if not isinstance(ship, dict) or ship.get("countdown") or ship.get("hostile_pawns", 0):
            continue
        for candidate in ship.get("boarding_options") or []:
            if not isinstance(candidate, dict):
                continue
            key = "_".join(str(candidate.get(k)) for k in ("map_id", "root_id", "pawn_id", "worker_id", "casket_id"))
            options[key] = {**candidate, "colonists_at_home": ship.get("colonists_at_home"),
                            "passengers": ship.get("passengers"), "launch_blockers": ship.get("launch_blockers"),
                            "hostile_pawns": ship.get("hostile_pawns"), "total_item_nutrition": ship.get("total_item_nutrition")}
    return options


def ship_options(context):
    options = {}
    for ship in context.get("native_milestones") or []:
        if not isinstance(ship, dict) or ship.get("countdown"):
            continue
        parts, required = ship.get("parts") or {}, ship.get("required_parts") or {}
        complete = bool(required) and all(parts.get(name, 0) >= count for name, count in required.items())
        action = "launch" if ship.get("launch_blockers") == [] and ship.get("passengers") else "start" if complete and ship.get("has_hibernating_parts") else None
        if action:
            options[f"{ship.get('map_id')}_{ship.get('root_id')}_{action}"] = {"ship_action": action, **ship}
    return options


def comparison(action, context):
    """Put native risks first in separate fields so prompt clipping retains them."""
    if action == "progression_boardship":
        candidates = boarding_options(context)
        effects = {}
        for key, r in candidates.items():
            effects[key] = {
                "benefit": f"Board {r.get('pawn')} into casket {r.get('casket_id')}; {r.get('job')}.",
                "risk": f"{r.get('remaining_armed_mobile_combat_colonists')} armed / {r.get('remaining_mobile_doctors')} doctors remain; psychic bond separation {r.get('psychic_bond_warning')}.",
                "cost": f"Travel + 500 ticks; {r.get('worker')} leaves {r.get('current_job')}; passenger stops working.",
                "inaction": "Delay escape/preservation; keep passenger and worker available for care and defense.",
                "uncertainty": f"Health {r.get('pawn_health_fraction')}, carrier {r.get('worker_health_fraction')}; job may fail; completion needs occupancy observation."}
        facts = {"boarding": "One pawn only; no hostile map; mobile entry waits for reactor Running.",
                 "reactor_running": sorted(set(bool(r.get('reactor_running')) for r in candidates.values())),
                 "downed": sum(bool(r.get('pawn_downed')) for r in candidates.values()),
                 "last_roles": "0 armed or doctors means no such mobile role remains; decide or defer."}
        defer = {"benefit": "Retain available care, defense and worker labor.", "risk": "Escape delayed; downed patient remains outside cryptosleep.",
                 "cost": "Time passes; no boarding order.", "inaction": "Caskets remain unfilled; current jobs continue.", "uncertainty": "Patient and threat conditions can change before the next decision."}
    elif action == "progression_ship":
        candidates = ship_options(context)
        effects = {}
        for key, r in candidates.items():
            starting = r['ship_action'] == 'start'
            effects[key] = {
                "benefit": "Start reactor preparation for escape." if starting else f"Launch passengers {r.get('passengers')}.",
                "risk": f"{r.get('startup_days')} days repeated raids; {r.get('armed_mobile_combat_colonists')} armed, {r.get('downed_colonists')} downed." if starting else f"{len(r.get('colonists_at_home') or [])} unboarded colonists left behind; ship consumed.",
                "cost": f"Defense and medical labor for {r.get('startup_days')} days." if starting else f"Ship consumed; left home {r.get('colonists_at_home')}.",
                "inaction": "Delay escape; improve reserves/defense and boarding first.",
                "uncertainty": f"Total item nutrition {r.get('total_item_nutrition')} is NOT accessible safe food; counts do not prove defense quality."}
        facts = {"startup_days": sorted(set(r.get('startup_days') for r in candidates.values() if r.get('startup_days') is not None)),
                 "outside_passengers": list(dict.fromkeys(name for r in candidates.values() for name in r.get('colonists_at_home') or [])),
                 "danger": "Repeated startup raids; unboarded colonists stay home.",
                 "hostiles": sum(int(r.get('hostile_pawns') or 0) for r in candidates.values())}
        defer = {"benefit": "Preserve home labor; prepare reserves or board more passengers.", "risk": "Escape postponed; threats can arrive during delay.",
                 "cost": "More colony time before escape.", "inaction": "Reactor/launch command stays unissued.", "uncertainty": "Waiting does not guarantee improved readiness."}
    else:
        candidates = _options(context)
        effects = {name: {"benefit": f"{r['label']}; unlocks {r['unlocks']}; ship prerequisite {r['ship_prerequisite']}.",
                          "risk": "Research labor competes with survival; switching delays the current unlock.",
                          "cost": f"{r['remaining_points']} remaining research points, researcher time and bench power.",
                          "inaction": "Keep current project; selected technology remains unavailable.",
                          "uncertainty": "Points measure work, not days; no victory inferred from research."} for name, r in candidates.items()}
        facts = {"current_project": (context.get('current') or {}).get('name'), "time": "Research points are work, not completion days."}
        defer = {"benefit": "Keep current research and labor flexibility.", "risk": "Missing technology unlocks delayed.", "cost": "No target change; current work continues.",
                 "inaction": "Prerequisite frontier remains unresolved.", "uncertainty": "Current project may still require staff, power and inputs."}
    choices = {key: f"{r.get('label') or r.get('pawn') or r.get('ship_action') or key}; {effects[key]['benefit']}" for key, r in candidates.items()}
    choices['defer'] = 'Keep current work; defer this commitment.'
    effects['defer'] = defer
    return candidates, choices, effects, facts


def choose(agent, state, action, snapshot):
    context = snapshot.get('development', {}).get('progression', {})
    candidates, choices, effects, facts = comparison(action, context)
    selected, raw = ask_laya_choice(agent, {**state, 'option_effects': effects, 'decision_facts': facts}, action,
                                    'Choose an ordinary progression step or defer; compare benefit, risk, cost, delay and uncertainty.', choices, detailed=True)
    return ({'defer': True} if selected == 'defer' else candidates[selected]), raw


def execute(client, snapshot, map_state, action, selected):
    if action not in ACTIONS:
        return {"applied": False, "reason": "deferred or unsupported action"}
    if selected.get("defer"):
        _record_cooldown(snapshot, map_state, action, deferred=True)
        return {"applied": False, "reason": "deliberately deferred; reconsider after 15000 ticks", "deferred": True}
    fresh = collect(client, {"map": snapshot.get("map") or {}})  # Execution bypasses earlier-cycle research cache.
    if action == "progression_boardship":
        ids = ("map_id", "root_id", "pawn_id", "worker_id", "casket_id")
        candidate = next((r for r in boarding_options(fresh).values() if all(r.get(k) == selected.get(k) for k in ids)), None)
        readiness = ("pawn_downed", "reactor_running", "remaining_mobile_combat_colonists", "remaining_armed_mobile_combat_colonists", "remaining_mobile_doctors", "pawn_weapon", "psychic_bond_warning", "current_job", "colonists_at_home", "passengers")
        if candidate is None or any(candidate.get(k) != selected.get(k) for k in readiness):
            return {"applied": False, "reason": "boarding, pawn job or home readiness changed; new decision required"}
        try:
            response = client.post("/api/v1/colony/progression/board", query={**{k: candidate[k] for k in ids}, "confirmed": True})
            if response == "boarding_job_started":
                _record_cooldown(snapshot, map_state, action)
            return {"applied": response == "boarding_job_started", "reason": str(response), "boarding_complete": False}
        except Exception as exc:
            return {"applied": False, "reason": str(exc)}
    if action == "progression_ship":
        candidate = next((r for r in ship_options(fresh).values() if r.get("map_id") == selected.get("map_id") and r.get("root_id") == selected.get("root_id") and r.get("ship_action") == selected.get("ship_action")), None)
        if candidate is None:
            return {"applied": False, "reason": "ship conditions changed"}
        if any(candidate.get(k) != selected.get(k) for k in ("passengers", "colonists_at_home", "mobile_combat_colonists", "armed_mobile_combat_colonists", "downed_colonists", "hostile_pawns")):
            return {"applied": False, "reason": "passengers or defense readiness changed; new decision required"}
        try:
            response = client.post("/api/v1/colony/progression/ship", query={"map_id": candidate["map_id"], "root_id": candidate["root_id"], "action": candidate["ship_action"], "confirmed": True})
            if response in ("reactor_start_requested", "launch_countdown_started"):
                _record_cooldown(snapshot, map_state, action)
            return {"applied": response in ("reactor_start_requested", "launch_countdown_started"), "reason": str(response), "victory_verified": False}
        except Exception as exc:
            return {"applied": False, "reason": str(exc)}
    name = selected.get("name")
    if name not in _options(fresh):
        return {"applied": False, "reason": "project no longer feasible or already current"}
    try:
        response = client.post("/api/v1/research/target", query={"name": name, "force": False})
        if not isinstance(response, dict) or response.get("name") != name:
            return {"applied": False, "reason": "target not confirmed", "response": response}
        _record_cooldown(snapshot, map_state, action)
        return {"applied": True, "reason": "ordinary research target selected; progress still requires pawn work", "response": response}
    except Exception as exc:
        return {"applied": False, "reason": str(exc)}


def assess(action, snapshot):
    if action == "progression_boardship":
        return {"benefit": "One selected passenger begins ordinary ship boarding; downed pawns can be carried.", "cost": "Pawn/carrier travel and 500 ticks; passenger leaves colony labor until ejected.", "risk": "Losing a last doctor/defender or psychic bond separation; jobs can fail before boarding.", "inaction": "Retains care/defense/work but postpones escape or preservation of a downed pawn.", "uncertainty": "Job started does not prove casket occupied; engine rejects threats, unsafe path or reservations."}
    if action == "progression_ship":
        return {"benefit": "Escape advances through native reactor startup or boarded-passenger launch.", "cost": "Startup commits to roughly 15 days of defense; launch consumes the ship and removes passengers.", "risk": "Repeated threats during startup; unboarded colonists remain behind on launch.", "inaction": "Delay preserves labor and allows reserves/boarding, but postpones escape.", "uncertainty": "Defense quality, medicine, usable food and threat strength are not proven by counts; countdown is not verified credits."}
    return {"benefit": "Unlock feasible technologies and measured prerequisite steps.", "cost": "Researcher labor, bench power, advanced facility construction; points are remaining work.",
            "risk": "Diverting researchers can worsen food, care and defense; switching delays current unlocks.",
            "inaction": "Retains current project and labor flexibility but postpones missing technologies.",
            "uncertainty": "No reliable completion date without throughput; research completion alone never verifies victory."}
