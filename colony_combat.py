from __future__ import annotations

from typing import Any


def _cell(row: dict[str, Any] | None) -> tuple[float, float] | None:
    position = (row or {}).get("position") or {}
    if position.get("x") is None or position.get("z") is None:
        return None
    return float(position["x"]), float(position["z"])


def live_hostiles(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in (snapshot.get("combat") or {}).get("hostiles") or []
            if not row.get("is_dead") and not row.get("is_downed")]


def protected_emergency_care_ids(snapshot: dict[str, Any]) -> set[int]:
    """Do not cancel an active tend job for a distant combat order."""
    colonists = (snapshot.get("combat") or {}).get("colonists") or []
    untreated_patients = {int(row["id"]) for row in colonists
                          if row.get("id") is not None and not row.get("is_dead")
                          and row.get("tendable_now")}
    return {int(row["id"]) for row in colonists
            if row.get("id") is not None and not row.get("is_dead") and not row.get("is_downed")
            and str(row.get("current_job") or "").lower() == "tendpatient"
            and row.get("current_job_target_id") is not None
            and int(row["current_job_target_id"]) in untreated_patients
            and float(row.get("distance_to_nearest_opponent") or 9999) > 4}


def threat_radius(hostile: dict[str, Any]) -> float:
    """Keep ordinary errands outside a hostile's reach and a hive's guard area."""
    radius = max(22.0, min(55.0, float(hostile.get("weapon_range") or 0) + 8.0))
    if "defendandexpandhive" in str(hostile.get("lord_job_type") or "").lower() \
            and hostile_is_preparing(hostile):
        # A passive hive should not make the colony's food store unusable
        # while still denying pickup of guns and jelly in its defended area.
        return 20.0
    return radius


def errand_exposed(snapshot: dict[str, Any], destination: dict[str, Any] | None,
                   origin: dict[str, Any] | None = None) -> bool:
    """Reject a pickup, harvest or haul when its target or direct route meets a live threat.

    RimWorld may choose a longer path around terrain, so this is a conservative
    feasibility check, not proof that a route is safe. Missing coordinates also
    cannot justify ordering a civilian into an active threat.
    """
    hostiles = live_hostiles(snapshot)
    if not hostiles:
        return False
    target = _cell({"position": destination})
    start = _cell({"position": origin}) if origin is not None else None
    if target is None or (origin is not None and start is None):
        return True
    for hostile in hostiles:
        enemy = _cell(hostile)
        if enemy is None:
            return True
        radius_squared = threat_radius(hostile) ** 2
        if (target[0] - enemy[0]) ** 2 + (target[1] - enemy[1]) ** 2 <= radius_squared:
            return True
        if start is None:
            continue
        dx, dz = target[0] - start[0], target[1] - start[1]
        fraction = max(0.0, min(1.0, ((enemy[0] - start[0]) * dx
                                       + (enemy[1] - start[1]) * dz) / max(1.0, dx * dx + dz * dz)))
        closest = (start[0] + fraction * dx, start[1] + fraction * dz)
        if (closest[0] - enemy[0]) ** 2 + (closest[1] - enemy[1]) ** 2 <= radius_squared:
            return True
    return False


