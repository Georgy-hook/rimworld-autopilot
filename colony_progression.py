"""Measured progression; a doctrine is a preference, never proof of victory."""
from __future__ import annotations

from laya_decisions import ask_laya_choice
import colony_quests as quests
import colony_reasoning as reasoning
from colony_retry import recent as retry_recent, failure_record
from colony_affordances import interaction_identity

DESCRIPTIONS = {"progression_research": "Resolve native prerequisite or supporting infrastructure research for the chosen ending route, comparing alternatives and defer.",
                "progression_ship": "Compare ordinary ship reactor startup or launch against defer using actual engine blockers and survival facts.",
                "progression_boardship": "Choose one passenger/casket or downed-passenger carrier, preserving defenders and doctors; or defer."}
LABELS = {"progression_research": "Следующий шаг исследований", "progression_ship": "Реактор и запуск корабля", "progression_boardship": "Посадка пассажира в корабль"}
ACTIONS = set(DESCRIPTIONS)
DESCRIPTIONS["progression_ending"] = "Compare all native ending routes; accept an eligible offered quest or order a native ending site job. Resolve subsequent native choices explicitly; stop only on engine victory evidence."
LABELS["progression_ending"] = "Следующий шаг выбранного финала"
ACTIONS.add("progression_ending")
DOMAINS = {key: "strategy" for key in ACTIONS}
SHIP_RESEARCH = ("ShipBasics", "ShipCryptosleep", "ShipReactor", "ShipEngine", "ShipComputerCore", "ShipSensorCluster")
APPLIED_RETRY_TICKS = {"progression_research": 30000, "progression_ship": 15000, "progression_boardship": 600}
APPLIED_RETRY_TICKS["progression_ending"] = 600
ENDING_ROUTES = {
    "ship_journey": {"dlc": None, "prerequisites": "Travel by native caravan to the revealed escape ship, survive its native reactor startup, board passengers and launch.", "cost": "Travel supplies, lost home labor and reactor defense; people left at home remain.", "risk": "Caravan ambushes, starvation, illness and ship defense; arrival does not verify escape."},
    "ship_escape": {"dlc": None, "prerequisites": "Research and construct a connected ship, survive reactor startup, board chosen passengers and launch; alternatively travel to the offered landed ship.", "cost": "Research, advanced materials, construction, travel or 15 days of reactor defense; unboarded people remain.", "risk": "Repeated raids and loss of colony labor during boarding."},
    "royal_ascent": {"dlc": "royalty", "prerequisites": "Earn the native required Royal Ascent title (installed Count definition labeled archon), qualify for and accept Royal Ascent, host the stellarch successfully, then board the native departure shuttle.", "cost": "Honor, noble rooms and throne requirements, hospitality and defense for the visit.", "risk": "Guest death, mood or hospitality failure; repeated attacks."},
    "archonexus": {"dlc": "ideology", "prerequisites": "Reach each native wealth/research/faction requirement, accept three colony-sale cycles with explicit survivor and item selection, travel to the revealed core and invoke it.", "cost": "Three colony rebuilds; only the native selected pawns, animals and possessions transfer.", "risk": "Irreversible sale and separated colonists; final site defense."},
    "anomaly_void": {"dlc": "anomaly", "prerequisites": "Investigate monolith, discover the native required entity categories/counts, satisfy active-condition gates, survive void awakening, reach and resolve the final native choice. Study supports anomaly research and containment.", "cost": "Discovery, study and containment labor, stronger anomalies and final emergency.", "risk": "Entity escapes, darkness and assault; final embrace/disrupt choice has different consequences."},
    "odyssey_mechhive": {"dlc": "odyssey", "prerequisites": "Build and operate a gravship, progress offered gravship quests, obtain native space capability, travel to and resolve the mechhive objective.", "cost": "Gravship construction, fuel, travel, upgrades and orbital combat.", "risk": "Space hazards and mechanoid defenses; unavailable while Odyssey is inactive."},
}
PENDING_WINDOWS = ("Dialog_ChooseThingsForNewColony", "Dialog_ConfigureIdeo", "Screen_ArchonexusSettlementCinematics")


def canonical_route(route):
    return {"imperial_ascension": "royal_ascent", "mechhive": "odyssey_mechhive"}.get(route, route)


def option_route(row):
    """Native QuestScriptDef / site identity, independent of localized labels."""
    if row.get("kind") == "odyssey":
        return "odyssey_mechhive"
    route = canonical_route(row.get("route"))
    if route in ENDING_ROUTES:
        return route
    name = str(route or row.get("site") or "")
    if "RoyalAscent" in name:
        return "royal_ascent"
    if "Archonexus" in name:
        return "archonexus"
    if "Void" in name:
        return "anomaly_void"
    if any(word in name for word in ("Gravship", "Mechhive", "Cerebrex")):
        return "odyssey_mechhive"
    if "ShipEscape" in name:
        return "ship_journey"
    return None


