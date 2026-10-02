from __future__ import annotations

import argparse
from itertools import combinations
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

import colony_combat as combat_planner
import colony_capabilities as capabilities
import laya_preferences
from laya_decisions import ask_laya_choice


DEFAULT_API_URL = "http://localhost:8765"
DEFAULT_MODEL = "convaiinnovations/laya"
__version__ = "0.0.6"
SAFE_WORK_TYPES = {
    "prioritize_cooking": "Cooking",
    "prioritize_growing": "Growing",
    "prioritize_hauling": "Hauling",
    "prioritize_construction": "Construction",
    "prioritize_cleaning": "Cleaning",
}
COMBAT_CHOICES = {
    "engage_ranged",
    "engage_melee",
    "equip_ranged_weapon",
    "equip_melee_weapon",
    "draft_best_defender",
    "hold_and_observe",
    "stand_down",
    "remain_drafted",
    "prepare_undrafted",
    "preemptive_strike",
    "equip_emp_weapon",
    "focus_mechanoids",
    "focus_insects",
    "emergency_self_tend",
    "release_trained_animals",
    "recall_combat_animals",
}
COMBAT_CHOICES.update(combat_planner.TACTICS)


class RimApiError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def unwrap(envelope: Any, endpoint: str) -> Any:
    if not isinstance(envelope, dict):
        raise RimApiError(f"{endpoint}: expected a JSON object")
    if envelope.get("success") is False:
        errors = envelope.get("errors") or ["unknown RIMAPI error"]
        raise RimApiError(f"{endpoint}: {'; '.join(map(str, errors))}")
    return envelope.get("data", envelope)


@dataclass
class RimApiClient:
    base_url: str = DEFAULT_API_URL
    timeout: float = 8.0

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("RIMAPI URL must be a local http:// address")
        self.base_url = self.base_url.rstrip("/") + "/"

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        query: dict[str, Any] | None = None,
        body: Any | None = None,
    ) -> Any:
        url = urljoin(self.base_url, endpoint.lstrip("/"))
        if query:
            url += "?" + urlencode(query)
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8-sig"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RimApiError(f"{endpoint}: HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RimApiError(f"{endpoint}: {exc}") from exc
        return unwrap(payload, endpoint)

    def get(self, endpoint: str, **query: Any) -> Any:
        return self.request("GET", endpoint, query=query or None)

    def post(self, endpoint: str, *, query: dict[str, Any] | None = None, body: Any | None = None) -> Any:
        return self.request("POST", endpoint, query=query, body=body)