# These are strategic templates, not scripts with fixed coordinates.  RIMAPI
# resolves positions against the live map and rejects every route that crosses
# a friendly trap.  Keeping the catalogue here lets the model compare tactics
# without making the low-level safety code part of its prompt.
TACTICS: dict[str, dict[str, Any]] = {
    "hold_cover": {
        "label": "Hold strong cover",
        "description": "Use nearby walls, barricades, sandbags or shelves and make the enemy cross open ground.",
        "tags": {"general", "ranged", "defense"},
    },
    "focus_fire": {
        "label": "Concentrated fire",
        "description": "All safe shooters attack one high-priority target, reducing enemy damage quickly instead of spreading wounds.",
        "tags": {"general", "ranged"},
    },
    "civilian_retreat": {
        "label": "Withdraw unarmed civilians",
        "description": "Move mobile unarmed colonists away from the nearest hostile along a trap-free path instead of standing still or charging into melee.",
        "tags": {"unarmed", "fallback", "defense"},
    },
    "firing_line": {
        "label": "Safe firing line",
        "description": "Form a spaced line behind cover; adjacent shooters remain inside the short friendly-fire-safe envelope.",
        "tags": {"general", "ranged", "defense"},
    },
    "spread_out": {
        "label": "Disperse against explosives",
        "description": "Keep several cells between fighters to limit rockets, grenades, fire and area psycasts.",
        "tags": {"explosive", "siege", "drop_pod", "mechanoid"},
    },
    "kite": {
        "label": "Kite slow melee enemies",
        "description": "A fast ranged pawn draws pursuit while the firing group shoots; retreat paths must contain no friendly traps.",
        "tags": {"melee_enemy", "animal", "insect", "open_field"},
    },
    "backstep_fire": {
        "label": "Backstep and fire",
        "description": "Mobile shooters take short trap-free steps away from adjacent melee enemies, then fire again without leaving pursuit distance.",
        "tags": {"melee_enemy", "insect", "animal", "ranged"},
    },
    "screen_melee": {
        "label": "Melee screen for shooters",
        "description": "A capable but potentially exposed melee fighter intercepts the closest enemy while supporting shooters concentrate fire.",
        "tags": {"melee_enemy", "insect", "animal", "close_quarters"},
    },
    "melee_assault": {
        "label": "Coordinated melee assault",
        "description": "All mobile armed melee fighters attack together instead of retreating one by one. Closing across open ground can be deadly against guns or stronger enemies; any allied shooters provide covering fire.",
        "tags": {"melee_enemy", "ranged_enemy", "close_quarters", "assault"},
    },
    "melee_hold_line": {
        "label": "Hold a melee group",
        "description": "Gather sword fighters into one nearby group and intercept enemies when they close. This avoids a risky long charge but gives ranged enemies time to shoot and drafted fighters cannot rest or eat.",
        "tags": {"melee_enemy", "defense", "close_quarters"},
    },
    "coordinate_melee_roles": {
        "label": "Assign individual melee roles",
        "description": "Choose each armed melee fighter's role separately: attack, guard, lure, or withdraw. They receive orders in one cycle, so one can draw pursuit while others attack or cover the shooters.",
        "tags": {"melee_enemy", "close_quarters", "general"},
    },
    "advance_to_range": {
        "label": "Bring guns into range",
        "description": "Out-of-range shooters move in short trap-free steps while those already in range keep shooting. Advancing may expose the group.",
        "tags": {"ranged", "assault", "mechanoid", "insect"},
    },
    "withdraw_and_regroup": {
        "label": "Withdraw and regroup",
        "description": "Move the selected mobile fighters beyond immediate enemy reach along trap-free routes; this stops their fire temporarily and enemies may pursue. Once at safe distance, choose a new tactic rather than repeating withdrawal.",
        "tags": {"fallback", "ranged", "melee_enemy", "mechanoid"},
    },
    "staggered_retreat": {
        "label": "Staggered retreat",
        "description": "One element moves to the fallback line while the other covers, preventing a simultaneous rout.",
        "tags": {"general", "fallback", "ranged"},
    },
    "melee_block": {
        "label": "Three-on-one melee block",
        "description": "Hold a one-cell doorway or choke with up to three armored melee pawns and shoot over them from directly behind.",
        "tags": {"melee_enemy", "insect", "animal", "choke"},
    },
    "door_defense": {
        "label": "Doorway defense",
        "description": "Use an owned doorway as a controlled choke with short retreat access to the hospital and inner base.",
        "tags": {"melee_enemy", "drop_pod", "breach", "defense"},
    },
    "killbox_hold": {
        "label": "Hold the prepared kill zone",
        "description": "Occupy the colony's actual funnel and firing positions instead of chasing enemies outside it.",
        "tags": {"assault", "killbox", "defense"},
    },
    "fallback_line": {
        "label": "Withdraw to internal defenses",
        "description": "Use the verified inner firing line when breachers, drop pods or insects bypass the outer defenses.",
        "tags": {"breach", "drop_pod", "insect", "fallback"},
    },
    "wide_flank": {
        "label": "Wide flanking arc",
        "description": "Split healthy shooters between the main position and a safe side angle to negate one-direction cover.",
        "tags": {"siege", "staging", "ranged", "open_field"},
    },
    "pincer": {
        "label": "Two-sided pincer",
        "description": "Use two mutually supporting groups against a static or cover-dependent enemy; never isolate a single pawn.",
        "tags": {"siege", "staging", "cluster", "ranged"},
    },
    "counter_snipe": {
        "label": "Counter-snipe",
        "description": "Only long-range shooters expose themselves; everyone else remains behind cover or in reserve.",
        "tags": {"siege", "sniper", "staging"},
    },
    "rush_ranged": {
        "label": "Melee rush on ranged threats",
        "description": "Armored, mobile melee fighters close on isolated gunners so those enemies cannot continue firing.",
        "tags": {"ranged_enemy", "close_quarters"},
    },
    "emp_control": {
        "label": "EMP control",
        "description": "Stun mechanoids or shields with a verified EMP weapon while conventional fire focuses one disabled target.",
        "tags": {"mechanoid", "shield"},
    },
    "smoke_advance": {
        "label": "Smoke-covered advance",
        "description": "Advance under smoke against turrets or static guns, with melee and short-range weapons protected by the screen.",
        "tags": {"turret", "cluster", "siege"},
    },
    "siege_harass": {
        "label": "Hit-and-run against a siege",
        "description": "Long-range mobile shooters fire from maximum range and withdraw before the preparing enemy can answer.",
        "tags": {"siege", "staging", "open_field"},
    },
    "mortar_counterbattery": {
        "label": "Mortar counter-battery",
        "description": "Use completed, supplied mortars from the protected mortar post instead of crossing the map on foot.",
        "tags": {"siege", "cluster", "mortar"},
    },
    "drop_pod_encircle": {
        "label": "Encircle drop pods",
        "description": "Evacuate civilians, spread armed pawns around the landing room and attack from multiple doors after pods open.",
        "tags": {"drop_pod", "close_quarters"},
    },
    "infestation_choke": {
        "label": "Contain an infestation at a choke",
        "description": "Do not enter the hive room piecemeal; block its exit and concentrate short-range fire behind armored melee.",
        "tags": {"insect", "choke"},
    },
    "infestation_burn": {
        "label": "Controlled infestation burn",
        "description": "Only burn a sealed stone compartment after checking escape routes, temperature exposure and valuable contents.",
        "tags": {"insect", "fire"},
    },
    "cluster_poke": {
        "label": "Wake a mech cluster from range",
        "description": "Use maximum range or indirect fire, then withdraw to prepared EMP and firing positions before machines engage.",
        "tags": {"mechanoid", "cluster", "staging"},
    },
    "intercept_kidnapper": {
        "label": "Intercept a kidnapper",
        "description": "Fast healthy fighters cut off a fleeing pawn carrying a colonist; other defenders cover the route and hospital access.",
        "tags": {"kidnap", "rescue"},
    },
    "covered_rescue": {
        "label": "Rescue under covering fire",
        "description": "A mobile reserve rescues a downed ally only after shooters suppress the nearest threat and the route is clear.",
        "tags": {"rescue", "general"},
    },
    "fire_retreat": {
        "label": "Retreat from fire and heat",
        "description": "Break contact through a non-burning route and use the firefoam-protected fallback rather than fighting in superheated rooms.",
        "tags": {"fire", "fallback"},
    },
    "psycast_control": {
        "label": "Psychic crowd control",
        "description": "Use a feasible hostile psycast such as stun, vertigo, berserk, skip or wall control without exceeding heat or psyfocus limits.",
        "tags": {"psycast", "general"},
    },
    "psycast_support": {
        "label": "Psychic mobility/support",
        "description": "Use a feasible allied psycast such as focus, invisibility, waterskip or skip to rescue, reposition or protect the line.",
        "tags": {"psycast", "rescue", "general"},
    },
    "stand_down": {
        "label": "Stand down",
        "description": "Undraft everyone when the combat API verifies that no hostile pawn remains.",
        "tags": {"post_combat"},
    },
}