def route_matches(chosen, row):
    chosen = canonical_route(chosen)
    # Resolve a native transaction already in progress, including cancel.
    # A new route requires an explicit doctrine change, not an unrelated menu.
    if row.get("kind") in {"selection", "continuation", "world-targeting"}:
        return True
    if not chosen:
        return True
    candidate = option_route(row)
    return candidate == chosen or {candidate, chosen} <= {"ship_escape", "ship_journey"}


def peek_pending(client):
    try:
        return client.get("/api/v1/colony/endings/pending") is True
    except Exception:
        return False


def pending_action(context):
    if (context.get("world_targeting") or {}).get("active"):
        return "progression_ending"
    odyssey = context.get("odyssey") or {}
    if odyssey.get("picking_destination") or odyssey.get("landing"):
        return "progression_ending"
    if (context.get("ending_selection") or {}).get("available"):
        return "progression_ending"
    continuation = context.get("ending_continuation") or {}
    if continuation.get("choosing_tile") or continuation.get("configuring_ideology"):
        return "progression_ending"
    return None


def pending_blocker(context):
    if pending_action(context) is None or ending_options(context):
        return None
    odyssey = context.get("odyssey") or {}
    return (odyssey.get("landing_blocker") or odyssey.get("destination_blocker")
            or "Native continuation has no currently feasible choices; await fresh native readiness")


def _protected_job(name):
    return name in {"TendPatient", "Rescue", "FeedPatient", "DoBill", "EnterCryptosleepCasket", "CarryToCryptosleepCasket"}


def _ending_unchanged(selected, row):
    """Bind real identities/costs while allowing normal observation drift."""
    kind = row.get("kind")
    if kind == "job" and _protected_job(row.get("current_job")):
        return False
    for key, value in row.items():
        if key == "expires_in_ticks":
            continue
        if kind == "accept" and key == "quest_offer":
            # Countdown/current-job drift is not a different offer. The native
            # version binds actual terms; execute still refreshes colony readiness.
            if (selected.get(key) or {}).get("offer_version") != (value or {}).get("offer_version"):
                return False
            continue
        if kind == "job" and key in {"current_job", "inspect"}:
            continue  # Native eligibility and protected-worker guards are regenerated.
        if kind == "journey":
            if key in {"label", "travelers", "home_food_nutrition", "mass", "capacity", "approximate_distance_tiles", "travel_estimate_reason"}:
                continue
            if key == "colonists_at_home" and "home_pawn_ids" in row:
                continue  # Stable roster IDs replace displayed names.
        previous = selected.get(key)
        if kind == "journey" and key in {"travel_days", "food_margin_days", "native_approx_food_days"} and isinstance(value, (int, float)) and isinstance(previous, (int, float)):
            if abs(value - previous) <= .25:
                continue
        if kind == "journey" and key == "daily_nutrition" and isinstance(value, (int, float)) and isinstance(previous, (int, float)) and abs(value - previous) <= .02:
            continue
        if previous != value:
            return False
    return True


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
    try:
        result["endings"] = client.get("/api/v1/colony/endings")
        result["victory_verified"] = result["endings"].get("victory_verified") is True
    except Exception as exc:
        result["errors"]["endings"] = str(exc)
    for key, suffix in (("ending_selection", "selection"), ("ending_continuation", "continuation"), ("odyssey", "odyssey"), ("world_targeting", "world-targeting")):
        try:
            result[key] = client.get("/api/v1/colony/endings/" + suffix)
        except Exception as exc:
            result["errors"][key] = str(exc)
    result["ending_routes"] = {name: {**row, "available": row["dlc"] is None or (result.get("endings") or {}).get(row["dlc"]) is True} for name, row in ENDING_ROUTES.items()}
    result["support_research"] = {route: research_frontier(result.get("research_tree"), targets) for route, targets in (result.get("endings") or {}).get("support_research_targets", {}).items()}
    map_id = (snapshot.get("map") or {}).get("id")
    if map_id is not None:
        result["native_milestones"] = [r for r in result.get("native_milestones") or [] if isinstance(r, dict) and str(r.get("map_id")) == str(map_id)]
        try:
            result["ending_journey"] = client.get("/api/v1/colony/endings/journey", map_id=map_id)
            journey = result["ending_journey"] or {}
            targets = journey.get("support_research_targets") or []
            for route in {r.get("route") for r in journey.get("readiness") or []}:
                if route in ("ship_journey", "archonexus") and targets:
                    result["support_research"][route] = research_frontier(result.get("research_tree"), targets)
        except Exception as exc:
            result["errors"]["ending_journey"] = str(exc)
    return result