def first_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_colonists(rows: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        pawn = row.get("pawn") or row.get("colonist") or row
        details = row.get("detailes") or row
        medical = details.get("medical_info") or details.get("colonist_medical_info") or {}
        work = details.get("work_info") or details.get("colonist_work_info") or {}
        skills = {
            str(skill.get("name")): {
                "level": int(first_number(skill.get("level"))),
                "passion": int(first_number(skill.get("passion"))),
                "disabled": bool(skill.get("totally_disabled")),
            }
            for skill in (work.get("skills") or [])
            if isinstance(skill, dict) and skill.get("name")
        }
        priorities = {
            str(item.get("work_type")): {
                "priority": int(first_number(item.get("priority"))),
                "disabled": bool(item.get("is_totally_disabled")),
            }
            for item in (work.get("work_priorities") or [])
            if isinstance(item, dict) and item.get("work_type")
        }
        traits = [
            {
                "name": str(item.get("name") or ""),
                "label": str(item.get("label") or item.get("name") or ""),
                "description": str(item.get("description") or ""),
                "suppressed": bool(item.get("suppressed")),
            }
            for item in (work.get("traits") or [])
            if isinstance(item, dict) and not item.get("suppressed")
        ]
        hediffs = [
            {
                "def_name": str(item.get("def_name") or ""),
                "label": str(item.get("label") or item.get("label_cap") or ""),
                "part": str(item.get("part_label") or item.get("part_def_name") or ""),
                "severity": round(first_number(item.get("severity")), 3),
                "permanent": bool(item.get("is_permanent")),
                "life_threatening": bool(item.get("is_currently_life_threatening")),
                "bleeding": bool(item.get("bleeding")),
                "tendable_now": bool(item.get("tendable_now")),
                "can_ever_kill": bool(item.get("can_ever_kill")),
                "immunity": (round(first_number(item["immunity"]), 4)
                             if item.get("immunity") is not None else None),
                "lethal_severity": item.get("lethal_severity"),
                "tend_quality": item.get("tend_quality"),
                "tend_ticks_left": item.get("tend_ticks_left"),
            }
            for item in (medical.get("hediffs") or [])
            if isinstance(item, dict) and item.get("visible", True)
        ]
        pawn_id = pawn.get("id")
        if pawn_id is None:
            continue
        result.append(
            {
                "id": int(pawn_id),
                "name": str(pawn.get("name") or pawn_id),
                "gender": str(pawn.get("gender") or "None"),
                "age": int(first_number(pawn.get("age"))),
                "health": round(first_number(pawn.get("health"), 1.0), 3),
                "mood": round(first_number(pawn.get("mood"), 0.5), 3),
                "hunger": round(first_number(pawn.get("hunger"), 0.5), 3),
                "rest": round(first_number(details.get("sleep"), 0.5), 3),
                "joy": round(first_number(details.get("joy"), 0.5), 3),
                "bleeding_rate": round(first_number(medical.get("bleeding_rate"), 0.1 if any(
                    condition["bleeding"] and condition["tendable_now"] for condition in hediffs
                ) else 0.0), 3),
                "tendable_now": any(condition["tendable_now"] for condition in hediffs),
                "pain": round(first_number(medical.get("pain")), 3),
                "comfort": round(first_number(details.get("comfort"), 0.5), 3),
                "beauty": round(first_number(details.get("beauty"), 0.5), 3),
                "downed": bool(medical.get("is_downed")),
                "current_job": str(work.get("current_job") or work.get("job") or "unknown"),
                "inspiration": str(work.get("inspiration_def_name") or ""),
                "position": pawn.get("position") or {},
                "skills": skills,
                "work_priorities": priorities,
                "traits": traits,
                "health_conditions": hediffs,
                "patient_feeding_eligible": medical.get("patient_feeding_eligible"),
                "patient_raw_food_allowed": medical.get("patient_raw_food_allowed"),
                "capacities": {
                    "consciousness": round(first_number(medical.get("consciousness"), 1.0), 3),
                    "moving": round(first_number(medical.get("moving"), 1.0), 3),
                    "manipulation": round(first_number(medical.get("manipulation"), 1.0), 3),
                    "sight": round(first_number(medical.get("sight"), 1.0), 3),
                },
                "pain": round(first_number(medical.get("pain")), 3),
                "relations": (details.get("social_info") or {}).get("direct_relations") or [],
            }
        )
    return result


def summarize_resources(things: Any) -> dict[str, int]:
    totals = {"food": 0, "meals": 0, "medicine": 0, "wood": 0, "steel": 0, "components": 0}
    if not isinstance(things, list):
        return totals
    for item in things:
        if not isinstance(item, dict) or item.get("is_forbidden"):
            continue
        name = str(item.get("def_name") or "").lower()
        categories = " ".join(map(str, item.get("categories") or [])).lower()
        amount = max(0, int(first_number(item.get("stack_count"), 1)))
        if "food" in categories or name.startswith("meal") or name.endswith("meat"):
            totals["food"] += amount
        if name.startswith("meal") or "foodmeals" in categories:
            totals["meals"] += amount
        if "medicine" in name:
            totals["medicine"] += amount
        if name == "woodlog":
            totals["wood"] += amount
        if name == "steel":
            totals["steel"] += amount
        if "component" in name:
            totals["components"] += amount
    return totals


def normalize_resource_summary(summary: Any) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {"food": 0, "meals": 0, "raw_food": 0, "nutrition": 0.0,
                "nutrition_rotting_soon": 0.0, "medicine": 0, "weapons": 0}
    critical = summary.get("critical_resources") or {}
    food = critical.get("food_summary") or {}
    rot = food.get("rot_status_info") or {}
    return {
        "food": int(first_number(food.get("food_total"))),
        "meals": int(first_number(food.get("meals_count"))),
        "raw_food": int(first_number(food.get("raw_food_count"))),
        "nutrition": round(first_number(food.get("total_nutrition")), 2),
        "nutrition_rotting_soon": round(first_number(rot.get("nutrition_rotating_soon")), 2),
        "medicine": int(first_number(critical.get("medicine_total"))),
        "weapons": int(first_number(critical.get("weapon_count"))),
    }


def safe_get(client: RimApiClient, endpoint: str, warnings: list[str], **query: Any) -> Any:
    try:
        return client.get(endpoint, **query)
    except RimApiError as exc:
        warnings.append(str(exc))
        return None


def annotate_mental_states(colonists: list[dict[str, Any]], fighters: Any) -> None:
    """The combat feed exposes a pawn's live mental break; the detailed feed does not."""
    by_id = {
        int(row["id"]): bool(row.get("is_in_mental_state"))
        for row in (fighters if isinstance(fighters, list) else []) if isinstance(row, dict)
        and row.get("id") is not None
    }
    for colonist in colonists:
        colonist["in_mental_state"] = by_id.get(int(colonist.get("id") or 0), False)


def annotate_combat_capability(colonists: list[dict[str, Any]], combat: Any) -> None:
    """Do not mistake a pacifist holding a gun for an available defender."""
    if not isinstance(combat, dict):
        return
    by_id = {int(row["id"]): row for row in colonists if row.get("id") is not None}
    for pawn in combat.get("colonists") or []:
        detail = by_id.get(int(pawn.get("id") or 0))
        if detail is None:
            continue
        skills = detail.get("skills") or {}
        combat_skills = [skills[name] for name in ("Shooting", "Melee")
                         if isinstance(skills.get(name), dict)]
        pawn["can_fight"] = not combat_skills or any(not row.get("disabled") for row in combat_skills)


def active_immune_diseases(pawn: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep lethal disease recovery separate from summary wound health."""
    return [h for h in pawn.get("health_conditions") or [] if isinstance(h, dict)
            and ((h.get("can_ever_kill") and h.get("immunity") is not None)
                 or "infection" in str(h.get("def_name") or "").lower())
            and (h.get("immunity") is None or first_number(h.get("immunity")) < 1)]


def annotate_combat_medical_state(colonists: list[dict[str, Any]], combat: Any) -> None:
    """Use the live combat rate instead of the detailed API's wound placeholder."""
    if not isinstance(combat, dict):
        return
    by_id = {int(row["id"]): row for row in colonists if row.get("id") is not None}
    for pawn in combat.get("colonists") or []:
        detail = by_id.get(int(pawn.get("id") or 0))
        if detail is None:
            continue
        if pawn.get("bleeding_rate") is not None:
            detail["bleeding_rate"] = round(first_number(pawn["bleeding_rate"]), 3)
        if pawn.get("tendable_now") is not None:
            detail["tendable_now"] = bool(pawn["tendable_now"])
        if pawn.get("is_downed") is not None:
            detail["downed"] = bool(pawn["is_downed"])
        if pawn.get("current_job") is not None:
            detail["current_job"] = str(pawn["current_job"])


def collect_snapshot(client: RimApiClient) -> dict[str, Any]:
    warnings: list[str] = []
    game = client.get("/api/v1/game/state")
    maps = client.get("/api/v1/maps")
    if not isinstance(maps, list) or not maps:
        raise RimApiError("RIMAPI reports no loaded map; load a colony first")
    # An active quest/rescue map takes precedence over the home colony while
    # player pawns are fighting there.  Otherwise use the currently selected
    # populated map, then the main settlement.
    home = next(
        (m for m in maps if int(first_number(m.get("free_colonists"))) > 0 and int(first_number(m.get("hostiles"))) > 0),
        next(
            (m for m in maps if m.get("is_temp_incident_map") and int(first_number(m.get("free_colonists"))) > 0),
            next((m for m in maps if m.get("is_player_home")), maps[0]),
        ),
    )
    map_id = int(home.get("id", home.get("index", 0)))

    raw_colonists = safe_get(client, "/api/v2/colonists/detailed", warnings)
    if raw_colonists is None:
        raw_colonists = client.get("/api/v1/colonists")
    colonists = normalize_colonists(raw_colonists)
    creatures = safe_get(client, "/api/v1/map/creatures/summary", warnings, map_id=map_id) or {}
    farm = safe_get(client, "/api/v1/map/farm/summary", warnings, map_id=map_id) or {}
    date_info = safe_get(client, "/api/v1/datetime", warnings) or {}
    resource_summary = safe_get(client, "/api/v1/resources/summary", warnings, map_id=map_id)
    combat = safe_get(client, "/api/v1/combat/state", warnings, map_id=map_id) or {}
    raw_animals = safe_get(client, "/api/v1/map/animals", warnings, map_id=map_id) or []
    raw_wild_humans = safe_get(client, "/api/v1/map/wild-humans", warnings, map_id=map_id) or []
    hostiles = combat.get("hostiles") if isinstance(combat, dict) else []
    fighters = combat.get("colonists") if isinstance(combat, dict) else []
    weapons = combat.get("available_weapons") if isinstance(combat, dict) else []
    annotate_mental_states(colonists, fighters)
    annotate_combat_capability(colonists, combat)
    annotate_combat_medical_state(colonists, combat)

    return {
        "captured_at": utc_now(),
        "game": {
            "tick": game.get("game_tick"),
            "wealth": game.get("colony_wealth"),
            "colonist_count": game.get("colonist_count", len(colonists)),
            "storyteller": game.get("storyteller"),
            "is_paused": bool(game.get("is_paused")),
            "date": date_info.get("datetime"),
        },
        "map": {
            "id": map_id,
            "seed": home.get("seed"),
            "tile_id": home.get("tile_id"),
            "is_player_home": bool(home.get("is_player_home")),
            "is_temp_incident_map": bool(home.get("is_temp_incident_map")),
            "is_current_map": bool(home.get("is_current_map")),
            "enemies": (len(hostiles) if isinstance(hostiles, list) else int(first_number(creatures.get("enemies_count"))))
                       + sum(bool(row.get("active_threat")) for row in combat.get("hostile_buildings") or []),
            "animals": int(first_number(creatures.get("animals_count"))),
            "growing_zones": int(first_number(farm.get("total_growing_zones"))),
            "plants": int(first_number(farm.get("total_plants"))),
            "expected_yield": round(first_number(farm.get("total_expected_yield")), 2),
            "resources": normalize_resource_summary(resource_summary),
        },
        "colonists": colonists,
        "wild_humans": [{
            "id": int(row["id"]), "name": str(row.get("name") or row["id"]),
            "gender": str(row.get("gender") or "None"),
            "age": int(first_number(row.get("age"))),
            "health": round(first_number(row.get("health"), 1.0), 3),
            "downed": bool(row.get("downed")),
            "minimum_handling_skill": int(first_number(row.get("minimum_handling_skill"), 7)),
            "position": row.get("position") or {},
        } for row in raw_wild_humans if isinstance(row, dict) and row.get("id") is not None],
        "animals": [
            {
                "id": int(row.get("id")),
                "name": str(row.get("name") or row.get("def") or row.get("id")),
                "def": str(row.get("def") or ""),
                "is_colony_animal": bool(row.get("is_colony_animal")),
                "health": round(first_number(row.get("health"), 1.0), 3),
                "hunger": round(first_number(row.get("hunger"), 1.0), 3),
                "rest": round(first_number(row.get("rest"), 1.0), 3),
                "consciousness": round(first_number(row.get("consciousness"), 1.0), 3),
                "moving": round(first_number(row.get("moving"), 1.0), 3),
                "pain": round(first_number(row.get("pain")), 3),
                "health_conditions": [
                    {"def_name": str(condition.get("def_name") or ""),
                     "label": str(condition.get("label") or ""),
                     "severity": round(first_number(condition.get("severity")), 3),
                     "stage": str(condition.get("stage") or ""),
                     "tendable_now": bool(condition.get("tendable_now")),
                     "is_permanent": bool(condition.get("is_permanent")),
                     "is_currently_life_threatening": bool(condition.get("is_currently_life_threatening")),
                     "can_ever_kill": bool(condition.get("can_ever_kill")),
                     "immunity": condition.get("immunity"),
                     "tend_quality": condition.get("tend_quality"),
                     "tend_ticks_left": condition.get("tend_ticks_left")}
                    for condition in row.get("health_conditions") or []
                    if isinstance(condition, dict)
                ],
                "bleeding_rate": round(first_number(row.get("bleeding_rate")), 3),
                "tendable_now": bool(row.get("tendable_now")),
                "gender": str(row.get("gender") or "None"),
                "wildness": round(first_number(row.get("wildness"), 1.0), 3),
                "minimum_handling_skill": int(first_number(row.get("minimum_handling_skill"))),
                "master_pawn_id": row.get("master_pawn_id"),
                "bonded_pawn_id": row.get("bonded_pawn_id"),
                "follow_drafted": bool(row.get("follow_drafted")),
                "animals_released": bool(row.get("animals_released")),
                "trainability": row.get("trainability"),
                "trainables": row.get("trainables") or [],
                "in_mental_state": bool(row.get("in_mental_state")),
                "combat_power": first_number(row.get("combat_power")),
                "manhunter_on_tame_fail_chance": round(first_number(row.get("manhunter_on_tame_fail_chance")), 3),
                "reproductive": bool(row.get("reproductive")),
                "requires_pen": row.get("requires_pen"),
                "has_suitable_enclosed_pen": bool(row.get("has_suitable_enclosed_pen")),
                "pregnant": bool(row.get("pregnant")),
                "downed": bool(row.get("downed")),
                "dead": bool(row.get("dead")),
                "current_job": str(row.get("current_job") or "unknown"),
                "position": row.get("position") or {},
                "min_comfortable_temperature": round(first_number(row.get("min_comfortable_temperature"), -10.0), 1),
                "max_comfortable_temperature": round(first_number(row.get("max_comfortable_temperature"), 40.0), 1),
            }
            for row in raw_animals
            if isinstance(row, dict) and row.get("id") is not None and bool(row.get("is_colony_animal"))
        ],
        "wild_animals": [
            {
                "id": int(row.get("id")),
                "name": str(row.get("name") or row.get("def") or row.get("id")),
                "def": str(row.get("def") or ""),
                "gender": str(row.get("gender") or "None"),
                "wildness": round(first_number(row.get("wildness"), 1.0), 3),
                "minimum_handling_skill": int(first_number(row.get("minimum_handling_skill"))),
                "manhunter_on_tame_fail_chance": round(first_number(row.get("manhunter_on_tame_fail_chance")), 3),
                "reproductive": bool(row.get("reproductive")),
                "pregnant": bool(row.get("pregnant")),
                "can_tame": bool(row.get("can_be_designated_for_taming")),
                "requires_pen": row.get("requires_pen"),
                "has_suitable_enclosed_pen": bool(row.get("has_suitable_enclosed_pen")),
                "market_value": round(first_number(row.get("market_value")), 1),
                "meat_amount": int(first_number(row.get("meat_amount"))),
                "leather_amount": int(first_number(row.get("leather_amount"))),
                "combat_power": round(first_number(row.get("combat_power")), 1),
                "predator": bool(row.get("predator")),
                "harm_revenge_chance": round(first_number(row.get("harm_revenge_chance")), 3),
                "position": row.get("position") or {},
                "min_comfortable_temperature": round(first_number(row.get("min_comfortable_temperature"), -10.0), 1),
                "max_comfortable_temperature": round(first_number(row.get("max_comfortable_temperature"), 40.0), 1),
            }
            for row in raw_animals
            if isinstance(row, dict) and row.get("id") is not None and not bool(row.get("is_colony_animal")) and not bool(row.get("dead"))
        ],
        "combat": {
            "available": bool(combat),
            "colonists": fighters if isinstance(fighters, list) else [],
            "hostiles": hostiles if isinstance(hostiles, list) else [],
            "hostile_buildings": combat.get("hostile_buildings") or [],
            "native_options": combat.get("native_options") or [],
            "available_weapons": weapons if isinstance(weapons, list) else [],
            "colony_animals": combat.get("colony_animals") or [],
            "defenses": combat.get("defenses", []) if isinstance(combat, dict) else [],
        },
        "warnings": warnings,
    }


def decision_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    colonists = snapshot["colonists"]
    def stat(name: str, fn: Any, default: float) -> float:
        values = [first_number(c.get(name), default) for c in colonists]
        return round(fn(values), 3) if values else default

    has_hostiles = bool(combat_planner.live_hostiles(snapshot))
    has_drafted = any(bool(c.get("is_drafted")) for c in snapshot["combat"]["colonists"])
    if has_hostiles:
        task = "Choose one immediate defensive action against verified hostile pawns."
    elif has_drafted:
        task = "The API verifies that no hostile pawns remain; decide whether to end combat readiness."
    else:
        task = "Choose one safe colony work-priority action for the next short interval."
    preferences = laya_preferences.load_preferences()
    if has_hostiles:
        combat = snapshot["combat"]
        welfare = {row.get("id"): row for row in colonists}
        def fighter(row: dict[str, Any]) -> str:
            needs = welfare.get(row.get("id")) or {}
            return (
                f"{row.get('name') or row.get('id')}#{row.get('id')} hp={first_number(row.get('health')):.2f} "
                f"{'down' if row.get('is_downed') else 'mental_break' if row.get('is_in_mental_state') else 'up'} "
                f"{row.get('weapon_def') or 'unarmed'} range={first_number(row.get('weapon_range')):.0f} "
                f"armor={first_number(row.get('armor_sharp')):.2f} shoot={row.get('shooting_skill')} "
                f"melee={row.get('melee_skill')} dist={first_number(row.get('distance_to_nearest_opponent')):.0f} "
                f"pos={row.get('position')} "
                f"move={first_number(row.get('moving'), 1):.2f} pain={first_number(row.get('pain')):.2f} "
                f"bleed={first_number(row.get('bleeding_rate')):.2f} tendable={bool(row.get('tendable_now'))} "
                f"rest={first_number(needs.get('rest'), 1):.2f} food={first_number(needs.get('hunger'), 1):.2f} "
                f"job={row.get('current_job')} target={row.get('current_job_target_id')}"
            )
        def hostile(row: dict[str, Any]) -> str:
            return (
                f"{row.get('kind_def') or row.get('name')}#{row.get('id')} hp={first_number(row.get('health')):.2f} "
                f"{row.get('weapon_def') or 'unarmed'} job={row.get('current_job')} "
                f"group={row.get('lord_toil_name') or ''} "
                f"range={first_number(row.get('weapon_range')):.0f} "
                f"dist={first_number(row.get('distance_to_nearest_opponent')):.0f} "
                f"power={first_number(row.get('combat_power')):.0f} carrying={row.get('carrying_pawn_id')}"
            )
        ranked_hostiles = sorted(combat.get("hostiles", []), key=lambda row: (
            not bool(row.get("carrying_pawn_id")), first_number(row.get("distance_to_nearest_opponent"), 9999),
            -first_number(row.get("combat_power")),
        ))
        ranked_fighters = sorted(combat.get("colonists", []), key=lambda row: (
            not bool(row.get("has_ranged_weapon")), first_number(row.get("distance_to_nearest_opponent"), 9999),
        ))
        active_enemies = [row for row in combat.get("hostiles", [])
                          if not row.get("is_dead") and not row.get("is_downed")]
        available_allies = [row for row in combat.get("colonists", [])
                            if not row.get("is_dead") and not row.get("is_downed")
                            and not row.get("is_in_mental_state") and row.get("can_fight", True)]
        enemy_gear = sorted({str(row.get("weapon_def") or row.get("kind_def") or "unknown")
                             for row in active_enemies})
        allied_gear = sorted({str(row.get("weapon_def") or "unarmed") for row in available_allies})
        return {
            "task": task,
            "paused": bool(snapshot["game"].get("is_paused")),
            "hostiles": [hostile(row) for row in ranked_hostiles[:8]],
            "hostile_count": len(combat.get("hostiles", [])),
            "fighters": [fighter(row) for row in ranked_fighters[:12]],
            "fighter_count": len(combat.get("colonists", [])),
            "force_balance": {
                "active_enemies": len(active_enemies),
                "enemy_gear": enemy_gear[:12],
                "enemy_health": [round(first_number(row.get("health"), 1), 2) for row in active_enemies[:12]],
                "available_allies": len(available_allies),
                "available_shooters": sum(bool(row.get("has_ranged_weapon")) for row in available_allies),
                "available_armed_melee": sum(bool(row.get("weapon_def")) and not row.get("has_ranged_weapon")
                                              for row in available_allies),
                "downed_allies": sum(bool(row.get("is_downed")) for row in combat.get("colonists", [])),
                "allies_in_mental_break": sum(bool(row.get("is_in_mental_state")) for row in combat.get("colonists", [])),
                "allied_gear": allied_gear[:12],
                "shooters_with_clear_shot": sum(combat_planner.has_clear_shot(row, active_enemies)
                                                for row in available_allies),
            },
            "combat_tradeoff": (
                "Keeping a wounded fighter may cost that fighter's life, but withdrawing them removes firepower "
                "or a melee screen and can doom everyone else. Withdrawing the whole team may preserve survivors "
                "for regrouping, but stops fire and may let enemies pursue or capture someone. A fighter can also "
                "deliberately hold danger so others escape. Compare both risks using live health, enemy numbers, "
                "weapons, ranges, terrain and remaining defenses; none of these outcomes is mandatory."
            ),
            "defenses": sorted({str(row.get("kind")) for row in combat.get("defenses", [])})[:8],
            "free_weapons": [str(row.get("label") or row.get("def_name")) for row in combat.get("available_weapons", [])[:6]],
            "risk_context": "Unarmed civilians face high melee risk. Raiders who are still preparing leave time to eat, rest, equip and work. An advancing or kidnapping enemy changes that tradeoff.",
        }
    return {
        "task": task,
        "game": snapshot["game"],
        "threats": snapshot["map"]["enemies"],
        "farm": {
            "zones": snapshot["map"]["growing_zones"],
            "plants": snapshot["map"]["plants"],
            "expected_yield": snapshot["map"]["expected_yield"],
        },
        "resources": snapshot["map"]["resources"],
        "colonist_welfare": {
            "count": len(colonists),
            "lowest_health": stat("health", min, 1.0),
            "lowest_mood": stat("mood", min, 0.5),
            "lowest_food_level": stat("hunger", min, 0.5),
            "highest_bleeding_rate": stat("bleeding_rate", max, 0.0),
        },
        "current_jobs": [c["current_job"] for c in colonists[:8]],
        "combat": snapshot["combat"],
        "player_preferences": laya_preferences.model_context(preferences),
        "constraints": [
            "Do not cheat, spawn items, edit pawn stats, or force combat.",
            "During a threat, use only real drafted colonists and real hostile target IDs.",
            "Only one colonist work priority may be changed per cycle.",
        ],
    }


def combat_model_context(agent: Any, snapshot: dict[str, Any], *,
                         role_target: dict[str, Any] | None = None,
                         assigned_roles: dict[int, str] | None = None) -> dict[str, Any]:
    """Fit actionable combat evidence into Laya's real state-token window."""
    if not combat_planner.live_hostiles(snapshot):
        # Post-combat choices need the verified absence of hostiles and the
        # squad's condition. Serializing the entire map here can exceed Laya's
        # tokenizer limit even though the model later truncates the sequence.
        resources = (snapshot.get("map") or {}).get("resources") or {}
        farm = snapshot.get("map") or {}
        preferences = laya_preferences.model_context(laya_preferences.load_preferences())
        def count_rows(value: Any) -> int:
            return len(value) if isinstance(value, (list, tuple, dict)) else int(first_number(value))
        return {
            "task": "Post-combat or routine work",
            "hostiles": 0,
            "drafted": sum(bool(pawn.get("is_drafted")) for pawn in snapshot["combat"].get("colonists", [])),
            "people": [{
                "id": pawn.get("id"), "health": pawn.get("health"),
                "downed": pawn.get("is_downed"), "drafted": pawn.get("is_drafted"),
                "bleeding": pawn.get("bleeding_rate"),
                "job": pawn.get("current_job"),
                "work": {name: ((pawn.get("work_priorities") or {}).get(name) or {}).get("priority")
                         for name in ("Cooking", "Growing", "Hauling", "Construction", "Cleaning")},
            } for pawn in snapshot["colonists"][:4]],
            "resources": {name: resources.get(name) for name in ("food", "meals", "raw_food", "medicine")},
            "farm": {
                "zones": count_rows(farm.get("growing_zones")),
                "plants": count_rows(farm.get("plants")),
                "expected_yield": farm.get("expected_yield"),
            },
            "player_preferences": {
                "weights": preferences.get("priority_weights_0_to_100"),
                "guidance": str(preferences.get("personal_guidance") or "")[:120],
            },
        }
    combat = snapshot["combat"]
    active = combat_planner.live_hostiles(snapshot)
    tactical_facts = combat_planner.threat_facts(snapshot)
    available = [row for row in combat.get("colonists", []) if not row.get("is_dead")
                 and not row.get("is_downed") and not row.get("is_in_mental_state")
                 and row.get("can_fight", True)]
    fighters = sorted(combat.get("colonists", []), key=lambda row: (
        not bool(row.get("tendable_now") or row.get("bleeding_rate")),
        first_number(row.get("health"), 1),
        first_number(row.get("distance_to_nearest_opponent"), 9999),
    ))
    enemies = sorted(active, key=lambda row: (
        not bool(row.get("carrying_pawn_id")),
        first_number(row.get("distance_to_nearest_opponent"), 9999),
    ))
    welfare = {row.get("id"): row for row in snapshot.get("colonists", [])}
    allied_gear = sorted({str(row.get("weapon_def") or "unarmed") for row in fighters})
    enemy_gear = sorted({str(row.get("weapon_def") or "unarmed") for row in enemies})
    enemy_kinds = sorted({str(row.get("kind_def") or row.get("name") or "enemy") for row in enemies})
    shooters = [row for row in available if row.get("has_ranged_weapon")]
    covering_now = sum(combat_planner.has_clear_shot(row, active) for row in shooters)
    exposed_civilians = [row for row in combat.get("colonists", [])
                         if not row.get("is_dead") and not row.get("is_downed")
                         and (not row.get("weapon_def") or not row.get("can_fight", True))
                         and first_number(row.get("distance_to_nearest_opponent"), 9999) <= 18]
    immediate_threat = (
        f"{len(exposed_civilians)} unarmed ally(s) within 18 cells of an enemy; "
        f"{covering_now}/{len(shooters)} guns have a clear firing lane. Holding a blocked line does not "
        "protect the civilian; moving around walls may expose shooters but can prevent injury or kidnapping. "
        "Advancing guns can expose them; withdrawing the civilian may separate the squad."
        if exposed_civilians else None
    )
    def fighter(row: dict[str, Any]) -> str:
        needs = welfare.get(row.get("id")) or {}
        gear = allied_gear.index(str(row.get("weapon_def") or "unarmed"))
        status = ("/down" if row.get("is_downed") else
                  "/mental_break" if row.get("is_in_mental_state") else
                  "/pacifist" if not row.get("can_fight", True) else "")
        low_rest = "/tired" if first_number(needs.get("rest"), 1) < 0.5 else ""
        return (f"{row.get('id')}:{round(first_number(row.get('health'), 1) * 100)}/"
                f"{round(first_number(row.get('bleeding_rate')) * 100)}/{gear}/"
                f"{round(first_number(row.get('weapon_range')))}/"
                f"{round(first_number(row.get('distance_to_nearest_opponent'), 9999))}/"
                f"{int(combat_planner.has_clear_shot(row, active))}/"
                f"{round(first_number(row.get('moving'), 1) * 100)}/"
                f"{int(first_number(row.get('melee_skill')))}/"
                f"{int(first_number(row.get('shooting_skill')))}/"
                f"{round(first_number(row.get('armor_sharp')) * 100)}{status}{low_rest}")
    def hostile(row: dict[str, Any]) -> str:
        gear = enemy_gear.index(str(row.get("weapon_def") or "unarmed"))
        kind = enemy_kinds.index(str(row.get("kind_def") or row.get("name") or "enemy"))
        carrying = f"/carrying={row['carrying_pawn_id']}" if row.get("carrying_pawn_id") else ""
        return (f"{row.get('id')}:{kind}/{round(first_number(row.get('health'), 1) * 100)}/{gear}/"
                f"{round(first_number(row.get('weapon_range')))}/"
                f"{round(first_number(row.get('distance_to_nearest_opponent'), 9999))}/"
                f"{int(first_number(row.get('melee_skill')))}/"
                f"{round(first_number(row.get('armor_sharp')) * 100)}{carrying}")
    state: dict[str, Any] = {}
    if role_target is not None:
        state["role_target"] = role_target
        state["roles_already_assigned"] = assigned_roles or {}
    state.update({
        "task": "Whole-squad combat",
        "choice_context": tactical_facts,
        "paused": bool(snapshot["game"].get("is_paused")),
        "phase": "preparing" if active and all(combat_planner.hostile_is_preparing(row) for row in active) else "assault",
        "forces": (f"{len(available)} allies, {sum(bool(row.get('has_ranged_weapon')) for row in available)} guns, "
                   f"{sum(bool(row.get('weapon_def')) and not row.get('has_ranged_weapon') for row in available)} melee, "
                   f"{sum(not bool(row.get('weapon_def')) for row in available)} unarmed; "
                   f"{len(active)} enemies; {sum(bool(row.get('is_downed')) for row in combat.get('colonists', []))} allies down"),
        "covering_guns": f"{covering_now}/{len(shooters)} have clear firing lanes",
        "trained_combat_animals": [{"id": a.get("id"), "name": a.get("name"), "master": a.get("master_pawn_id"),
                                     "power": a.get("combat_power"), "health": a.get("health"), "released": a.get("animals_released")}
                                    for a in capabilities.combat_animals(snapshot)],
        **({"immediate_threat": immediate_threat} if immediate_threat else {}),
        "ally_weapons": allied_gear,
        "enemy_weapons": enemy_gear,
        "enemy_kinds": enemy_kinds,
        "enemy_jobs": sorted({str(row.get("current_job") or row.get("lord_toil_name") or "unknown") for row in active})[:5],
        "fighter_format": "id:hp%/bleed%/weapon#/range/dist/clear-shot(1|0)/move%/melee/shoot/armor%",
        "hostile_format": "id:kind#/hp%/weapon#/range/dist/melee/armor%",
        "fighters": [fighter(row) for row in fighters],
        "hostiles": [hostile(row) for row in enemies],
        "defenses": sorted({str(row.get("kind")) for row in combat.get("defenses", [])})[:5],
        "tradeoff": "Fight wounded: may die. Withdraw: lose firepower, allies may die. Retreat: save squad, yield ground.",
    })
    tokenizer = getattr(agent, "tok", None)
    if tokenizer is None:
        return state
    config = getattr(agent, "cfg", {}) or {}
    budget = max(64, int(config.get("max_len", 512)) - int(config.get("head_max_len", 192)) - 8)
    def fits() -> bool:
        payload = json.dumps(state, ensure_ascii=False)
        try:
            encoded = tokenizer(payload, add_special_tokens=False,
                                truncation=True, max_length=budget + 1)
        except TypeError:
            encoded = tokenizer(payload, add_special_tokens=False)
        return len(encoded["input_ids"]) <= budget
    if fits():
        return state
    # Keep the actual three-person squad visible before dropping less important
    # descriptive fields. A one-fighter snapshot misrepresents a live battle.
    for fighter_limit, enemy_limit in ((8, 5), (5, 3), (3, 2)):
        state["fighters"] = [fighter(row) for row in fighters[:fighter_limit]]
        state["hostiles"] = [hostile(row) for row in enemies[:enemy_limit]]
        if fits():
            return state
    contact_gunners = [row for row in available if row.get("has_ranged_weapon")
                       and first_number(row.get("distance_to_nearest_opponent"), 9999) <= 2]
    contact_risk = (
        f"Gun in melee: {', '.join(str(row.get('name')) for row in contact_gunners[:2])}; "
        f"bleeding {max(first_number(row.get('bleeding_rate')) for row in contact_gunners):.2f}. "
        "Gun-bashing stops shooting; a short retreat can restore range but the enemy may pursue."
        if contact_gunners else None
    )
    def compact_hostile(row: dict[str, Any]) -> str:
        return (f"{row.get('kind_def') or row.get('name') or 'enemy'}#{row.get('id')}:"
                f"{round(first_number(row.get('health'), 1) * 100)}%/"
                f"{row.get('weapon_def') or 'natural'}/"
                f"{round(first_number(row.get('distance_to_nearest_opponent'), 9999))}cells")
    compact = {
        "task": "Combat: decide for all fighters",
        **({"contact_ids": tactical_facts["contact_fighters"][:4]}
           if tactical_facts["contact_fighters"] else {}),
        **({"carriers": [{"id": row["id"], "carrying": row["carrying_pawn_id"]}
                        for row in tactical_facts["carriers"][:2]]} if tactical_facts["carriers"] else {}),
        "forces": state["forces"],
        "covering_guns": state["covering_guns"],
        "ally_weapons": state["ally_weapons"],
        "fighter_format": state["fighter_format"],
        "fighters": [fighter(row) for row in fighters[:3]],
        "hostiles": [compact_hostile(row) for row in enemies[:2]],
        "risk": (contact_risk or f"Unarmed ally near enemy; {covering_now}/{len(shooters)} guns have clear shots. "
                 "Walls block fire; moving to a lane exposes guns, but waiting risks capture."
                 if immediate_threat else
                 contact_risk or "Injured fighters may die; withdrawal saves them but reduces firepower."),
    }
    if role_target is not None:
        compact["role_target"] = role_target
    state = compact
    if fits():
        return state
    state.pop("ally_weapons", None)
    state.pop("fighter_format", None)
    state["fighters"] = [fighter(row) for row in fighters[:2]]
    state["hostiles"] = [compact_hostile(row) for row in enemies[:1]]
    if fits():
        return state
    raise ValueError("Laya combat context exceeds its real token budget even after compacting")


def ask_combat_choice(agent: Any, state: dict[str, Any], question_id: str,
                      question: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Use the same bounded option protocol as development decisions."""
    options = dict(question.get("criteria") or {})
    # Test doubles without Laya's tokenizer keep their observable single call.
    # Production always uses the bounded tournament when the list is long.
    if len(options) > 6 and getattr(agent, "tok", None) is None:
        raw = agent.predict(state, {question_id: question})
        return str((raw.get("answers") or {}).get(question_id, {}).get("choice") or ""), raw
    return ask_laya_choice(agent, state, question_id, str(question.get("instructions") or ""), options)


def make_questions(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if snapshot["combat"]["hostiles"] or combat_planner.live_hostiles(snapshot):
        criteria = combat_planner.available_tactics(snapshot)
        protected = combat_planner.protected_emergency_care_ids(snapshot)
        fighters = [
            pawn for pawn in snapshot["combat"].get("colonists", [])
            if not pawn.get("is_dead") and not pawn.get("is_downed") and not pawn.get("is_in_mental_state")
            and pawn.get("can_fight", True) and pawn.get("id") not in protected
        ]
        living_colonists = [pawn for pawn in snapshot["combat"].get("colonists", [])
                            if not pawn.get("is_dead") and not pawn.get("is_downed")]
        mobile_civilians = [pawn for pawn in living_colonists
                            if not pawn.get("is_in_mental_state")
                            and pawn.get("id") not in protected
                            and first_number(pawn.get("moving"), 1) >= 0.65
                            and (not pawn.get("can_fight", True) or not pawn.get("weapon_def"))]
        if any(combat_planner.errand_exposed(snapshot, pawn.get("position"))
               for pawn in mobile_civilians):
            criteria["civilian_retreat"] = (
                "Move mobile civilians, including pacifists, away from the threat instead of leaving them to sleep or haul nearby."
            )
        drafted = any(pawn.get("is_drafted") for pawn in living_colonists)
        safe_ranged_pairs = [
            (pawn, weapon)
            for pawn in fighters
            if not pawn.get("has_ranged_weapon")
            and first_number(pawn.get("sight"), 1) >= 0.65
            and first_number(pawn.get("manipulation"), 1) >= 0.65
            for weapon in snapshot["combat"].get("available_weapons", [])
            if weapon.get("is_ranged") and capabilities.weapon_compatible(pawn, weapon) and not combat_planner.errand_exposed(
                snapshot, weapon.get("position"), pawn.get("position"))
        ]
        actively_fighting = any(pawn.get("is_drafted") and str(pawn.get("current_job") or "").lower() in {
            "attackstatic", "attackmelee", "goto", "wait_combat", "castverb",
        } for pawn in living_colonists)
        staging_distance = 70 if actively_fighting else 35
        staging = bool(fighters) and bool(living_colonists) and all(
            first_number(pawn.get("distance_to_nearest_opponent"), 9999) > staging_distance
            for pawn in living_colonists
        ) \
            and all(combat_planner.hostile_is_preparing(row) for row in combat_planner.live_hostiles(snapshot))
        armed_shooters = [pawn for pawn in fighters if pawn.get("has_ranged_weapon")]
        ready_shooters = [pawn for pawn in armed_shooters if first_number(pawn.get("weapon_range")) >= 25
                          and first_number(pawn.get("moving"), 1) >= 0.8]
        welfare = {pawn.get("id"): pawn for pawn in snapshot.get("colonists", [])}
        hostile_rows = combat_planner.live_hostiles(snapshot)
        if hostile_rows and not drafted and all(combat_planner.hostile_is_preparing(row) for row in hostile_rows) \
                and all(first_number(pawn.get("distance_to_nearest_opponent"), 9999) > 35
                        and not pawn.get("is_downed")
                        and first_number(pawn.get("bleeding_rate")) <= 0.05
                        for pawn in snapshot["combat"].get("colonists", []) if not pawn.get("is_dead")):
            criteria["continue_safe_colony_work"] = (
                "Continue ordinary colony work while distant hostiles guard their area; avoid all exposed pickups and routes."
            )
        far_assault = bool(hostile_rows) and not staging and not actively_fighting and not any(
            combat_planner.is_kidnapper(pawn)
            for pawn in hostile_rows
        ) and all(
            first_number(pawn.get("distance_to_nearest_opponent"), 0) > max(
                10, first_number(pawn.get("weapon_range")) - 2
            ) for pawn in armed_shooters
        ) and all(
            first_number(pawn.get("distance_to_nearest_opponent"), 0) > 25 for pawn in living_colonists
        ) and all(
            first_number(pawn.get("distance_to_nearest_opponent"), 0) > max(
                25, first_number(pawn.get("weapon_range")) + 5
            ) for pawn in hostile_rows
        )
        if staging:
            if drafted and not actively_fighting:
                criteria["prepare_undrafted"] = "Raiders are preparing: undraft so fighters can eat, rest and work; a sudden assault may catch them unready."
            criteria["hold_and_observe"] = (
                "Observe staging raiders while keeping the current defense; drafted colonists will not rest or eat."
                if drafted else "Observe staging raiders while civilians continue their current safe jobs."
            )
            free_ranged = bool(safe_ranged_pairs)
            unarmed_capable = any(
                not pawn.get("has_ranged_weapon")
                and first_number(pawn.get("sight"), 1) >= 0.65
                and first_number(pawn.get("manipulation"), 1) >= 0.65
                for pawn in fighters
            )
            if free_ranged and unarmed_capable:
                criteria["equip_ranged_weapon"] = "Equip suitable unarmed colonists with available ranged weapons before the raid advances."
            if ready_shooters:
                weak = len(ready_shooters) < len(hostile_rows)
                tired = any(first_number((welfare.get(pawn.get("id")) or {}).get("rest"), 1) < 0.4
                            or first_number((welfare.get(pawn.get("id")) or {}).get("hunger"), 1) < 0.35
                            or first_number(pawn.get("health"), 1) < 0.85 for pawn in ready_shooters)
                criteria["preemptive_strike"] = (
                    "Provoke the staging enemy with long-range shooters; they may be isolated or counterattacked. "
                    f"Shooters {len(ready_shooters)} vs enemies {len(hostile_rows)}; outnumbered={weak}; tired_or_wounded={tired}."
                )
        elif far_assault:
            if drafted:
                criteria["prepare_undrafted"] = "Assault is beyond range: eat and rest now, but risk being caught before re-drafting."
            criteria["hold_and_observe"] = (
                "Watch the approach with current orders; drafted fighters cannot eat or sleep."
                if drafted else "Watch the approach while civilians keep their current safe jobs."
            )
        if any(first_number(pawn.get("distance_to_nearest_opponent"), 9999) <= 2
               for pawn in fighters):
            criteria["engage_melee"] = (
                "Enemy is in contact: only fighters actually touching the enemy enter melee; other armed colonists keep firing. "
                "Gun-bashing sacrifices ranged fire and can be lethal against a stronger melee attacker; compare a short backstep."
            )
            if "backstep_fire" in criteria:
                criteria = {"backstep_fire": criteria.pop("backstep_fire"), **criteria}
        # A healthy melee attacker has reached an isolated, mobile gunner.
        # Holding cover or bashing it with a gun can kill the only nearby
        # defender before distant allies can cross the map. Preserve the
        # normal tactical choice when the enemy is already nearly down or a
        # shooter/melee guard is close enough to cover the contact.
        if "backstep_fire" in criteria:
            isolated_contact = any(
                pawn.get("has_ranged_weapon")
                and first_number(pawn.get("distance_to_nearest_opponent"), 9999) <= 2
                and first_number(pawn.get("moving"), 1) >= 0.7
                and not any(other.get("id") != pawn.get("id")
                            and not other.get("is_downed")
                            and first_number(other.get("distance_to_nearest_opponent"), 9999) <= 10
                            for other in fighters)
                for pawn in fighters
            )
            strong_melee_threat = any(not hostile.get("has_ranged_weapon")
                                      and first_number(hostile.get("health"), 0) >= 0.65
                                      for hostile in hostile_rows)
            if isolated_contact and strong_melee_threat:
                criteria = {"backstep_fire": (
                    "Immediately backstep the isolated gunner from a healthy melee attacker and keep firing; "
                    "distant allies cannot cover this contact yet."
                )}
        if not staging and any(first_number(pawn.get("distance_to_nearest_opponent"), 0) > 20
                               for pawn, _ in safe_ranged_pairs):
            criteria["equip_ranged_weapon"] = "Give suitable unarmed colonists nearby ranged weapons; they must survive the trip to pick them up."
        if any(
            pawn.get("tendable_now") and not pawn.get("is_downed") and not pawn.get("is_in_mental_state")
            and first_number(pawn.get("moving"), 1) >= 0.65
            and first_number(pawn.get("distance_to_nearest_opponent"), 9999) > 4
            for pawn in snapshot["combat"].get("colonists", [])
        ):
            criteria["emergency_self_tend"] = (
                "A mobile injured colonist may leave the firing line to self-tend. Close enemies can kill them "
                "during treatment; staying may cause death from bleeding, while withdrawal reduces team firepower."
            )
        if not criteria:
            criteria = {
                "hold_and_observe": "Keep civilians undrafted while monitoring the threat.",
            }
            if drafted:
                criteria["prepare_undrafted"] = "Undraft exhausted or defenseless colonists so they can seek safety."
        if any(combat_planner.is_kidnapper(row) for row in hostile_rows):
            criteria.pop("prepare_undrafted", None)
        if capabilities.combat_animals(snapshot):
            criteria["release_trained_animals"] = "Release trained healthy following animals with their master into combat. Compare allied power, enemy fire, melee danger and animal losses; this does not draft livestock."
        if capabilities.combat_animals(snapshot, released=True):
            criteria["recall_combat_animals"] = "Disable release with the master; animals resume following, though recall may not stop an attack instantly. Preserve wounded or outmatched animals."
        if combat_planner.guarded_hive_outside_contact(snapshot):
            # A generic focus-fire order repositions out-of-range shooters
            # toward its target. At a passive hive that is an attack order,
            # even when the model's text says to hold cover.
            allowed = {"civilian_retreat", "withdraw_and_regroup", "backstep_fire",
                       "prepare_undrafted", "continue_safe_colony_work", "hold_and_observe",
                       "emergency_self_tend", "equip_ranged_weapon", "equip_melee_weapon",
                       "equip_emp_weapon", "recall_combat_animals"}
            criteria = {name: description for name, description in criteria.items() if name in allowed}
            if not criteria:
                criteria["hold_and_observe"] = "Watch the guarded hive without sending colonists into its territory."
        if not any(not row.get("is_dead") and not row.get("is_downed") for row in snapshot["combat"]["hostiles"]):
            # Legacy positioning/tactics resolve Pawn targets. Native weapon
            # commands explicitly support Thing targets such as active turrets.
            criteria = {key: value for key, value in criteria.items() if key in {
                "emp_control", "smoke_advance", "mortar_reload", "mortar_counterbattery", "attack_structure"}}
            criteria["hold_and_observe"] = "Keep current orders; the active hostile structure still threatens its area."
            criteria["continue_safe_colony_work"] = "Continue work outside verified turret exposure; leave the hostile structure intact."
        return {
            "threat_action": {
                "type": "choice",
                "instructions": "Choose one feasible coordinated tactic from the live enemy weapons/jobs, pawn mobility and health, psycasts, and defenses that actually exist. Positioning is resolved by RIMAPI and any route crossing a friendly trap is rejected.",
                "criteria": criteria,
            }
        }
    if any(bool(c.get("is_drafted")) for c in snapshot["combat"]["colonists"]):
        return {
            "post_combat_action": {
                "type": "choice",
                "instructions": "The combat API reports zero hostile pawns. Return colonists to normal work unless a verified current threat requires continued drafting.",
                "criteria": {
                    "remain_drafted": "Keep the drafted state only if the current state contains concrete evidence of continuing danger.",
                    "stand_down": "Undraft colonists and resume normal colony work because the verified hostile count is zero.",
                },
            }
        }
    return {
        "colony_action": {
            "type": "choice",
            "instructions": "Select the most useful safe action now. Prefer keep_current_plan unless the state clearly supports a change.",
            "criteria": {
                "keep_current_plan": "Make no changes when the colony is stable or evidence is insufficient.",
                "prioritize_cooking": "Set Cooking to priority 1 for one healthy colonist when ready food is low.",
                "prioritize_growing": "Set Growing to priority 1 for one healthy colonist when food production needs attention.",
                "prioritize_hauling": "Set Hauling to priority 1 for one healthy colonist when general logistics should be improved.",
                "prioritize_construction": "Set Construction to priority 1 for one healthy colonist when colony development is the best focus.",
                "prioritize_cleaning": "Set Cleaning to priority 1 for one healthy colonist when no urgent production need dominates.",
            },
        }
    }


def choose_worker(colonists: list[dict[str, Any]], work: str) -> dict[str, Any] | None:
    skill_for_work = {
        "Cooking": "Cooking",
        "Growing": "Plants",
        "PlantCutting": "Plants",
        "Construction": "Construction",
        "Research": "Intellectual",
        "Hunting": "Shooting",
        "Handling": "Animals",
        "Doctor": "Medicine",
    }
    skill_name = skill_for_work.get(work)
    eligible = []
    for colonist in colonists:
        priorities = colonist.get("work_priorities") or {}
        priority = priorities.get(work)
        if active_immune_diseases(colonist) and work not in {"Patient", "PatientBedRest"}:
            continue
        if first_number(colonist.get("health")) < 0.75 or first_number(colonist.get("bleeding_rate")) > 0.0 or colonist.get("downed"):
            continue
        # A missing row is not evidence that this pawn can perform the work.
        # RIMAPI now includes zero-priority rows for capable workers so Laya
        # can explicitly re-enable those jobs without guessing capability.
        if not isinstance(priority, dict) or priority.get("disabled"):
            continue
        eligible.append(colonist)
    if not eligible:
        return None
    def score(colonist: dict[str, Any]) -> tuple[float, int]:
        skill = colonist.get("skills", {}).get(skill_name, {}) if skill_name else {}
        return (
            first_number(skill.get("level")) * 2
            + first_number(skill.get("passion"))
            + first_number(colonist.get("mood"), 0.5)
            + first_number(colonist.get("rest"), 0.5)
            + first_number(colonist.get("health")),
            int(colonist.get("id") or 0),
        )
    return max(eligible, key=score)


def decide(agent: Any, snapshot: dict[str, Any], confidence_threshold: float) -> dict[str, Any]:
    if snapshot["map"]["enemies"] > 0 and not snapshot["combat"]["available"]:
        return {
            "choice": "prepare_undrafted",
            "confidence": 0.0,
            "reason": "Combat API is unavailable, so no target can be validated; undraft instead of exhausting colonists.",
            "raw": None,
        }
    questions = make_questions(snapshot)
    question_id = next(iter(questions))
    feasible = list(questions[question_id].get("criteria", {}))
    visible_state = combat_model_context(agent, snapshot)
    choice, raw = ask_combat_choice(agent, visible_state, question_id, questions[question_id])
    raw["visible_state"] = visible_state
    answer = (raw.get("answers") or {}).get(question_id) or {}
    confidence = first_number(answer.get("confidence"))
    reason = "Laya decision"
    if choice not in feasible and feasible:
        raise ValueError(f"Laya returned infeasible combat choice {choice!r}")
    if confidence < confidence_threshold:
        reason = f"Confidence {confidence:.3f} is below threshold {confidence_threshold:.3f}"
        choice = "keep_current_plan"
    if choice not in SAFE_WORK_TYPES and choice not in COMBAT_CHOICES and choice != "keep_current_plan":
        raise ValueError(f"Unsupported combat choice {choice!r}")
    if choice in {"emp_control", "smoke_advance", "mortar_reload", "mortar_counterbattery", "attack_structure"}:
        rows = combat_planner.native_tactical_options(snapshot, choice)
        aliases = {f"n{i}": row for i, row in enumerate(rows.values())}
        criteria = {key: str(row.get("label") or key) for key, row in aliases.items()}
        effects = {key: row["effects"] for key, row in aliases.items()}
        criteria["defer"] = "Keep current jobs and ammunition; do not issue this weapon order."
        effects["defer"] = {"benefit": "Keep existing defense orders.", "risk": "The threat remains.",
                            "cost": "No new weapon/ammunition commitment.", "inaction": "Others continue their current orders.",
                            "uncertainty": "Reassess changing range, health, ammunition and targets."}
        selected, native_raw = ask_laya_choice(agent, {"option_effects": effects,
            "decision_facts": {"tactic": choice, "hostiles": len(combat_planner.live_hostiles(snapshot))}},
            "native_weapon_order", "Choose one verified actor, weapon and target with explicit costs and collateral risks, or defer.", criteria)
        raw["native_weapon_order"] = native_raw
        return {"choice": "hold_and_observe" if selected == "defer" else choice, "confidence": confidence,
                "reason": reason, "raw": raw, "native_plan": aliases.get(selected)}
    if choice == "melee_assault":
        fighters = [row for row in snapshot["combat"].get("colonists", [])
                    if not row.get("is_dead") and not row.get("is_downed") and not row.get("is_in_mental_state")]
        swords = [row for row in fighters if row.get("weapon_def") and not row.get("has_ranged_weapon")]
        guns = [row for row in fighters if row.get("has_ranged_weapon")]
        covering = [row for row in guns if combat_planner.has_clear_shot(
            row, snapshot["combat"].get("hostiles") or [])]
        if swords and guns and not covering and min(
            first_number(row.get("distance_to_nearest_opponent"), 9999) for row in swords
        ) > 12:
            confirmation = {
                "type": "choice",
                "instructions": (
                    "The sword fighter would charge without any allied gun currently in firing range. "
                    "Choose whether that immediate unsupported attack is still worth the risk, "
                    "or first bring the guns into range while the sword fighter stays with them. "
                    "Both options are valid decisions; consider enemy count, equipment, ally health and distance."
                ),
                "criteria": {
                    "charge_now": (
                        f"Attack immediately with {len(swords)} sword fighter(s); "
                        f"0/{len(guns)} guns can cover them now. The attacker may be downed before help arrives."
                    ),
                    "bring_guns_forward": (
                        f"Advance {len(guns)} shooters into range first and keep the sword fighter(s) near them; "
                        "the enemy has more time to approach or attack."
                    ),
                },
            }
            selected, support_raw = ask_combat_choice(
                agent, combat_model_context(agent, snapshot), "unsupported_charge", confirmation
            )
            raw["support_check"] = support_raw
            if selected == "bring_guns_forward":
                choice = "advance_to_range"
    selected_fighter_ids = None
    psycast_plan = None
    animal_master_id = None
    weapon_pawn_id = weapon_item_id = None
    if choice in {"release_trained_animals", "recall_combat_animals"}:
        animal_rows = capabilities.combat_animals(snapshot, released=choice == "recall_combat_animals")
        master_options = {str(a["master_pawn_id"]): "; ".join(
            f"{b.get('name')}: hp {b.get('health')}, power {b.get('combat_power')}, position {b.get('position')}"
            for b in animal_rows if b.get("master_pawn_id") == a["master_pawn_id"]) for a in animal_rows}
        selected, animal_raw = ask_laya_choice(agent, visible_state, "animal_master",
            "Choose the master and its trained group; consider damage risk and distance. A bond is not training. Animals can die in a charge.", master_options)
        if selected not in master_options:
            raise ValueError("Infeasible combat animal master")
        animal_master_id = int(selected)
        raw["animal_choice"] = animal_raw
    if choice in {"equip_ranged_weapon", "equip_melee_weapon", "equip_emp_weapon"}:
        eligible = {}
        for pawn in snapshot["combat"].get("colonists") or []:
            if pawn.get("is_downed") or pawn.get("is_dead") or pawn.get("is_in_mental_state") or pawn.get("current_job") in capabilities.CARE_JOBS:
                continue
            if choice == "equip_ranged_weapon" and pawn.get("has_ranged_weapon"):
                continue
            weapons = {key: w for key, w in capabilities.safe_weapons(snapshot, pawn).items()
                       if bool(w.get("is_ranged")) == (choice != "equip_melee_weapon")
                       and (choice != "equip_emp_weapon" or w.get("emp") or "emp" in str(w.get("def_name") or "").lower())}
            if weapons:
                eligible[str(pawn["id"])] = {"pawn": pawn, "weapons": weapons}
        if eligible:
            selected, pawn_raw = ask_laya_choice(agent, visible_state, "weapon_pawn",
                "Choose a fighter by skills, health, current weapon and pickup safety.",
                {key: f"{p['pawn'].get('name')}; shooting {p['pawn'].get('shooting_skill')}, melee {p['pawn'].get('melee_skill')}; current {capabilities.weapon_note(p['pawn'].get('weapon_info') or {})}" for key, p in eligible.items()})
            if selected not in eligible:
                raise ValueError("Infeasible weapon recipient")
            weapon_pawn_id = int(selected)
            items = eligible[selected]["weapons"]
            weapon_context = {"choice_context": {"fighter": {k: eligible[str(weapon_pawn_id)]["pawn"].get(k) for k in
                ("id", "shooting_skill", "melee_skill", "sight", "manipulation", "weapon_def")}}, "colony": visible_state}
            selected, weapon_raw = ask_laya_choice(agent, weapon_context, "weapon_item",
                "Choose an actual compatible weapon by damage, range, accuracy, AP, quality, pawn skills and enemy armor. Explosives/fire can hurt allies; EMP is specialized against machines. Price alone does not measure effectiveness.",
                {key: capabilities.weapon_note(w) for key, w in items.items()}, detailed=True)
            if selected not in items:
                raise ValueError("Infeasible weapon")
            weapon_item_id = int(selected)
            raw["weapon_choice"] = {"pawn": pawn_raw, "weapon": weapon_raw}
    if choice in {"psycast_control", "psycast_support"}:
        options = combat_planner.psycast_options(snapshot, hostile=choice == "psycast_control")
        if options:
            psy_question = {"psycast_plan": {
                "type": "choice",
                "instructions": "Choose the exact caster and ability. RIMAPI will re-check target validity, psyfocus, cooldown and neural heat before queueing a normal casting job.",
                "criteria": {key: row["summary"] for key, row in options.items()},
            }}
            selected, psy_raw = ask_combat_choice(agent, combat_model_context(agent, snapshot),
                                                  "psycast_plan", psy_question["psycast_plan"])
            if selected in options:
                psycast_plan = options[selected]
            raw["psycast"] = psy_raw
        if psycast_plan is None:
            choice = "hold_cover"

    medical_target_id = None
    if choice == "emergency_self_tend":
        patients = [pawn for pawn in snapshot["combat"].get("colonists", [])
                    if pawn.get("tendable_now") and not pawn.get("is_downed") and not pawn.get("is_in_mental_state")
                    and first_number(pawn.get("moving"), 1) >= 0.65
                    and first_number(pawn.get("distance_to_nearest_opponent"), 9999) > 4
                    ]
        if len(patients) > 1:
            medical_question = {"medical_target": {
                "type": "choice",
                "instructions": "Choose which colonist needs an immediate safe self-tend. Compare bleeding, mobility, health and enemy distance.",
                "criteria": {str(int(pawn["id"])): (
                    f"{pawn.get('name')}: health {first_number(pawn.get('health')):.2f}, "
                    f"bleeding {first_number(pawn.get('bleeding_rate')):.2f}, "
                    f"moving {first_number(pawn.get('moving'), 1):.2f}, "
                    f"nearest enemy {first_number(pawn.get('distance_to_nearest_opponent')):.0f} cells"
                ) for pawn in patients},
            }}
            selected, medical_raw = ask_combat_choice(agent, combat_model_context(agent, snapshot),
                                                      "medical_target", medical_question["medical_target"])
            medical_target_id = int(selected) if selected in medical_question["medical_target"]["criteria"] else None
            raw["medical_target"] = medical_raw
        elif patients:
            medical_target_id = int(patients[0]["id"])

    melee_role = None
    melee_roles: dict[int, str] = {}
    ranged_group_tactics = {
        "hold_cover", "focus_fire", "firing_line", "spread_out", "kite", "backstep_fire",
        "advance_to_range", "staggered_retreat", "killbox_hold", "wide_flank", "pincer",
        "counter_snipe", "siege_harass", "drop_pod_encircle",
    }
    if choice in ranged_group_tactics or choice == "coordinate_melee_roles":
        melee_fighters = [
            pawn for pawn in snapshot["combat"].get("colonists", [])
            if not pawn.get("is_dead") and not pawn.get("is_downed") and not pawn.get("is_in_mental_state")
            and pawn.get("can_fight", True) and not pawn.get("has_ranged_weapon")
        ]
        role_raw: dict[str, Any] = {}
        has_shooters = any(pawn.get("has_ranged_weapon") and not pawn.get("is_dead")
                           and not pawn.get("is_downed") and not pawn.get("is_in_mental_state")
                           and pawn.get("can_fight", True)
                           for pawn in snapshot["combat"].get("colonists", []))
        supporting_guns = [row for row in snapshot["combat"].get("colonists", [])
                           if row.get("has_ranged_weapon") and not row.get("is_dead")
                           and not row.get("is_downed") and not row.get("is_in_mental_state")
                           and row.get("can_fight", True)]
        active_enemies = [row for row in snapshot["combat"].get("hostiles", [])
                          if not row.get("is_dead") and not row.get("is_downed")]
        for pawn in melee_fighters:
            mobile = first_number(pawn.get("moving"), 1) >= 0.65
            pawn_pos = pawn.get("position") or {}
            support_gap = min((
                ((first_number(pawn_pos.get("x")) - first_number((gun.get("position") or {}).get("x"))) ** 2
                 + (first_number(pawn_pos.get("z")) - first_number((gun.get("position") or {}).get("z"))) ** 2) ** 0.5
                for gun in supporting_guns if pawn_pos and gun.get("position")
            ), default=9999.0)
            clear_guns = sum(combat_planner.has_clear_shot(gun, active_enemies) for gun in supporting_guns)
            isolated = not pawn.get("weapon_def") and has_shooters and support_gap > 12
            melee_options = {
                ("guard_shooters" if has_shooters else "melee_hold_line"):
                    (f"Regroup toward the armed allies {support_gap:.0f} cells away without drawing pursuers "
                     "out of firing range. Unarmed guards stay behind the shooters; armed guards can intercept."
                     if isolated else
                     "Stay beside the shooters; unarmed guards shelter behind them rather than charging. "
                     "Armed guards may intercept close enemies."),
            }
            if has_shooters:
                melee_options["screen_melee"] = (
                    f"Screen the armed group; they are {support_gap:.0f} cells away and {clear_guns}/{len(supporting_guns)} "
                    "can shoot now. An isolated fighter must regroup first." if isolated else
                    "Intercept enemies close to the shooters; the screen risks injury in melee."
                )
            if mobile:
                melee_options["melee_assault"] = (
                    f"Attack now; {clear_guns}/{len(supporting_guns)} guns can cover from here, "
                    f"nearest shooter {support_gap:.0f} cells away. "
                    "An unarmed fighter can be downed or killed before help arrives."
                )
                if (first_number(pawn.get("distance_to_nearest_opponent"), 9999) <= 20
                        and (not supporting_guns or (support_gap <= 30
                                 and any(first_number(gun.get("distance_to_nearest_opponent"), 9999)
                                         <= first_number(gun.get("weapon_range")) + 12
                                         for gun in supporting_guns)))):
                    melee_options["lure_enemy"] = (
                        "Draw the nearest enemy into allied range with short trap-free moves, staying close enough to keep pursuit. "
                        "If the enemy ignores the lure, the fighter may contribute no damage while allies are exposed."
                    )
                melee_options["withdraw_and_regroup"] = (
                    ("Retreat from the enemy and rejoin distant gunmen; this may save an isolated unarmed colonist, "
                     "but the enemy may follow." if isolated else
                     "Withdraw this fighter from danger. They may survive, but nearby allies lose protection.")
                )
            question_id = f"melee_role_{int(pawn['id'])}"
            melee_question = {question_id: {
                "type": "choice",
                "instructions": (
                    f"Choose the role for {pawn.get('name') or pawn['id']} only. Every other controllable fighter also receives a role this cycle. "
                    "Compare this fighter's health, armor, movement and position with the enemy count, health, weapons and ranges. "
                    "A lure helps only if attackers can shoot the pursuer; an isolated charge can kill the attacker; "
                    "retreat can save them but expose allies. No outcome is mandatory."
                ),
                "criteria": melee_options,
            }}
            role_target = {
                "id": int(pawn["id"]),
                "health": first_number(pawn.get("health")),
                "armor": first_number(pawn.get("armor_sharp")),
                "movement": first_number(pawn.get("moving"), 1),
                "distance_to_enemy": first_number(pawn.get("distance_to_nearest_opponent"), 9999),
                "weapon": pawn.get("weapon_def"),
                "nearest_gun_cells": round(support_gap),
                "guns_with_clear_shot": f"{clear_guns}/{len(supporting_guns)}",
            }
            role_state = combat_model_context(agent, snapshot, role_target=role_target, assigned_roles=melee_roles.copy())
            selected_role, prediction = ask_combat_choice(agent, role_state, question_id, melee_question[question_id])
            melee_roles[int(pawn["id"])] = selected_role if selected_role in melee_options else next(iter(melee_options))
            role_raw[question_id] = prediction
        if role_raw:
            raw["melee_roles"] = role_raw

    cover_tactic = None
    if choice == "withdraw_and_regroup":
        eligible = [
            pawn for pawn in snapshot["combat"].get("colonists", [])
            if not pawn.get("is_dead") and not pawn.get("is_downed") and not pawn.get("is_in_mental_state")
            and pawn.get("can_fight", True) and first_number(pawn.get("moving"), 1) >= 0.65
        ]
        live_hostiles = [row for row in snapshot["combat"].get("hostiles", [])
                         if not row.get("is_dead") and not row.get("is_downed")]
        if len(eligible) > 1:
            teams: dict[str, list[dict[str, Any]]] = {}
            enemy_summary = "; ".join(
                f"{row.get('kind_def') or row.get('name')} hp {first_number(row.get('health'), 1):.2f} "
                f"weapon {row.get('weapon_def') or 'natural'}"
                for row in live_hostiles[:6]
            )

            def add_team(members: list[dict[str, Any]]) -> None:
                if members:
                    key = "team_" + "_".join(str(int(pawn["id"])) for pawn in members)
                    teams[key] = members

            add_team(eligible)
            for omitted in eligible:
                add_team([pawn for pawn in eligible if pawn["id"] != omitted["id"]])
            for pawn in eligible:
                add_team([pawn])
            for first, second in combinations(eligible, 2):
                add_team([first, second])
            if len(teams) > 1:
                team_question = {"combat_team": {
                    "type": "choice",
                    "instructions": (
                        f"Choose which fighters actually withdraw against {len(live_hostiles)} active enemies. "
                        f"Enemies: {enemy_summary}. "
                        "Everyone not in the withdrawal group will receive an explicit covering combat order. "
                        "An injured fighter may die if kept in cover, but withdrawing too many can doom the others. "
                        "Withdrawing all stops the colony's fire; leaving one cover fighter may sacrifice them to save others."
                    ),
                    "criteria": {
                        key: (
                            f"Withdraw {len(members)}; "
                            f"covering: {', '.join(str(pawn.get('name') or pawn.get('id')) for pawn in eligible if pawn not in members) or 'nobody'}. "
                            + "; ".join(
                            f"{pawn.get('name')} health {first_number(pawn.get('health')):.2f}, "
                            f"pain {first_number(pawn.get('pain')):.2f}, bleed {first_number(pawn.get('bleeding_rate')):.2f}, "
                            f"move {first_number(pawn.get('moving'), 1):.2f}, "
                            f"weapon {pawn.get('weapon_label') or pawn.get('weapon_def') or 'none'}, "
                            f"conditions {pawn.get('health_conditions') or []}"
                            for pawn in members
                            )
                        )
                        for key, members in teams.items()
                    },
                }}
                selected_key, roster_raw = ask_combat_choice(agent, combat_model_context(agent, snapshot),
                                                             "combat_team", team_question["combat_team"])
                selected_fighter_ids = [int(pawn["id"]) for pawn in teams.get(selected_key, eligible)]
                raw["roster"] = roster_raw
            else:
                selected_fighter_ids = [int(pawn["id"]) for pawn in eligible]
        elif eligible:
            selected_fighter_ids = [int(eligible[0]["id"])]
        covering = [pawn for pawn in snapshot["combat"].get("colonists", [])
                    if not pawn.get("is_dead") and not pawn.get("is_downed") and not pawn.get("is_in_mental_state")
                    and int(pawn.get("id", -1)) not in set(selected_fighter_ids or [])]
        if covering:
            cover_options: dict[str, str] = {}
            if any(pawn.get("has_ranged_weapon") for pawn in covering):
                cover_options["focus_fire"] = "Cover the withdrawal with concentrated gunfire; exposed shooters may be wounded."
                cover_options["hold_cover"] = "Hold current firing positions and existing cover while others withdraw."
                if any(first_number(pawn.get("distance_to_nearest_opponent"), 9999) < 12
                       for pawn in covering):
                    cover_options["backstep_fire"] = "Backstep from close enemies and keep firing while the group withdraws."
            if any(pawn.get("weapon_def") and not pawn.get("has_ranged_weapon") for pawn in covering):
                cover_options["screen_melee"] = "Use an armed melee screen to buy time; the screen may be sacrificed."
            if any(pawn.get("weapon_def") and not pawn.get("has_ranged_weapon")
                   and first_number(pawn.get("moving"), 1) >= 0.65 for pawn in covering):
                cover_options["melee_assault"] = "Counterattack with the remaining sword fighters while the others withdraw; this risks losing the cover group."
            if len(cover_options) > 1:
                cover_question = {"cover_tactic": {"type": "choice",
                    "instructions": "Choose how the remaining fighters cover the withdrawal. Compare their equipment, health, enemy distance and the risk of losing them.",
                    "criteria": cover_options}}
                chosen_cover, cover_raw = ask_combat_choice(agent, combat_model_context(agent, snapshot),
                                                            "cover_tactic", cover_question["cover_tactic"])
                cover_tactic = chosen_cover if chosen_cover in cover_options else next(iter(cover_options))
                raw["cover"] = cover_raw
            elif cover_options:
                cover_tactic = next(iter(cover_options))
    return {
        "choice": choice, "confidence": confidence, "reason": reason, "raw": raw,
        "selected_fighter_ids": selected_fighter_ids,
        "cover_tactic": cover_tactic,
        "melee_role": melee_role,
        "melee_roles": melee_roles,
        "psycast_plan": psycast_plan,
        "medical_target_id": medical_target_id,
        "animal_master_id": animal_master_id,
        "weapon_pawn_id": weapon_pawn_id,
        "weapon_item_id": weapon_item_id,
    }


def combat_reserve_commands(snapshot: dict[str, Any], active_ids: set[int]) -> list[dict[str, Any]]:
    """Give omitted drafted fighters an explicit retreat instead of making them idle."""
    protected = combat_planner.protected_emergency_care_ids(snapshot)
    omitted = [pawn for pawn in snapshot.get("combat", {}).get("colonists", [])
               if pawn.get("id") is not None and not pawn.get("is_dead") and not pawn.get("is_in_mental_state")
               and int(pawn["id"]) not in active_ids and int(pawn["id"]) not in protected]
    target_id = combat_planner.choose_default_target(snapshot, "withdraw_and_regroup")
    if target_id is None:
        return [
            {"endpoint": "/api/v1/pawn/edit/status", "body": {"pawn_id": pawn["id"], "is_drafted": False}}
            for pawn in omitted if pawn.get("is_drafted")
        ]
    mobile = [pawn for pawn in omitted if not pawn.get("is_downed")
              and first_number(pawn.get("moving"), 1) >= 0.65
              and first_number(pawn.get("distance_to_nearest_opponent"), 9999) < 18]
    commands = []
    if mobile and target_id is not None:
        commands.append({"endpoint": "/api/v1/combat/tactic", "body": {
            "map_id": snapshot["map"]["id"], "tactic": "withdraw_and_regroup",
            "fighter_ids": [int(pawn["id"]) for pawn in mobile], "target_pawn_id": target_id,
        }})
    commands.extend(
        {"endpoint": "/api/v1/pawn/edit/status", "body": {"pawn_id": pawn["id"], "is_drafted": False}}
        for pawn in omitted if pawn not in mobile and pawn.get("is_drafted")
    )
    return commands


def melee_support_commands(snapshot: dict[str, Any], decision: dict[str, Any],
                           active_ids: set[int], target_id: int | None) -> tuple[list[dict[str, Any]], set[int]]:
    """Apply every model-assigned melee role during the same combat cycle."""
    protected = combat_planner.protected_emergency_care_ids(snapshot)
    melee = [pawn for pawn in snapshot["combat"].get("colonists", [])
             if not pawn.get("is_dead") and not pawn.get("is_downed") and not pawn.get("is_in_mental_state")
             and pawn.get("can_fight", True) and not pawn.get("has_ranged_weapon")
             and int(pawn.get("id", -1)) not in active_ids and int(pawn.get("id", -1)) not in protected]
    if not melee or target_id is None:
        return [], active_ids
    assigned_roles = decision.get("melee_roles") or {}
    default_role = "melee_hold_line" if decision.get("choice") == "coordinate_melee_roles" else "guard_shooters"
    groups: dict[str, list[dict[str, Any]]] = {}
    for pawn in melee:
        pawn_id = int(pawn["id"])
        pawn_default_role = "withdraw_and_regroup" if not pawn.get("weapon_def") else default_role
        role = str(assigned_roles.get(pawn_id) or assigned_roles.get(str(pawn_id))
                   or decision.get("melee_role") or pawn_default_role)
        if role not in {"guard_shooters", "screen_melee", "melee_assault", "melee_hold_line",
                        "lure_enemy", "withdraw_and_regroup"}:
            role = pawn_default_role
        if (role in {"melee_assault", "lure_enemy", "withdraw_and_regroup"}
                and first_number(pawn.get("moving"), 1) < 0.65):
            role = pawn_default_role
        groups.setdefault(role, []).append(pawn)
    commands = []
    for role, pawns in groups.items():
        commands.append({"endpoint": "/api/v1/combat/tactic", "body": {
            "map_id": snapshot["map"]["id"], "tactic": role,
            "fighter_ids": [int(pawn["id"]) for pawn in pawns], "target_pawn_id": target_id,
        }})
        active_ids.update(int(pawn["id"]) for pawn in pawns)
    return commands, active_ids


def plan_action(snapshot: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    choice = decision["choice"]
    if combat_planner.guarded_hive_outside_contact(snapshot) and choice in (
        set(combat_planner.TACTICS) | {
            "engage_ranged", "engage_melee", "draft_best_defender", "preemptive_strike",
            "focus_mechanoids", "focus_insects", "equip_melee_weapon", "equip_emp_weapon",
        }
    ) - {"stand_down", "withdraw_and_regroup", "civilian_retreat", "backstep_fire",
         "equip_melee_weapon", "equip_emp_weapon"}:
        return {"kind": "noop", "description": "Avoid advancing into a passive guarded hive"}
    resume_command = None
    if snapshot["map"]["enemies"] > 0 and snapshot["game"].get("is_paused"):
        resume_command = {"endpoint": "/api/v1/game/speed", "query": {"speed": 1}}
    if choice in {"emp_control", "smoke_advance", "mortar_reload", "mortar_counterbattery", "attack_structure"}:
        selected = decision.get("native_plan")
        if not isinstance(selected, dict) or selected not in combat_planner.native_tactical_options(snapshot, choice).values():
            return {"kind": "noop", "description": "Native weapon/target choice changed; request a new decision"}
        body = {"map_id": snapshot["map"]["id"], "tactic": choice,
                "fighter_ids": [selected["fighter_id"]], "target_pawn_id": selected["target_id"],
                "defense_building_id": selected.get("defense_building_id", 0)}
        commands = [{"endpoint": "/api/v1/combat/tactic", "body": body}]
        if resume_command:
            commands.append(resume_command)
        return {"kind": "commands", "description": selected.get("label") or choice, "commands": commands}
    if choice == "keep_current_plan":
        return {"kind": "noop", "description": "Keep current priorities"}
    if choice == "continue_safe_colony_work":
        return {"kind": "noop", "description": "Continue safe colony work while monitoring distant hostiles"}
    if choice == "hold_and_observe" and resume_command:
        return {
            "kind": "commands",
            "description": "Resume at normal speed and observe the threat",
            "commands": [resume_command],
        }
    if choice in {"hold_and_observe", "remain_drafted"}:
        return {"kind": "noop", "description": choice.replace("_", " ")}
    if choice in {"release_trained_animals", "recall_combat_animals"}:
        master_id = decision.get("animal_master_id")
        animals = capabilities.combat_animals(snapshot, released=choice == "recall_combat_animals")
        if master_id not in {a.get("master_pawn_id") for a in animals}:
            return {"kind": "noop", "description": "No verified trained animal group and master"}
        if choice == "release_trained_animals" and combat_planner.guarded_hive_outside_contact(snapshot):
            return {"kind": "noop", "description": "No animal charge into a guarded passive hive"}
        commands = []
        if choice == "release_trained_animals":
            commands.append({"endpoint": "/api/v1/pawn/edit/status", "body": {"pawn_id": master_id, "is_drafted": True}})
        commands.append({"endpoint": "/api/v1/combat/animals/release", "body": {
            "map_id": snapshot["map"]["id"], "master_pawn_id": master_id, "release": choice == "release_trained_animals"}})
        if resume_command:
            commands.append(resume_command)
        return {"kind": "commands", "description": choice.replace("_", " "), "commands": commands}
    if choice == "stand_down":
        drafted = [c for c in snapshot["combat"]["colonists"] if c.get("is_drafted")]
        commands = [
            {"endpoint": "/api/v1/pawn/edit/status", "body": {"pawn_id": c["id"], "is_drafted": False}}
            for c in drafted
        ]
        for master in {a.get("master_pawn_id") for a in snapshot["combat"].get("colony_animals") or snapshot.get("animals") or [] if a.get("animals_released")}:
            if master:
                commands.insert(0, {"endpoint": "/api/v1/combat/animals/release", "body": {"map_id": snapshot["map"]["id"], "master_pawn_id": master, "release": False}})
        if snapshot["game"].get("is_paused"):
            commands.append({"endpoint": "/api/v1/game/speed", "query": {"speed": 1}})
        return {
            "kind": "commands",
            "description": f"Undraft {len(drafted)} colonist(s)",
            "commands": commands,
        }
    if choice == "emergency_self_tend":
        patient_id = decision.get("medical_target_id")
        patient = next((pawn for pawn in snapshot["combat"].get("colonists", [])
                        if pawn.get("id") == patient_id and pawn.get("tendable_now")
                        and not pawn.get("is_downed") and not pawn.get("is_in_mental_state")
                        and first_number(pawn.get("moving"), 1) >= 0.65
                        and first_number(pawn.get("distance_to_nearest_opponent"), 9999) > 4), None)
        if patient is None:
            return {"kind": "noop", "description": "No mobile self-tend patient remains"}
        commands = []
        if patient.get("is_drafted"):
            commands.append({"endpoint": "/api/v1/pawn/edit/status", "body": {
                "pawn_id": patient_id, "is_drafted": False,
            }})
        commands.append({"endpoint": "/api/v1/pawn/medical/tend", "body": {
            "patient_pawn_id": patient_id, "doctor_pawn_id": patient_id, "self_tend": True,
        }})
        if resume_command:
            commands.append(resume_command)
        return {"kind": "commands", "description": f"Emergency self-tend: {patient.get('name')}",
                "commands": commands}
    if choice == "withdraw_and_regroup":
        protected = combat_planner.protected_emergency_care_ids(snapshot)
        colonists = [pawn for pawn in snapshot["combat"].get("colonists", [])
                     if not pawn.get("is_dead") and not pawn.get("is_downed")
                     and not pawn.get("is_in_mental_state") and pawn.get("can_fight", True)
                     and pawn.get("id") not in protected]
        target_id = combat_planner.choose_default_target(snapshot, choice)
        if target_id is None:
            return {"kind": "noop", "description": "No active enemy remains to withdraw from"}
        selected = decision.get("selected_fighter_ids")
        withdrawing_ids = set(map(int, selected)) if selected is not None else {
            int(pawn["id"]) for pawn in colonists if first_number(pawn.get("moving"), 1) >= 0.65
        }
        withdrawing = [pawn for pawn in colonists if int(pawn["id"]) in withdrawing_ids
                       and first_number(pawn.get("moving"), 1) >= 0.65]
        covering = [pawn for pawn in colonists if int(pawn["id"]) not in withdrawing_ids]
        commands: list[dict[str, Any]] = []

        def order(tactic: str, pawns: list[dict[str, Any]]) -> None:
            if pawns:
                commands.append({"endpoint": "/api/v1/combat/tactic", "body": {
                    "map_id": snapshot["map"]["id"], "tactic": tactic,
                    "fighter_ids": [int(pawn["id"]) for pawn in pawns],
                    "target_pawn_id": target_id,
                }})

        order("withdraw_and_regroup", withdrawing)
        cover_tactic = str(decision.get("cover_tactic") or "")
        armed_cover = [pawn for pawn in covering if pawn.get("weapon_def")]
        ranged_cover = [pawn for pawn in armed_cover if pawn.get("has_ranged_weapon")]
        melee_cover = [pawn for pawn in armed_cover if not pawn.get("has_ranged_weapon")]
        if cover_tactic in {"screen_melee", "melee_assault"}:
            if cover_tactic == "melee_assault":
                mobile_melee = [pawn for pawn in melee_cover if first_number(pawn.get("moving"), 1) >= 0.65]
                order("melee_assault", mobile_melee)
                order("guard_shooters", [pawn for pawn in melee_cover if pawn not in mobile_melee])
            else:
                order("screen_melee", melee_cover)
            order("focus_fire", ranged_cover)
        else:
            active_tactic = cover_tactic if cover_tactic in {"focus_fire", "hold_cover", "backstep_fire"} else "focus_fire"
            mobile_ranged = [pawn for pawn in ranged_cover if first_number(pawn.get("moving"), 1) >= 0.65]
            if active_tactic == "backstep_fire":
                order("backstep_fire", mobile_ranged)
                order("focus_fire", [pawn for pawn in ranged_cover if pawn not in mobile_ranged])
            else:
                order(active_tactic, ranged_cover)
            order("screen_melee", melee_cover)
        order("civilian_retreat", [pawn for pawn in covering if not pawn.get("weapon_def")
                                   and first_number(pawn.get("moving"), 1) >= 0.65])
        commands.extend({"endpoint": "/api/v1/pawn/edit/status", "body": {
            "pawn_id": pawn["id"], "is_drafted": False,
        }} for pawn in covering if not pawn.get("weapon_def") and pawn.get("is_drafted")
                        and first_number(pawn.get("moving"), 1) < 0.65)
        if resume_command:
            commands.append(resume_command)
        return {"kind": "commands" if commands else "noop",
                "description": f"Regroup {len(withdrawing)} fighter(s), cover with {len(covering)}",
                "commands": commands}
    if choice == "coordinate_melee_roles":
        protected = combat_planner.protected_emergency_care_ids(snapshot)
        target_id = combat_planner.choose_default_target(snapshot, choice)
        if target_id is None:
            return {"kind": "noop", "description": "No active enemy remains for a coordinated melee plan"}
        shooters = [pawn for pawn in snapshot["combat"].get("colonists", [])
                    if not pawn.get("is_dead") and not pawn.get("is_downed")
                    and not pawn.get("is_in_mental_state") and pawn.get("can_fight", True)
                    and pawn.get("id") not in protected
                    and pawn.get("has_ranged_weapon")
                    and first_number(pawn.get("manipulation"), 1) >= 0.65
                    and first_number(pawn.get("sight"), 1) >= 0.65]
        active_ids = {int(pawn["id"]) for pawn in shooters}
        melee_commands, active_ids = melee_support_commands(snapshot, decision, active_ids, target_id)
        commands = combat_reserve_commands(snapshot, active_ids)
        if shooters:
            commands.append({"endpoint": "/api/v1/combat/tactic", "body": {
                "map_id": snapshot["map"]["id"], "tactic": "focus_fire",
                "fighter_ids": [int(pawn["id"]) for pawn in shooters], "target_pawn_id": target_id,
            }})
        commands.extend(melee_commands)
        if resume_command:
            commands.append(resume_command)
        return {"kind": "commands" if commands else "noop",
                "description": f"Individual melee roles for {len(decision.get('melee_roles') or {})} fighter(s)",
                "commands": commands}
    if choice in combat_planner.TACTICS:
        protected = combat_planner.protected_emergency_care_ids(snapshot)
        choke_door_id = combat_planner.insect_choke_door(snapshot) if choice == "infestation_choke" else None
        if choice == "infestation_choke" and choke_door_id is None:
            return plan_action(snapshot, {**decision, "choice": "withdraw_and_regroup"})
        fighters = [
            pawn for pawn in snapshot["combat"].get("colonists", [])
            if not pawn.get("is_dead") and not pawn.get("is_downed")
            and not pawn.get("is_in_mental_state")
            and (choice == "civilian_retreat" or pawn.get("can_fight", True))
            and pawn.get("id") not in protected
        ]
        selected = decision.get("selected_fighter_ids")
        if selected is not None:
            selected_set = set(map(int, selected))
            fighters = [pawn for pawn in fighters if int(pawn.get("id", -1)) in selected_set]
        ranged_tactics = {
            "hold_cover", "focus_fire", "intercept_kidnapper", "firing_line", "spread_out", "kite", "backstep_fire", "advance_to_range",
            "staggered_retreat", "killbox_hold", "wide_flank", "pincer",
            "counter_snipe", "siege_harass", "drop_pod_encircle",
        }
        melee_tactics = {"melee_assault", "melee_hold_line", "screen_melee", "melee_block", "door_defense", "infestation_choke", "rush_ranged"}
        if choice in ranged_tactics:
            fighters = [pawn for pawn in fighters if pawn.get("has_ranged_weapon") and first_number(pawn.get("manipulation"), 1) >= 0.65 and first_number(pawn.get("sight"), 1) >= 0.65]
            if choice == "counter_snipe":
                fighters = [pawn for pawn in fighters if first_number(pawn.get("weapon_range")) >= 30]
        elif choice in melee_tactics:
            fighters = [pawn for pawn in fighters if pawn.get("weapon_def") and not pawn.get("has_ranged_weapon")
                        and first_number(pawn.get("moving"), 1) >= (0.65 if choice in {"melee_assault", "melee_hold_line", "screen_melee"} else 0.8)
                        and (choice in {"melee_assault", "melee_hold_line", "screen_melee"} or first_number(pawn.get("armor_sharp")) >= 0.4)]
        elif choice == "civilian_retreat":
            fighters = [pawn for pawn in fighters if first_number(pawn.get("moving"), 1) >= 0.65
                        and (not pawn.get("can_fight", True) or not pawn.get("weapon_def"))
                        and combat_planner.errand_exposed(snapshot, pawn.get("position"))]
        elif choice == "withdraw_and_regroup":
            fighters = [pawn for pawn in fighters if first_number(pawn.get("moving"), 1) >= 0.65]
        if choice == "backstep_fire":
            fighters = [pawn for pawn in fighters if first_number(pawn.get("moving"), 1) >= 0.65]
        if choice == "kite":
            target_id = combat_planner.choose_default_target(snapshot, choice)
            lures = [pawn for pawn in fighters
                     if first_number(pawn.get("moving"), 1) >= 0.85
                     and first_number(pawn.get("distance_to_nearest_opponent"), 9999) <= 16]
            pairs = [
                (lure, [pawn for pawn in fighters
                        if pawn["id"] != lure["id"]
                        and first_number(pawn.get("distance_to_nearest_opponent"), 9999)
                        <= first_number(pawn.get("weapon_range")) + 12])
                for lure in lures
            ]
            pairs = [(lure, support) for lure, support in pairs if support]
            if not pairs:
                # A partial roster must never turn coordinated kiting into a
                # solo retreat that leaves the firing line exposed.
                return plan_action(snapshot, {**decision, "choice": "focus_fire"})
            lure, support = max(pairs, key=lambda pair: (
                first_number(pair[0].get("moving"), 1),
                first_number(pair[0].get("health")),
                len(pair[1]),
            ))
            active_ids = {int(lure["id"])} | {int(pawn["id"]) for pawn in support}
            melee_commands, active_ids = melee_support_commands(snapshot, decision, active_ids, target_id)
            commands = combat_reserve_commands(snapshot, active_ids) + [
                {"endpoint": "/api/v1/combat/tactic", "body": {
                    "map_id": snapshot["map"]["id"], "tactic": "advance_to_range",
                    "fighter_ids": [int(pawn["id"]) for pawn in support],
                    "target_pawn_id": target_id,
                }},
                {"endpoint": "/api/v1/combat/tactic", "body": {
                    "map_id": snapshot["map"]["id"], "tactic": "kite",
                    "fighter_ids": [int(lure["id"])],
                    "target_pawn_id": target_id,
                }},
            ] + melee_commands
            if resume_command:
                commands.append(resume_command)
            return {"kind": "commands", "description": f"Kite with {lure.get('name')}; {len(support)} covering shooter(s)",
                    "commands": commands}
        target_id = combat_planner.choose_default_target(snapshot, choice)
        active_ids = {int(pawn["id"]) for pawn in fighters}
        melee_commands = []
        if choice in ranged_tactics:
            melee_commands, active_ids = melee_support_commands(snapshot, decision, active_ids, target_id)
        elif choice in melee_tactics:
            covering_shooters = [pawn for pawn in snapshot["combat"].get("colonists", [])
                                if not pawn.get("is_dead") and not pawn.get("is_downed")
                                and not pawn.get("is_in_mental_state") and pawn.get("can_fight", True)
                                and pawn.get("id") not in protected
                                and pawn.get("has_ranged_weapon")
                                and first_number(pawn.get("manipulation"), 1) >= 0.65
                                and first_number(pawn.get("sight"), 1) >= 0.65]
            if covering_shooters and target_id is not None:
                groups = [("focus_fire", covering_shooters)]
                if choice == "infestation_choke":
                    live_enemies = combat_planner.live_hostiles(snapshot)
                    ready = [pawn for pawn in covering_shooters
                             if combat_planner.has_clear_shot(pawn, live_enemies)]
                    groups = [("focus_fire", ready), ("fallback_line", [
                        pawn for pawn in covering_shooters if pawn not in ready])]
                for support_tactic, support_pawns in groups:
                    if not support_pawns:
                        continue
                    support_body = {"map_id": snapshot["map"]["id"], "tactic": support_tactic,
                                    "fighter_ids": [int(pawn["id"]) for pawn in support_pawns],
                                    "target_pawn_id": target_id}
                    if choice == "infestation_choke":
                        support_body["defense_building_id"] = choke_door_id
                    melee_commands.append({"endpoint": "/api/v1/combat/tactic", "body": support_body})
                active_ids.update(int(pawn["id"]) for pawn in covering_shooters)
        reserve_commands = [] if choice in {"psycast_control", "psycast_support"} else combat_reserve_commands(
            snapshot, active_ids
        )
        if not fighters:
            commands = reserve_commands + melee_commands + ([resume_command] if resume_command else [])
            return {"kind": "commands", "description": "Withdraw vulnerable fighters", "commands": commands} if commands else {
                "kind": "noop", "description": "No healthy fighter was selected for the tactic"
            }
        def already_shooting(pawn: dict[str, Any]) -> bool:
            if (not pawn.get("is_drafted") or pawn.get("current_job") != "AttackStatic"
                    or pawn.get("current_job_target_id") != target_id):
                return False
            shootable = pawn.get("shootable_opponent_ids")
            if shootable is not None:
                return target_id in {int(opponent_id) for opponent_id in shootable}
            return (first_number(pawn.get("distance_to_nearest_opponent"), 9999)
                    <= first_number(pawn.get("weapon_range")))

        if choice == "focus_fire" and all(already_shooting(pawn) for pawn in fighters):
            commands = reserve_commands + melee_commands + ([resume_command] if resume_command else [])
            if commands:
                return {"kind": "commands", "description": "Continue focus fire with simultaneous support", "commands": commands}
            return {"kind": "noop", "description": "Existing focus-fire order is still active"}
        body: dict[str, Any] = {
            "map_id": snapshot["map"]["id"],
            "tactic": choice,
            "fighter_ids": [int(pawn["id"]) for pawn in fighters],
            "target_pawn_id": target_id,
        }
        if choke_door_id is not None:
            body["defense_building_id"] = choke_door_id
        psycast = decision.get("psycast_plan") or {}
        if psycast:
            body.update({
                "psycaster_pawn_id": int(psycast["pawn_id"]),
                "ability_def_name": str(psycast["def_name"]),
            })
            if choice == "psycast_control":
                body["ability_target_pawn_id"] = target_id
            else:
                allies = [pawn for pawn in snapshot["combat"].get("colonists", []) if not pawn.get("is_dead")]
                if allies:
                    body["ability_target_pawn_id"] = int(min(allies, key=lambda pawn: first_number(pawn.get("health"), 1))["id"])
        commands = reserve_commands + [{"endpoint": "/api/v1/combat/tactic", "body": body}] + melee_commands
        if resume_command:
            commands.append(resume_command)
        return {
            "kind": "commands",
            "description": f"{combat_planner.TACTICS[choice]['label']}: {len(fighters)} fighter(s)",
            "commands": commands,
        }
    if choice == "prepare_undrafted":
        drafted = [c for c in snapshot["combat"]["colonists"] if c.get("is_drafted")]
        if not drafted:
            return {"kind": "noop", "description": "No colonist remains drafted"}
        commands = [
            {"endpoint": "/api/v1/pawn/edit/status", "body": {"pawn_id": c["id"], "is_drafted": False}}
            for c in drafted
        ]
        if resume_command:
            commands.append(resume_command)
        return {
            "kind": "commands",
            "description": f"Raid preparation: undraft {len(drafted)} colonist(s), restore needs, and monitor movement",
            "commands": commands,
        }
    if choice in {"engage_ranged", "engage_melee", "draft_best_defender", "equip_ranged_weapon", "equip_melee_weapon", "preemptive_strike", "equip_emp_weapon", "focus_mechanoids", "focus_insects"}:
        protected = combat_planner.protected_emergency_care_ids(snapshot)
        fighters = [
            c for c in snapshot["combat"]["colonists"]
            if not c.get("is_dead") and not c.get("is_downed")
            and not c.get("is_in_mental_state") and c.get("can_fight", True)
            and c.get("id") not in protected
        ]
        if decision.get("selected_fighter_ids") is not None:
            selected = set(map(int, decision.get("selected_fighter_ids") or []))
            fighters = [pawn for pawn in fighters if int(pawn.get("id", -1)) in selected]
        if choice in {"equip_ranged_weapon", "equip_emp_weapon"}:
            fighters = [pawn for pawn in fighters if first_number(pawn.get("sight"), 1) >= 0.65
                        and first_number(pawn.get("manipulation"), 1) >= 0.65]
        hostiles = [h for h in snapshot["combat"]["hostiles"] if not h.get("is_dead") and not h.get("is_downed")]
        if not fighters or not hostiles:
            commands = combat_reserve_commands(snapshot, set()) + ([resume_command] if resume_command else [])
            return {"kind": "commands", "description": "Withdraw vulnerable fighters", "commands": commands} if commands else {
                "kind": "noop", "description": "No eligible fighter or hostile target"
            }
        ranged = choice in {"engage_ranged", "equip_ranged_weapon", "preemptive_strike", "equip_emp_weapon", "focus_mechanoids", "focus_insects"}
        if ranged and choice not in {"equip_ranged_weapon", "equip_emp_weapon"}:
            armed = [c for c in fighters if c.get("has_ranged_weapon")]
            if armed:
                fighters = armed
        if choice == "preemptive_strike":
            fighters = [c for c in fighters if c.get("has_ranged_weapon") and first_number(c.get("weapon_range")) >= 25 and first_number(c.get("moving"), 1) >= 0.8]
            if not fighters:
                return {"kind": "noop", "description": "No mobile long-range striker is available"}
        reserve_commands = combat_reserve_commands(snapshot, {int(pawn["id"]) for pawn in fighters})
        ranked_fighters = sorted(
            fighters,
            key=lambda c: (
                first_number(c.get("shooting_skill") if ranged else c.get("melee_skill")),
                first_number(c.get("health")),
                -first_number(c.get("distance_to_nearest_opponent"), 9999),
            ),
            reverse=True,
        )
        actor = ranked_fighters[0]
        needs_weapon = choice in {"equip_ranged_weapon", "equip_melee_weapon", "equip_emp_weapon"} or (
            choice == "engage_ranged" and not actor.get("has_ranged_weapon")
        )
        if needs_weapon:
            weapons = [
                w for w in snapshot["combat"].get("available_weapons", [])
                if bool(w.get("is_ranged")) == ranged
            ]
            if choice == "equip_emp_weapon":
                weapons = [
                    w for w in weapons
                    if w.get("emp") or "emp" in (str(w.get("def_name") or "") + " " + str(w.get("label") or "")).lower()
                ]
            if not weapons:
                return {"kind": "noop", "description": "No suitable free weapon is available"}
            ax = first_number((actor.get("position") or {}).get("x"))
            az = first_number((actor.get("position") or {}).get("z"))
            if choice == "equip_ranged_weapon":
                unarmed = [pawn for pawn in ranked_fighters if not pawn.get("has_ranged_weapon")]
            elif choice == "equip_emp_weapon":
                unarmed = [pawn for pawn in ranked_fighters if not (pawn.get("weapon_info") or {}).get("emp")
                           and "emp" not in str(pawn.get("weapon_def") or "").lower()]
            else:
                unarmed = ranked_fighters
            commands: list[dict[str, Any]] = []
            assignments: list[str] = []
            remaining = list(weapons)
            for defender in unarmed:
                safe_weapons = [weapon for weapon in remaining if not combat_planner.errand_exposed(
                    snapshot, weapon.get("position"), defender.get("position")) and capabilities.weapon_compatible(defender, weapon)]
                if decision.get("weapon_pawn_id") is not None:
                    if defender["id"] != decision["weapon_pawn_id"]:
                        continue
                    safe_weapons = [w for w in safe_weapons if w["id"] == decision.get("weapon_item_id")]
                if not safe_weapons:
                    continue
                dx = first_number((defender.get("position") or {}).get("x"))
                dz = first_number((defender.get("position") or {}).get("z"))
                weapon = max(safe_weapons, key=lambda w: capabilities.weapon_score(defender, w,
                    first_number(defender.get("distance_to_nearest_opponent"), 20)))
                remaining.remove(weapon)
                if weapon.get("is_forbidden"):
                    commands.append({
                        "endpoint": "/api/v1/things/set-forbidden",
                        "body": {"thing_ids": [weapon["id"]], "map_id": snapshot["map"]["id"], "forbidden": False},
                    })
                commands.append({
                    "endpoint": "/api/v1/pawn/job",
                    "body": {"pawn_id": defender["id"], "job_def": "Equip", "target_thing_id": weapon["id"]},
                })
                assignments.append(f"{defender.get('name')} -> {weapon.get('label')}")
            if not assignments:
                return {"kind": "noop", "description": "No suitable unarmed colonist still needs this weapon"}
            if resume_command:
                commands.append(resume_command)
            return {
                "kind": "commands",
                "description": f"{choice}: " + "; ".join(assignments),
                "commands": commands,
            }
        ax = first_number((actor.get("position") or {}).get("x"))
        az = first_number((actor.get("position") or {}).get("z"))
        target_pool = hostiles
        if choice == "focus_mechanoids":
            tokens = ("mech", "scyther", "lancer", "centipede", "pikeman", "militor", "tesseron", "termite")
            target_pool = [h for h in hostiles if any(t in (str(h.get("name")) + str(h.get("kind_def")) + str(h.get("faction"))).lower() for t in tokens)] or hostiles
        elif choice == "focus_insects":
            tokens = ("insect", "megaspider", "spelopede", "megascarab")
            target_pool = [h for h in hostiles if any(t in (str(h.get("name")) + str(h.get("kind_def")) + str(h.get("faction"))).lower() for t in tokens)] or hostiles
        target = min(
            target_pool,
            key=lambda h: (
                first_number((h.get("position") or {}).get("x")) - ax
            ) ** 2 + (
                first_number((h.get("position") or {}).get("z")) - az
            ) ** 2,
        )
        if choice == "engage_melee":
            contact = [pawn for pawn in ranked_fighters
                       if first_number(pawn.get("distance_to_nearest_opponent"), 9999) <= 2]
            support = [pawn for pawn in ranked_fighters
                       if pawn not in contact and pawn.get("has_ranged_weapon")]
            if not contact:
                return {"kind": "noop", "description": "No fighter remains in melee contact"}
            commands = reserve_commands + [
                {"endpoint": "/api/v1/pawn/edit/status", "body": {"pawn_id": pawn["id"], "is_drafted": True}}
                for pawn in contact
            ] + [
                {"endpoint": "/api/v1/pawn/job", "body": {
                    "pawn_id": pawn["id"], "job_def": "AttackMelee", "target_thing_id": target["id"],
                }} for pawn in contact
            ]
            if support:
                commands.append({"endpoint": "/api/v1/combat/tactic", "body": {
                    "map_id": snapshot["map"]["id"], "tactic": "focus_fire",
                    "fighter_ids": [int(pawn["id"]) for pawn in support],
                    "target_pawn_id": int(target["id"]),
                }})
            if resume_command:
                commands.append(resume_command)
            return {"kind": "commands", "description": (
                f"Melee contact: {', '.join(str(p.get('name')) for p in contact)}; "
                f"covering shooters: {', '.join(str(p.get('name')) for p in support) or 'none'}"
            ), "commands": commands}
        if choice == "preemptive_strike":
            if all(
                pawn.get("is_drafted") and pawn.get("current_job") == "AttackStatic"
                and pawn.get("current_job_target_id") == target["id"] for pawn in ranked_fighters
            ):
                commands = reserve_commands + ([resume_command] if resume_command else [])
                if commands:
                    return {"kind": "commands", "description": "Continue strike; withdraw reserves", "commands": commands}
                return {"kind": "noop", "description": "Existing strike is still in progress"}
            commands = reserve_commands + [{"endpoint": "/api/v1/combat/tactic", "body": {
                "map_id": snapshot["map"]["id"],
                "tactic": "preemptive_strike",
                "fighter_ids": [int(pawn["id"]) for pawn in ranked_fighters],
                "target_pawn_id": int(target["id"]),
            }}]
            if resume_command:
                commands.append(resume_command)
            return {"kind": "commands", "description": f"Coordinated advance to firing range: {len(ranked_fighters)} shooters", "commands": commands}
        if choice in {"engage_ranged", "preemptive_strike", "focus_mechanoids", "focus_insects"}:
            attackers = [pawn for pawn in ranked_fighters if pawn.get("has_ranged_weapon")]
        elif choice == "engage_melee":
            attackers = ranked_fighters
        else:
            attackers = ranked_fighters
        if choice in {"engage_ranged", "preemptive_strike"}:
            attackers = [pawn for pawn in attackers if not (
                pawn.get("is_drafted") and pawn.get("current_job") == "AttackStatic"
                and pawn.get("current_job_target_id") == target["id"]
            )]
            if not attackers:
                commands = reserve_commands + ([resume_command] if resume_command else [])
                if commands:
                    return {"kind": "commands", "description": "Continue attack; withdraw reserves", "commands": commands}
                return {"kind": "noop", "description": "Existing attack is still in progress"}
        commands = reserve_commands + [
            {"endpoint": "/api/v1/pawn/edit/status", "body": {"pawn_id": pawn["id"], "is_drafted": True}}
            for pawn in attackers
        ]
        if choice != "draft_best_defender":
            commands.extend(
                {
                    "endpoint": "/api/v1/pawn/job",
                    "body": {
                        "pawn_id": pawn["id"],
                        "job_def": "AttackStatic" if ranged and pawn.get("has_ranged_weapon") else "AttackMelee",
                        "target_thing_id": target["id"],
                    },
                }
                for pawn in attackers
            )
        if resume_command:
            commands.append(resume_command)
        return {
            "kind": "commands",
            "description": f"{choice}: {', '.join(str(p.get('name')) for p in attackers)} -> {target.get('name')}",
            "commands": commands,
        }
    work = SAFE_WORK_TYPES[choice]
    target = choose_worker(snapshot["colonists"], work)
    if target is None:
        return {"kind": "noop", "description": "No healthy colonist is eligible for a priority change"}
    return {
        "kind": "work_priority",
        "description": f"Set {work}=1 for {target['name']} (id={target['id']})",
        "body": {"id": target["id"], "work": work, "priority": 1},
    }


def apply_action(client: RimApiClient, action: dict[str, Any]) -> Any:
    if action["kind"] == "noop":
        return {"applied": False, "reason": action["description"]}
    if action["kind"] == "commands":
        responses = []
        for command in action["commands"]:
            try:
                responses.append(client.post(command["endpoint"], query=command.get("query"), body=command.get("body")))
            except RimApiError as error:
                # At 3x a fighter can kill or move the target between the
                # combat snapshot and this job. Replan from the next snapshot
                # instead of putting the whole director into error backoff.
                detail = str(error)
                if (command["endpoint"] == "/api/v1/pawn/job"
                        and (command.get("body") or {}).get("target_thing_id") is not None
                        and "HTTP 404" in detail
                        and "Target thing not found on the worker's map" in detail):
                    return {"applied": bool(responses), "responses": responses,
                            "stale_target": True, "reason": detail}
                raise
        return {"applied": bool(responses), "responses": responses}
    if action["kind"] == "work_priority":
        response = client.post("/api/v1/colonist/work-priority", body=action["body"])
        return {"applied": True, "response": response}
    raise RimApiError(f"Blocked unknown action kind: {action['kind']}")


def append_log(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
    for attempt in range(8):
        try:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
            return
        except PermissionError:
            # Windows readers can briefly hold a sharing lock while the GUI
            # tails the history. A missed log line must not kill the director.
            time.sleep(0.08 * (attempt + 1))
    spill = path.with_name(path.stem + ".spill.jsonl")
    try:
        with spill.open("a", encoding="utf-8") as handle:
            handle.write(line)
        print(f"Primary decision log is locked; record saved to {spill}", file=sys.stderr, flush=True)
    except OSError as exc:
        print(f"Decision log unavailable at {path} and {spill}: {exc}", file=sys.stderr, flush=True)


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


class SafeDecisionAgent:
    """Never send a meaningless single-option question into Laya.

    Laya's decision head compares alternatives and requires at least two marker
    positions. A one-option question is not a decision, so it is resolved
    deterministically here while every genuine choice still goes to the model.
    Keeping this guard around the loaded agent protects every current and future
    caller, including nested event, combat and architecture questions.
    """

    def __init__(self, inner: Any) -> None:
        self.inner = inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    @staticmethod
    def _options(question: dict[str, Any]) -> list[Any]:
        kind = str(question.get("type") or "")
        criteria = question.get("criteria")
        if kind == "choice":
            if isinstance(criteria, dict):
                return list(criteria)
            if isinstance(criteria, list):
                return list(criteria)
        if kind == "score" and isinstance(criteria, list):
            return list(range(len(criteria)))
        return []

    @staticmethod
    def _deterministic_answer(question: dict[str, Any], option: Any) -> dict[str, Any]:
        if question.get("type") == "score":
            criteria = list(question.get("criteria") or [])
            return {
                "type": "score",
                "score": 0.0,
                "legend": {str(index): value for index, value in enumerate(criteria)},
                "probabilities": {"0": 1.0},
                "confidence": 1.0,
                "action": {"act_probability": 1.0},
                "resolved_without_model": True,
            }
        return {
            "type": "choice",
            "choice": str(option),
            "probabilities": {str(option): 1.0},
            "confidence": 1.0,
            "action": {"act_probability": 1.0},
            "resolved_without_model": True,
        }

    def predict(self, state: Any, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        model_questions: dict[str, dict[str, Any]] = {}
        answers: dict[str, Any] = {}
        for question_id, question in questions.items():
            options = self._options(question)
            if question.get("type") in {"choice", "score"} and not options:
                raise ValueError(f"Decision question {question_id!r} has no feasible options")
            if len(options) == 1:
                answers[question_id] = self._deterministic_answer(question, options[0])
            else:
                model_questions[question_id] = question

        model_result: dict[str, Any] = {}
        if model_questions:
            model_result = self.inner.predict(state, model_questions)
            answers.update(model_result.get("answers") or {})
        usage = dict(model_result.get("usage") or {})
        usage.setdefault("input_tokens", 0)
        usage.setdefault("output_tokens", 0)
        return {
            **model_result,
            "model": model_result.get("model") or "laya-deterministic-guard",
            "answers": answers,
            "usage": usage,
        }


def resolve_model_source(model: str) -> str:
    if model != DEFAULT_MODEL:
        return model
    else:
        # The public repository bundles several optional checkpoints. Downloading
        # every file on each startup can hang even after the root model is cached.
        from huggingface_hub import snapshot_download

        needed = ["model.safetensors", "rl_agent_config.json", "encoder/*", "tokenizer/*"]
        def complete(path: str) -> bool:
            root = Path(path)
            return all((root / name).is_file() for name in (
                "model.safetensors", "rl_agent_config.json", "encoder/config.json", "tokenizer/tokenizer.json"
            ))
        model_source = model
        try:
            cached = snapshot_download(model, allow_patterns=needed, local_files_only=True)
            if complete(cached):
                model_source = cached
        except OSError:
            pass
        if model_source == model:
            try:
                model_source = snapshot_download(model, allow_patterns=needed)
            except Exception as exc:
                raise RuntimeError(
                    "Laya model is not cached and its first download failed. Check the Internet connection and try again."
                ) from exc
            if not complete(model_source):
                raise RuntimeError("The Laya download is incomplete. Check disk space and try again.")
        return model_source


def load_agent(model: str, device: str) -> Any:
    try:
        import torch
    except ModuleNotFoundError:
        torch = None  # Lightweight clients can load a mocked or remote agent.
    if torch is not None:
        # A 20-thread CPU pool saturated the host during each short decision.
        cpu_threads = max(1, min(8, int(os.environ.get("LAYA_CPU_THREADS", "4"))))
        torch.set_num_threads(cpu_threads)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            pass  # PyTorch allows this setting only before the first inference.
    import laya

    selected = None if device == "auto" else device
    model_source = resolve_model_source(model)
    print(f"Loading Laya model {model!r} on {selected or 'auto'}...", flush=True)
    return SafeDecisionAgent(laya.load(model_source, device=selected))


def run_cycle(
    client: RimApiClient,
    agent: Any,
    *,
    apply: bool,
    confidence: float,
    log_path: Path,
) -> dict[str, Any]:
    snapshot = collect_snapshot(client)
    decision = decide(agent, snapshot, confidence)
    action = plan_action(snapshot, decision)
    result = {"applied": False, "reason": "preview mode"}
    if apply:
        result = apply_action(client, action)
    record = {
        "timestamp": utc_now(),
        "mode": "apply" if apply else "preview",
        "snapshot": snapshot,
        "decision": decision,
        "action": action,
        "result": result,
    }
    preferences = laya_preferences.load_preferences()
    if preferences.get("technical_logging"):
        append_log(log_path, record)
    else:
        append_log(log_path, {key: value for key, value in record.items() if key != "snapshot"})
    return record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe Laya bridge for RimWorld RIMAPI")
    parser.add_argument("command", choices=["check", "suggest", "run-once", "watch", "download-model"])
    parser.add_argument("--api-url", default=os.environ.get("RIMAPI_URL", DEFAULT_API_URL))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--confidence", type=float, default=0.0)
    parser.add_argument("--interval", type=int, default=45)
    parser.add_argument("--apply", action="store_true", help="Actually send whitelisted commands to RIMAPI")
    parser.add_argument("--log", type=Path, default=Path(__file__).with_name("logs") / "decisions.jsonl")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not 0 <= args.confidence <= 1:
        raise SystemExit("--confidence must be between 0 and 1")
    if args.interval < 10:
        raise SystemExit("--interval must be at least 10 seconds")
    if args.command == "download-model":
        resolve_model_source(args.model)
        print("Laya model files are ready.")
        return 0
    client = RimApiClient(args.api_url)

    if args.command == "check":
        print_json(collect_snapshot(client))
        return 0

    agent = load_agent(args.model, args.device)
    apply = bool(args.apply and args.command in {"run-once", "watch"})
    if args.command == "suggest":
        apply = False

    if args.command in {"suggest", "run-once"}:
        print_json(run_cycle(client, agent, apply=apply, confidence=args.confidence, log_path=args.log))
        return 0

    print(f"Watching every {args.interval}s in {'APPLY' if apply else 'PREVIEW'} mode. Ctrl+C stops safely.")
    try:
        while True:
            try:
                record = run_cycle(client, agent, apply=apply, confidence=args.confidence, log_path=args.log)
                print(f"[{record['timestamp']}] {record['action']['description']} | {record['result']}", flush=True)
            except Exception as exc:
                error = {"timestamp": utc_now(), "mode": "error", "error": repr(exc)}
                append_log(args.log, error)
                print(f"[{error['timestamp']}] {exc}", file=sys.stderr, flush=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Stopped. No further commands will be sent.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