MECH_TOKENS = ("mech", "scyther", "lancer", "centipede", "pikeman", "militor", "tesseron", "termite", "diabolus", "war queen")
INSECT_TOKENS = ("insect", "megaspider", "spelopede", "megascarab")
EXPLOSIVE_TOKENS = ("grenade", "doomsday", "triple rocket", "inferno", "mortar")


def _text(row: dict[str, Any]) -> str:
    return " ".join(str(row.get(key) or "") for key in ("name", "kind_def", "faction", "weapon_def", "weapon_label", "current_job")).lower()


def _defense_types(snapshot: dict[str, Any]) -> set[str]:
    return {str(row.get("kind") or "").lower() for row in snapshot.get("combat", {}).get("defenses", [])}


def hostile_is_preparing(row: dict[str, Any]) -> bool:
    job = str(row.get("current_job") or "").lower()
    if job == "goto" or any(token in job for token in ("attack", "breach", "sap", "kidnap", "steal")):
        return False
    lord_toil = str(row.get("lord_toil_name") or "").lower()
    hive_guard = "defendandexpandhive" in str(row.get("lord_job_type") or "").lower()
    return hive_guard or any(token in job for token in ("wait", "wander", "prepare", "siege")) or any(
        token in lord_toil for token in ("stage", "siege")
    )