def _raw_options(context):
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
                         "ending_support": name in ((context.get("chosen_route_support") or {}).get("frontier") or []),
                         "description": row.get("description") or "", "time": "Depends on assigned researchers, bench speed and interruptions; research points are work, not days."}
    return options


def prepare(snapshot, map_state):
    cooling = {action: _cooling(snapshot, map_state, action) for action in ACTIONS}
    context = snapshot.setdefault("development", {}).setdefault("progression", {})
    if context.get("victory_verified") is True or (context.get("endings") or {}).get("victory_verified") is True:
        return []
    import colony_sessions
    context["_transition_memory"] = colony_sessions.transition_memory(map_state, "progression_transitions", snapshot)
    context["_interaction_pending"] = map_state.setdefault("interaction_pending", {})
    context["_game_tick"] = int((snapshot.get("game") or {}).get("tick") or 0)
    context["options"] = _options(context)
    doctrine = (map_state or {}).get("doctrine") or snapshot.get("development", {}).get("doctrine") or {}
    chosen_route = canonical_route(doctrine.get("endgame") or doctrine.get("ending_route")
                                   or map_state.get("ending_commitment"))
    context["chosen_ending_route"] = chosen_route
    context["chosen_route_support"] = (context.get("support_research") or {}).get(chosen_route) or {}
    support_frontier = set(context["chosen_route_support"].get("frontier") or [])
    for name, row in context["options"].items():
        row["ending_support"] = name in support_frontier
    pursuing_ship = chosen_route == "ship_escape" or (not chosen_route and (
        doctrine.get("primary_direction") == "research_starflight" or doctrine.get("technology") == "starflight"))
    # Only add a decision when the route exposes an actionable prerequisite.
    # Ordinary research selection already belongs to the director.
    actions = ["progression_research"] if (pursuing_ship and any(r["ship_prerequisite"] for r in context["options"].values())) or any(r.get("ending_support") for r in context["options"].values()) else []
    if ship_options(context):
        actions.append("progression_ship")
    if boarding_options(context):
        actions.append("progression_boardship")
    if ending_options(context):
        actions.append("progression_ending")
    return [action for action in actions if not cooling[action] or pending_action(context) == action]


def _ending_options(context):
    native = context.get("endings") or {}
    if native.get("victory_verified"):
        return {}
    options = {}
    world_target = context.get("world_targeting") or {}
    if world_target.get("active"):
        options = {f"world_{index}": {**row, "kind": "world-targeting", "session": world_target.get("session")} for index, row in enumerate(world_target.get("options") or [])}
        options["cancel_world_target"] = {"kind": "world-targeting", "operation": "cancel", "session": world_target.get("session"), "label": "Cancel world target selection"}
        return options
    odyssey = context.get("odyssey") or {}
    if odyssey.get("picking_destination") or odyssey.get("landing"):
        rows = odyssey.get("destinations") or [] if odyssey.get("picking_destination") else odyssey.get("landings") or []
        return {f"odyssey_{index}": {**row, "kind": "odyssey", "session": (odyssey.get("destination_session") if odyssey.get("picking_destination") else odyssey.get("landing_session"))} for index, row in enumerate(rows)}
    continuation = context.get("ending_continuation") or {}
    if continuation.get("choosing_tile"):
        return {f"settle_{r['tile_id']}": {**r, "kind": "continuation", "operation": "tile", "label": f"Settle tile {r['tile_id']}"} for r in continuation.get("tiles") or []}
    if continuation.get("configuring_ideology"):
        return {f"ideology_{r['id']}": {**r, "kind": "continuation", "operation": "ideology", "ideology_id": r["id"]} for r in continuation.get("ideologies") or []}
    selection = context.get("ending_selection") or {}
    if selection.get("available"):
        options["cancel_transfer"] = {"kind": "selection", "operation": "cancel", "label": "Cancel colony sale and keep colony"}
        for row in selection.get("rows") or []:
            options[f"transfer_{row['thing_id']}"] = {**row, "kind": "selection", "operation": "select", "selected": not row.get("selected"),
                "label": ("Leave behind " if row.get("selected") else "Take ") + row["label"], "consequence": selection.get("consequence")}
        if selection.get("can_submit"):
            options["submit_transfer"] = {"kind": "selection", "operation": "submit", "label": "Review and confirm colony sale", "selection": selection}
        return options
    for quest in native.get("quests") or []:
        if quest.get("can_accept") is not True:
            continue
        pawns = quest.get("accepter_ids") or [] if quest.get("requires_accepter") else [0]
        for pawn_id in pawns:
            options[f"quest_{quest['quest_id']}_{pawn_id}"] = {**quest, "kind": "accept", "pawn_id": pawn_id}
    for job in native.get("site_jobs") or []:
        key = f"job_{job['map_id']}_{job['thing_id']}_{job['pawn_id']}_{job['label']}"
        options[key] = {**job, "kind": "job"}
    for index, row in enumerate(odyssey.get("launches") or []):
        options[f"odyssey_pilot_{index}"] = {**row, "kind": "odyssey"}
    for row in (context.get("ending_journey") or {}).get("journeys") or []:
        key = f"journey_{row['map_id']}_{row['object_id']}_{row['team']}_{row['supply_days']}"
        options[key] = {**row, "kind": "journey"}
    return options



def _transition_row(row):
    import colony_sessions
    observation = dict(row)
    for field in ('expires_in_ticks', 'remaining_points', 'progress', 'inspect', 'description'):
        observation.pop(field, None)
    if row.get('kind') == 'accept' and isinstance(observation.get('quest_offer'), dict):
        observation['quest_offer'] = observation['quest_offer'].get('offer_version')
    observation.pop('quest_plan', None)
    if row.get('kind') == 'journey':
        for field in ('label', 'travelers', 'home_food_nutrition', 'mass', 'capacity', 'approximate_distance_tiles',
                      'travel_estimate_reason', 'travel_days', 'food_margin_days', 'native_approx_food_days', 'daily_nutrition'):
            observation.pop(field, None)
        if 'home_pawn_ids' in row: observation.pop('colonists_at_home', None)
    return colony_sessions.transition_signature(observation)


def ending_options(context):
    import colony_sessions
    rows = _ending_options(context)
    memory = context.get('_transition_memory') or {}
    pending = context.get('_interaction_pending') or {}
    tick = int(context.get('_game_tick') or 0)
    pending_transaction = pending_action(context) is not None
    return {key: row for key, row in rows.items() if (pending_transaction or route_matches(context.get('chosen_ending_route'), row)) and not (
        row.get('kind') == 'job' and retry_recent(pending.get(_interaction_key(row)), tick, 30000))
        and not colony_sessions.transition_wait(memory, 'progression_ending:' + _transition_row(row), _transition_row(row))}


def _interaction_key(row):
    return interaction_identity({"kind": "menu", "target_id": row.get("thing_id"), "label": row.get("label")})


def journey_summary(context):
    route = context.get("chosen_ending_route")
    native = context.get("ending_journey") or {}
    rows = [r for r in native.get("readiness") or [] if r.get("route") == route]
    if not rows:
        return {}
    aliases = {"insufficient food edible and policy-allowed for every traveler": "diet-allowed survival meals missing",
               "home travel-food reserve below 30 nutrition": "home ration reserve missing",
               "insufficient travel medicine": "travel medicine missing", "home medicine reserve below eight": "home medicine reserve missing"}
    blockers = list(dict.fromkeys(aliases.get(b, b) for r in rows for b in r.get("blockers") or []))
    skills = list(dict.fromkeys(f"{s.get('skill')}{s.get('minimum')}" for r in native.get("ration_production") or [] for s in r.get("skill_requirements") or []))
    stations = list(dict.fromkeys(s for r in native.get("ration_production") or [] for s in r.get("stations") or []))
    return {"route": route, "blockers": blockers[:4], "ration_work": ",".join(skills + stations[:2]),
            "travel_days": [r.get("travel_days") for r in rows[:2]],
            "stock_food_margin_days": [r.get("stock_food_margin_days") for r in rows[:2]],
            "research": native.get("support_research_targets") or [], "destinations": len({r.get("object_id") for r in rows})}


def summary(snapshot):
    context = dict((snapshot.get("development") or {}).get("progression") or {})
    if not context.get("chosen_ending_route"):
        context["chosen_ending_route"] = ((snapshot.get("development") or {}).get("doctrine") or {}).get("endgame")
    ready = journey_summary(context)
    return {"journey_blockers": len(ready.get("blockers") or []), "journey_needs": ready} if ready else {}


def _rawboarding_options(context):
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