def guarded_hive_outside_contact(snapshot: dict[str, Any]) -> bool:
    """Do not approach a hive that is defending its own territory at a distance."""
    hostiles = live_hostiles(snapshot)
    return bool(hostiles) and all(
        "defendandexpandhive" in str(row.get("lord_job_type") or "").lower()
        and hostile_is_preparing(row)
        and float(row.get("distance_to_nearest_opponent")
                  if row.get("distance_to_nearest_opponent") is not None else 9999) > 8
        for row in hostiles
    )


def insect_choke_door(snapshot: dict[str, Any]) -> int | None:
    """Find an owned doorway with walls on both flanks and fighters behind it."""
    combat = snapshot.get("combat") or {}
    walls = {
        (int(pos["x"]), int(pos["z"]))
        for row in combat.get("defenses") or [] if row.get("kind") == "wall"
        for pos in [row.get("position") or {}]
        if pos.get("x") is not None and pos.get("z") is not None
    }
    protected = protected_emergency_care_ids(snapshot)
    fighters = [row for row in combat.get("colonists") or []
                if not row.get("is_dead") and not row.get("is_downed")
                and not row.get("is_in_mental_state") and row.get("can_fight", True)
                and row.get("id") not in protected
                and (row.get("position") or {}).get("x") is not None
                and (row.get("position") or {}).get("z") is not None]
    insects = [row for row in live_hostiles(snapshot)
               if any(token in _text(row) for token in INSECT_TOKENS)
               and (row.get("position") or {}).get("x") is not None
               and (row.get("position") or {}).get("z") is not None]
    options: list[tuple[float, int]] = []
    for door in combat.get("defenses") or []:
        pos = door.get("position") or {}
        if (door.get("kind") != "door" or door.get("id") is None
                or pos.get("x") is None or pos.get("z") is None
                or float(door.get("hit_points_percent") if door.get("hit_points_percent") is not None else 1) < 0.5):
            continue
        x, z = int(pos["x"]), int(pos["z"])
        for insect in insects:
            target = insect["position"]
            dx, dz = int(target["x"]) - x, int(target["z"]) - z
            distance = (dx * dx + dz * dz) ** 0.5
            if distance < 2 or distance > 24:
                continue
            along_x = abs(dx) >= abs(dz)
            if any((int(other["position"]["x"]) - x) * dx <= 0 if along_x
                   else (int(other["position"]["z"]) - z) * dz <= 0
                   for other in insects):
                continue
            flank_a = (x, z - 1) if along_x else (x - 1, z)
            flank_b = (x, z + 1) if along_x else (x + 1, z)
            if flank_a not in walls or flank_b not in walls:
                continue
            if along_x:
                behind = [pawn for pawn in fighters
                          if (int(pawn["position"]["x"]) - x) * dx < 0]
            else:
                behind = [pawn for pawn in fighters
                          if (int(pawn["position"]["z"]) - z) * dz < 0]
            if not behind:
                continue
            if not any(pawn.get("weapon_def") and not pawn.get("has_ranged_weapon")
                       and int(pawn.get("melee_skill") or 0) >= 5
                       and float(pawn.get("armor_sharp") or 0) >= 0.4
                       and float(pawn.get("moving", 1)) >= 0.8
                       for pawn in behind):
                continue
            if sum(bool(pawn.get("has_ranged_weapon"))
                   and float(pawn.get("manipulation", 1)) >= 0.65
                   and float(pawn.get("sight", 1)) >= 0.65 for pawn in behind) < 2:
                continue
            approach = min((int(pawn["position"]["x"]) - x) ** 2
                           + (int(pawn["position"]["z"]) - z) ** 2 for pawn in behind)
            if approach > 20 ** 2:
                continue
            options.append((distance + approach ** 0.5 / 4, int(door["id"])))
    return min(options)[1] if options else None


def has_clear_shot(shooter: dict[str, Any], hostiles: list[dict[str, Any]]) -> bool:
    """Range alone is not a firing lane: walls and closed doors can block it."""
    if not shooter.get("has_ranged_weapon"):
        return False
    shootable = shooter.get("shootable_opponent_ids")
    if shootable is not None:
        live_ids = {int(row["id"]) for row in hostiles if row.get("id") is not None
                    and not row.get("is_dead") and not row.get("is_downed")}
        return bool(live_ids.intersection(int(pawn_id) for pawn_id in shootable))
    # Older installed RIMAPI builds exposed only distance. Keep their behavior
    # while the updated combat-state field is being deployed.
    return 2 < float(shooter.get("distance_to_nearest_opponent") or 9999) <= float(shooter.get("weapon_range") or 0) + 1


def available_tactics(snapshot: dict[str, Any]) -> dict[str, str]:
    combat = snapshot.get("combat", {})
    hostiles = [row for row in combat.get("hostiles", []) if not row.get("is_dead") and not row.get("is_downed")]
    protected = protected_emergency_care_ids(snapshot)
    fighters = [row for row in combat.get("colonists", []) if not row.get("is_dead")
                and not row.get("is_downed") and not row.get("is_in_mental_state")
                and row.get("can_fight", True) and row.get("id") not in protected]
    if not hostiles:
        return {"stand_down": TACTICS["stand_down"]["description"]} if any(row.get("is_drafted") for row in fighters) else {}
    if not fighters:
        return {}

    hostile_text = [_text(row) for row in hostiles]
    hostile_jobs = " ".join(hostile_text)
    defenses = _defense_types(snapshot)
    ranged = [row for row in fighters if row.get("has_ranged_weapon") and float(row.get("manipulation", 1)) >= 0.65 and float(row.get("sight", 1)) >= 0.65]
    armed_melee = [row for row in fighters if row.get("weapon_def") and not row.get("has_ranged_weapon")
                   and float(row.get("moving", 1)) >= 0.65]
    melee = [row for row in armed_melee if int(row.get("melee_skill") or 0) >= 5
             and float(row.get("moving", 1)) >= 0.8]
    armored_melee = [row for row in melee if float(row.get("armor_sharp") or 0) >= 0.4]
    psycasts = [ability for pawn in fighters for ability in (pawn.get("psycasts") or []) if ability.get("can_cast")]
    has_explosives = any(any(token in text for token in EXPLOSIVE_TOKENS) for text in hostile_text)
    has_insects = any(any(token in text for token in INSECT_TOKENS) for text in hostile_text)
    insects_only = all(any(token in text for token in INSECT_TOKENS) for text in hostile_text)
    has_kidnapper = "kidnap" in hostile_jobs or any(row.get("carrying_pawn_id") for row in hostiles)
    staging = bool(fighters) and all(float(row.get("distance_to_nearest_opponent") or 0) > 35 for row in fighters) and all(
        hostile_is_preparing(row) for row in hostiles
    )

    in_range = [row for row in ranged if has_clear_shot(row, hostiles)]
    exposed_civilians = [row for row in fighters if not row.get("weapon_def")
                         and float(row.get("distance_to_nearest_opponent") or 9999) <= 18]
    contact = [row for row in ranged if float(row.get("distance_to_nearest_opponent") or 9999) <= 2]
    names: list[str] = ["hold_cover"] if ranged and len(contact) < len(ranged) else []
    if armed_melee:
        names += ["melee_assault", "melee_hold_line"]
        if len(armed_melee) >= 2:
            names.append("coordinate_melee_roles")
    if ranged and (in_range or len(contact) < len(ranged)):
        names.append("focus_fire")
    if ranged and len(in_range) < len(ranged):
        names.append("advance_to_range")
    retreat_distance = max(18.0, min(45.0, max(
        (float(row.get("weapon_range") or 0) + 4.0 for row in hostiles if row.get("has_ranged_weapon")),
        default=0.0,
    )))
    if any(float(row.get("moving", 1)) >= 0.65
           and float(row.get("distance_to_nearest_opponent") or 9999) < retreat_distance
           for row in fighters):
        names.append("withdraw_and_regroup")
    if not ranged and not armed_melee and any(float(row.get("moving", 1)) >= 0.65 for row in fighters):
        names.append("civilian_retreat")
    if len(ranged) >= 2:
        names.append("firing_line")
    if len(ranged) >= 2 and (has_explosives or len(hostiles) >= 8):
        names.append("spread_out")
    if armored_melee and "door" in defenses:
        names += ["melee_block", "door_defense"]
    if "killbox" in defenses:
        names.append("killbox_hold")
    if "fallback" in defenses or "door" in defenses or "barricade" in defenses:
        names.append("fallback_line")
    if staging and len(ranged) >= 3 and all(float(row.get("moving", 1)) >= 0.8 for row in ranged):
        names += ["wide_flank", "pincer", "siege_harass"]
        if any(float(row.get("weapon_range") or 0) >= 30 for row in ranged):
            names.append("counter_snipe")
    if ranged and (any("drop" in text for text in hostile_text) or "waitmaintainposture" in hostile_jobs):
        names.append("drop_pod_encircle")
    if insects_only and armored_melee and len(ranged) >= 2 and insect_choke_door(snapshot) is not None:
        names.append("infestation_choke")
    if len(ranged) >= 2 and all(not row.get("has_ranged_weapon") for row in hostiles) and (has_insects or any("animal" in text or "manhunter" in text for text in hostile_text)):
        # Kiting is a coordinated lure-and-fire plan. A lone mobile pawn (or a
        # lure already outside pursuit distance) merely abandons the shooters.
        if any(
            float(lure.get("moving", 1)) >= 0.85
            and float(lure.get("distance_to_nearest_opponent") or 9999) <= 16
            and any(
                support.get("id") != lure.get("id")
                and float(support.get("distance_to_nearest_opponent") or 9999)
                <= float(support.get("weapon_range") or 0) + 12
                for support in ranged
            )
            for lure in ranged
        ):
            names.append("kite")
    if ranged and all(not row.get("has_ranged_weapon") for row in hostiles):
        if any(float(row.get("distance_to_nearest_opponent") or 9999) <= 12
               and float(row.get("moving", 1)) >= 0.7 for row in ranged):
            names.append("backstep_fire")
        if any(float(row.get("moving", 1)) >= 0.65
               and int(row.get("melee_skill") or 0) >= 3
               and float(row.get("distance_to_nearest_opponent") or 9999) <= 20
               for row in melee) and any(
                   float(row.get("distance_to_nearest_opponent") or 9999)
                   <= float(row.get("weapon_range") or 0) + 1 for row in ranged):
            names.append("screen_melee")
    if any("gun" in text or "sniper" in text or "lancer" in text for text in hostile_text) and armored_melee:
        names.append("rush_ranged")
    if has_kidnapper and ranged:
        names.insert(0, "intercept_kidnapper")
    if psycasts:
        if any(ability.get("hostile") for ability in psycasts):
            names.append("psycast_control")
        if any(not ability.get("hostile") for ability in psycasts):
            names.append("psycast_support")
    if not names:
        names = ["civilian_retreat"] if any(float(row.get("moving", 1)) >= 0.65 for row in fighters) else []
    insect_contact = insects_only and any(
        float(row.get("distance_to_nearest_opponent") or 9999) < 18 for row in fighters)
    if insect_contact and not armored_melee and len(armed_melee) < max(2, len(hostiles)):
        # One unarmored founder should not charge an active insect. A larger
        # sword group can still coordinate against a small number of bugs.
        names = [name for name in names if name != "melee_assault"]
        if len(ranged) < 2:
            names = [name for name in names if name not in {"melee_hold_line", "screen_melee"}]
            if not in_range:
                names = [name for name in names if name not in
                         {"hold_cover", "focus_fire", "advance_to_range", "firing_line"}]

    result: dict[str, str] = {}
    for name in names:
        if name not in result:
            description = TACTICS[name]["description"]
            if name in {"hold_cover", "firing_line"} and len(in_range) < len(ranged):
                description = (f"Hold cover: only {len(in_range)}/{len(ranged)} guns have a clear firing lane now; "
                               "blocked or out-of-range guns must move around walls before they can shoot."
                               + (" An unarmed ally may be captured." if exposed_civilians else ""))
            elif name in {"focus_fire", "advance_to_range"} and exposed_civilians:
                description = (f"{len(exposed_civilians)} unarmed ally(s) threatened nearby. "
                               "Move distant guns into range and order civilian retreat; guns may be exposed "
                               "or arrive too late.")
            if name == "melee_assault" and ranged:
                ready_support = sum(
                    has_clear_shot(row, hostiles)
                    for row in ranged
                )
                weakest_skill = min(int(row.get("melee_skill") or 0) for row in armed_melee)
                least_armor = min(float(row.get("armor_sharp") or 0) for row in armed_melee)
                strongest_enemy = max(int(row.get("melee_skill") or 0) for row in hostiles)
                description = (f"Charge now: {len(armed_melee)} melee, lowest skill {weakest_skill}, "
                               f"armor {least_armor:.1f}; enemy melee up to {strongest_enemy}. "
                               f"Only {ready_support}/{len(ranged)} guns can cover. "
                               "An unsupported low-skill fighter may lose a limb or die.")
            if name == "focus_fire" and len(in_range) < len(ranged):
                description += (f" Only {len(in_range)}/{len(ranged)} armed shooters have a clear shot now; "
                                "the rest will seek trap-free firing lanes, which may expose them.")
            if name == "focus_fire" and len(in_range) < len(hostiles):
                description += " Risk: fewer shooters are in range than active enemies; other fighters may be left exposed."
            if name == "intercept_kidnapper":
                description += (" Pursue the carrier in long trap-free moves and fire whenever a shot opens; "
                                "this exposes the pursuer and may leave the base undefended.")
            if name in {"focus_fire", "hold_cover", "firing_line"} and any(
                float(row.get("distance_to_nearest_opponent") or 9999) <= 6 for row in ranged
            ):
                description += " Risk: a nearby melee enemy may prevent a shooter from firing; a short retreat or melee screen may be better."
            result[name] = description
    return result