def _rawship_options(context):
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
    if action == "progression_ending":
        candidates = ending_options(context)
        effects = {key: {"benefit": f"Native ending step: {r.get('label')}; {r.get('description') or r.get('inspect') or ''}",
                         "risk": "Ending escalation, colony sale or departure may be irreversible; compare route prerequisites and defense before accepting.",
                         "cost": "Pawn time, quest commitments and route-specific requirements.", "inaction": "Keep preparations; offered quest may expire.",
                         "uncertainty": "Native action requested does not prove completion; jobs and later choices remain."} for key, r in candidates.items()}
        facts = {"journey_needs": journey_summary(context), "ending_routes": context.get("ending_routes") or ENDING_ROUTES, "native_quests": (context.get("endings") or {}).get("quests"), "native_site_blockers": (context.get("endings") or {}).get("site_blockers"), "sale_selection": context.get("ending_selection"), "sale_continuation": context.get("ending_continuation"),
                 "final_choices": "Choose every native confirmation, survivor/item transfer and final embrace/disrupt choice explicitly. Never auto-dismiss ending dialogs."}
        defer = {"benefit": "Prepare colony and compare ending alternatives.", "risk": "Expiry or longer exposure to threats.", "cost": "Time.", "inaction": "No ending step begins.", "uncertainty": "No victory inferred."}
    elif action == "progression_boardship":
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
        effects = {name: {"benefit": f"{r['label']}; unlocks {r['unlocks']}; ship prerequisite {r['ship_prerequisite']}; chosen-route infrastructure support {r['ending_support']}.",
                          "risk": "Research labor competes with survival; switching delays the current unlock.",
                          "cost": f"{r['remaining_points']} remaining research points, researcher time and bench power.",
                          "inaction": "Keep current project; selected technology remains unavailable.",
                          "uncertainty": "Points measure work, not days; no victory inferred from research."} for name, r in candidates.items()}
        facts = {"journey_needs": journey_summary(context), "current_project": (context.get('current') or {}).get('name'), "chosen_ending_route": context.get("chosen_ending_route"),
                 "route_gate_note": (context.get("endings") or {}).get("research_gate_note"), "time": "Research points are work, not completion days."}
        defer = {"benefit": "Keep current research and labor flexibility.", "risk": "Missing technology unlocks delayed.", "cost": "No target change; current work continues.",
                 "inaction": "Prerequisite frontier remains unresolved.", "uncertainty": "Current project may still require staff, power and inputs."}
    choices = {key: f"{r.get('label') or r.get('pawn') or r.get('ship_action') or key}; {effects[key]['benefit']}" for key, r in candidates.items()}
    choices['defer'] = 'Keep current work; defer this commitment.'
    effects['defer'] = defer
    return candidates, choices, effects, facts


def choose(agent, state, action, snapshot):
    context = snapshot.get('development', {}).get('progression', {})
    candidates, choices, effects, facts = comparison(action, context)
    if action == "progression_ending" and not candidates:
        return {"blocked": True, "reason": pending_blocker(context) or "No live ending choices"}, {"reason": "no_live_ending_choices"}
    first = None
    if action == "progression_ending":
        def group(row):
            if row.get("kind") == "odyssey":
                return "odyssey_mechhive"
            if row.get("kind") == "world-targeting":
                return row.get("operation")
            if row.get("kind") == "selection":
                return row.get("category") or row.get("operation")
            if row.get("kind") == "continuation":
                return row.get("operation")
            return option_route(row) or "unknown_native_route"
        target_rows = {group(row): row for row in candidates.values()}
        target_choices = {key: (key + ": " + str(row.get("label") or row.get("site") or "native route")) for key, row in target_rows.items()}
        pending = pending_action(context) == action
        if not pending:
            target_choices["defer"] = "Prepare and compare ending routes later."
        target_effects = {}
        for key in target_choices:
            catalog = ENDING_ROUTES.get("royal_ascent" if key == "imperial_ascension" else key) or {}
            target_effects[key] = {"benefit": catalog.get("prerequisites") or target_choices[key], "cost": catalog.get("cost") or "Native transfer/configuration choice.",
                "risk": catalog.get("risk") or "Colony sale leaves unselected people and possessions behind; site and ideology change colony conditions.", "inaction": "No route step begins.", "uncertainty": "Only actual engine credits verify completion."}
        target, first = ask_laya_choice(agent, {**state, "option_effects": target_effects, "decision_facts": {"journey_needs": journey_summary(context), "chosen_ending_route": context.get("chosen_ending_route"), "available_routes": [r for r, info in (context.get("ending_routes") or {}).items() if info.get("available")]}}, action + "_route",
                                       "Choose a native ending route or pending configuration category; compare alternatives.", target_choices, detailed=True)
        if target == "defer":
            return {"defer": True}, first
        candidates = {key: row for key, row in candidates.items() if group(row) == target}
        choices = {key: choices[key] for key in candidates}
        effects = {key: effects[key] for key in candidates}
        for key, row in candidates.items():
            if row.get("kind") == "journey":
                effects[key]["benefit"] = f"Native travel estimate {row.get('travel_days')} days; {row.get('label')}; travelers {row.get('travelers')}; distance {row.get('approximate_distance_tiles')} tiles."
                effects[key]["cost"] = f"Packed nutrition {row.get('food_nutrition')}; native daily need {row.get('daily_nutrition')}; native approximate food days {row.get('native_approx_food_days')}; medicine {row.get('medicine_count')}; mass {row.get('mass')} / {row.get('capacity')} capacity."
                effects[key]["risk"] = f"Food margin {row.get('food_margin_days')} days against native ETA; people left at home {row.get('colonists_at_home')}; reserved travel nutrition {row.get('home_food_nutrition')}. Caravan ambushes, illness and absent labor."
                effects[key]["uncertainty"] = row.get("travel_estimate_reason") or (context.get("ending_journey") or {}).get("warning") or "Formation and arrival require observation; arrival never proves victory."
            elif row.get("kind") == "odyssey":
                effects[key]["benefit"] = f"{row.get('label')}; fuel {row.get('fuel')}; destination fuel cost {row.get('fuel_cost')}; distance {row.get('distance')}; biome {row.get('biome')}; layer {row.get('layer_id')}."
                effects[key]["risk"] = f"Outside ship {row.get('colonists_outside_ship')}; orbital warnings {row.get('orbital_warnings')}; landing footprint may displace obstacles. Boarding/fuel/travel never prove mechhive resolution."
            elif row.get("kind") == "world-targeting":
                effects[key]["benefit"] = f"{row.get('label')}; native target information: {row.get('native_info')}."
                effects[key]["risk"] = "Travel or world ability can separate people and consume resources; native callback can reject or open another choice."
            elif row.get("operation") == "tile":
                tile = row.get("facts") or {}
                effects[key]["benefit"] = f"Settle tile {row['tile_id']}: biome {tile.get('biome')}, temperature {tile.get('temperature')}, hills {tile.get('hilliness')}, rivers {tile.get('rivers')}, pollution {tile.get('pollution')}."
                effects[key]["risk"] = "Selected climate, terrain and pollution affect food, shelter and travel; a valid tile does not prove a safe colony."
            elif row.get("operation") == "select":
                effects[key]["benefit"] = f"{row['label']}; {row.get('category')}; transfer quantity {row.get('quantity')}."
                effects[key]["risk"] = f"{'Take' if row.get('selected') else 'Leave behind'} this {row.get('category')} in the colony sale; every unselected person, animal and item is abandoned."
            elif row.get("operation") == "ideology":
                effects[key]["benefit"] = f"Choose {row.get('label')}; memes {row.get('memes')}."
                effects[key]["risk"] = "Changing primary ideology changes beliefs and roles; current ideology is also an explicit alternative."
            elif row.get("kind") == "job":
                effects[key]["risk"] = f"{row.get('pawn')} leaves {row.get('current_job')}; {row.get('hostile_pawns')} enemies present. Final invocation/escalation can be irreversible."
            elif row.get("operation") == "submit":
                selected_rows = [r.get("label") for r in (row.get("selection") or {}).get("rows") or [] if r.get("selected")]
                effects[key]["risk"] = f"Sell colony; keep {selected_rows}; abandon all others. Opens native consequence confirmation."
        facts = {"journey_needs": journey_summary(context), "stage": target, "native_blockers": (context.get("ending_selection") or {}).get("blocker")}
        facts["care_risks"] = reasoning.attention_facts(snapshot).get("care_risks")
        facts["quest_colony"] = {**quests.colony_facts(snapshot), "ending": context.get("chosen_ending_route")}
        if not pending:
            choices["defer"] = "Prepare before committing this route step."
            effects["defer"] = {"benefit": "Preserve colony work.", "cost": "Time.", "risk": "Offer may expire.", "inaction": "Route step postponed.", "uncertainty": "Readiness may change."}
    selected, raw = ask_laya_choice(agent, {**state, 'option_effects': effects, 'decision_facts': facts}, action,
                                    'Choose an ordinary progression step or defer; compare benefit, risk, cost, delay and uncertainty.', choices, detailed=True)
    if first is not None:
        raw["ending_route_choice"] = first
    candidate = {'defer': True} if selected == 'defer' else candidates[selected]
    if candidate.get("kind") == "accept":
        choice, review, plan = quests.review(agent, candidate.get("quest_offer") or {}, snapshot,
            {"chosen_ending_route": context.get("chosen_ending_route")})
        raw["quest_review"] = review
        if choice != "accept":
            return {"defer": True}, raw
        candidate = {**candidate, "pawn_id": plan.get("accepter_pawn_id") or 0, "quest_plan": plan}
    return candidate, raw