def psycast_options(snapshot: dict[str, Any], hostile: bool | None = None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for pawn in snapshot.get("combat", {}).get("colonists", []):
        if pawn.get("is_dead") or pawn.get("is_downed") or pawn.get("is_in_mental_state"):
            continue
        for ability in pawn.get("psycasts") or []:
            if not ability.get("can_cast"):
                continue
            if hostile is not None and bool(ability.get("hostile")) != hostile:
                continue
            key = f"{int(pawn['id'])}:{ability.get('def_name')}"
            result[key] = {
                "pawn_id": int(pawn["id"]),
                "pawn": pawn.get("name"),
                **ability,
                "summary": (
                    f"{pawn.get('name')} — {ability.get('label') or ability.get('def_name')}; "
                    f"focus {float(pawn.get('psyfocus') or 0) * 100:.0f}%, "
                    f"heat {float(pawn.get('neural_heat') or 0):.0f}/{float(pawn.get('neural_heat_limit') or 0):.0f}; "
                    f"cost {float(ability.get('psyfocus_cost') or 0) * 100:.1f}% focus, "
                    f"+{float(ability.get('entropy_gain') or 0):.0f} heat; {ability.get('description') or ''}"
                ),
            }
    return result


def choose_default_target(snapshot: dict[str, Any], tactic: str) -> int | None:
    hostiles = [row for row in snapshot.get("combat", {}).get("hostiles", []) if not row.get("is_dead") and not row.get("is_downed")]
    if not hostiles:
        return None
    active_threats = [row for row in hostiles if not (
        "defendandexpandhive" in str(row.get("lord_job_type") or "").lower()
        and hostile_is_preparing(row)
        and float(row.get("distance_to_nearest_opponent")
                  if row.get("distance_to_nearest_opponent") is not None else 9999) > 8
    )]
    if active_threats:
        hostiles = active_threats
    if tactic == "intercept_kidnapper":
        kidnapping = [row for row in hostiles if "kidnap" in _text(row) or row.get("carrying_pawn_id")]
        if kidnapping:
            hostiles = kidnapping
    if tactic in {"emp_control", "cluster_poke"}:
        mechs = [row for row in hostiles if any(token in _text(row) for token in MECH_TOKENS)]
        if mechs:
            hostiles = mechs
    fighters = [row for row in snapshot.get("combat", {}).get("colonists", []) if not row.get("is_dead") and not row.get("is_downed")]
    def distance(row: dict[str, Any]) -> float:
        position = row.get("position") or {}
        if not fighters or "x" not in position or "z" not in position:
            return 0.0
        return min(((float(position["x"]) - float((pawn.get("position") or {}).get("x", position["x"]))) ** 2
                    + (float(position["z"]) - float((pawn.get("position") or {}).get("z", position["z"]))) ** 2) ** 0.5
                   for pawn in fighters)
    return int(max(hostiles, key=lambda row: (
        bool(row.get("carrying_pawn_id")),
        -int(distance(row) // 12),
        float(row.get("combat_power") or 0),
        -float(row.get("health") if row.get("health") is not None else 1),
    )).get("id"))