def _execute(client, snapshot, map_state, action, selected):
    if action not in ACTIONS:
        return {"applied": False, "reason": "deferred or unsupported action"}
    if selected.get("blocked"):
        return {"applied": False, "blocked": True, "reason": selected.get("reason") or "Native choices unavailable"}
    if selected.get("defer"):
        _record_cooldown(snapshot, map_state, action, deferred=True)
        return {"applied": False, "reason": "deliberately deferred; reconsider after 15000 ticks", "deferred": True}
    fresh = collect(client, {"map": snapshot.get("map") or {}})  # Execution bypasses earlier-cycle research cache.
    doctrine = map_state.get("doctrine") or (snapshot.get("development") or {}).get("doctrine") or {}
    fresh["chosen_ending_route"] = canonical_route(doctrine.get("endgame") or doctrine.get("ending_route")
                                                   or map_state.get("ending_commitment"))
    if fresh.get("victory_verified") is True:
        return {"applied": False, "reason": "native victory already verified", "victory_verified": True}
    if action == "progression_ending":
        # Quest expiry counts down during deliberation. Native eligibility is freshly
        # regenerated, so elapsed ticks alone must not invalidate the chosen offer.
        # Bind semantic identity, cost and readiness; tolerate ordinary observation drift.
        candidate = next((r for r in ending_options(fresh).values() if _ending_unchanged(selected, r)), None)
        if candidate is None:
            return {"applied": False, "reason": "ending requirements, option or pawn job changed; new decision required"}
        try:
            if candidate["kind"] == "job" and retry_recent(
                (map_state.get("interaction_pending") or {}).get(_interaction_key(candidate)),
                int((snapshot.get("game") or {}).get("tick") or 0), 30000):
                return {"applied": False, "reason": "interaction_awaiting_observed_result"}
            if candidate["kind"] == "accept":
                import rimworld_laya as bridge
                result = quests.accept_reviewed(client, selected.get("quest_plan"), bridge.collect_snapshot(client))
                if result.get("applied"):
                    _record_cooldown(snapshot, map_state, action)
                return {**result, "victory_verified": False}
            if candidate["kind"] == "journey":
                fields = ("map_id", "object_id", "team", "supply_days")
            elif candidate["kind"] in ("odyssey", "world-targeting"):
                fields = tuple(k for k in ("operation", "map_id", "thing_id", "pawn_id", "label", "tile_id", "layer_id", "session", "object_id", "x", "z", "rotation") if k in candidate)
            else:
                fields = ("operation", "tile_id" if candidate["operation"] == "tile" else "ideology_id") if candidate["kind"] == "continuation" else (("operation", "thing_id", "selected") if candidate.get("operation") == "select" else ("operation",)) if candidate["kind"] == "selection" else ("quest_id", "pawn_id") if candidate["kind"] == "accept" else ("map_id", "thing_id", "pawn_id", "label")
            query = {**{k: candidate[k] for k in fields}, "confirmed": True}
            if candidate["kind"] == "journey":
                query["pawn_ids"] = ",".join(str(n) for n in candidate["pawn_ids"])
                query["home_pawn_ids"] = ",".join(str(n) for n in sorted(candidate.get("home_pawn_ids") or []))
                query["manifest"] = ",".join(f"{r['def_name']}:{r['count']}" for r in sorted(candidate.get("manifest") or [], key=lambda r: r["def_name"]))
            response = client.post("/api/v1/colony/endings/" + candidate["kind"], query=query)
            applied = response in ("ending_caravan_forming", "ending_quest_accepted", "ending_native_action_requested", "sale_confirmation_opened", "sale_selection_updated", "sale_cancelled", "settlement_tile_chosen", "ideology_continuation_requested", "gravship_pilot_job_requested", "gravship_destination_chosen", "gravship_destination_cancelled", "gravship_landing_marker_placed", "gravship_landing_requested", "gravship_landing_map_selected", "world_target_chosen", "world_target_cancelled")
            if applied and candidate["kind"] == "job":
                map_state.setdefault("interaction_pending", {})[_interaction_key(candidate)] = failure_record(
                    int((snapshot.get("game") or {}).get("tick") or 0), seconds=120)
            if applied and candidate["kind"] not in ("selection", "continuation", "odyssey", "world-targeting"):
                _record_cooldown(snapshot, map_state, action)
            return {"applied": applied, "reason": str(response), "victory_verified": False, "native_choices_required": True}
        except Exception as exc:
            return {"applied": False, "reason": str(exc)}
    if action == "progression_boardship":
        ids = ("map_id", "root_id", "pawn_id", "worker_id", "casket_id")
        candidate = next((r for r in boarding_options(fresh).values() if all(r.get(k) == selected.get(k) for k in ids)), None)
        readiness = ("pawn_downed", "reactor_running", "remaining_mobile_combat_colonists", "remaining_armed_mobile_combat_colonists", "remaining_mobile_doctors", "pawn_weapon", "psychic_bond_warning", "colonists_at_home", "passengers")
        if candidate is None or _protected_job(candidate.get("current_job")) or any(candidate.get(k) != selected.get(k) for k in readiness):
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
    if action == "progression_ending":
        return {"benefit": "Advance the model-selected native DLC ending route.", "cost": "Route-specific honor, wealth, study, construction, travel and colony commitments.",
                "risk": "Irreversible sales, departures and escalating threats; final native choices require explicit decisions.", "inaction": "Prepare or choose another feasible ending route.",
                "uncertainty": "Only engine victory credits verify an ending; quest acceptance and countdown never do."}
    if action == "progression_boardship":
        return {"benefit": "One selected passenger begins ordinary ship boarding; downed pawns can be carried.", "cost": "Pawn/carrier travel and 500 ticks; passenger leaves colony labor until ejected.", "risk": "Losing a last doctor/defender or psychic bond separation; jobs can fail before boarding.", "inaction": "Retains care/defense/work but postpones escape or preservation of a downed pawn.", "uncertainty": "Job started does not prove casket occupied; engine rejects threats, unsafe path or reservations."}
    if action == "progression_ship":
        return {"benefit": "Escape advances through native reactor startup or boarded-passenger launch.", "cost": "Startup commits to roughly 15 days of defense; launch consumes the ship and removes passengers.", "risk": "Repeated threats during startup; unboarded colonists remain behind on launch.", "inaction": "Delay preserves labor and allows reserves/boarding, but postpones escape.", "uncertainty": "Defense quality, medicine, usable food and threat strength are not proven by counts; countdown is not verified credits."}
    return {"benefit": "Unlock feasible technologies and measured prerequisite steps.", "cost": "Researcher labor, bench power, advanced facility construction; points are remaining work.",
            "risk": "Diverting researchers can worsen food, care and defense; switching delays current unlocks.",
            "inaction": "Retains current project and labor flexibility but postpones missing technologies.",
            "uncertainty": "No reliable completion date without throughput; research completion alone never verifies victory."}


def execute(client, snapshot, map_state, action, selected):
    import colony_sessions
    if selected.get('defer') or selected.get('blocked'):
        return _execute(client, snapshot, map_state, action, selected)
    readiness = _transition_row(selected)
    key = action + ':' + readiness
    memory = colony_sessions.transition_memory(map_state, 'progression_transitions', snapshot)
    if colony_sessions.transition_wait(memory, key, readiness):
        return {'applied': False, 'reason': 'native_transition_awaiting_observation'}
    try:
        result = _execute(client, snapshot, map_state, action, selected)
    except Exception:
        colony_sessions.transition_record(memory, key, readiness, {'applied': False, 'reason': 'network_outcome_unknown'})
        raise
    colony_sessions.transition_record(memory, key, readiness, result)
    if result.get('applied'):
        route = option_route(selected) if action == 'progression_ending' else 'ship_escape' if action in {
            'progression_ship', 'progression_boardship'} else None
        if route:
            map_state['ending_commitment'] = route
    return result


def _filter_transitions(context, action, rows):
    import colony_sessions
    memory = context.get('_transition_memory') or {}
    return {key: row for key, row in rows.items() if not colony_sessions.transition_wait(memory, action + ':' + _transition_row(row), _transition_row(row))}


def _options(context):
    return _filter_transitions(context, 'progression_research', _raw_options(context))


def boarding_options(context):
    if context.get('chosen_ending_route') and canonical_route(context['chosen_ending_route']) not in {'ship_escape', 'ship_journey'}:
        return {}
    return _filter_transitions(context, 'progression_boardship', _rawboarding_options(context))


def ship_options(context):
    if context.get('chosen_ending_route') and canonical_route(context['chosen_ending_route']) not in {'ship_escape', 'ship_journey'}:
        return {}
    return _filter_transitions(context, 'progression_ship', _rawship_options(context))
