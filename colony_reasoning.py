"""Explicit consequences for the decision model; no invented success scores.

These are grounded affordance summaries, not a simulated future or a model's
hidden reasoning. Costs and downside are supplied before selection. Unknown
outcomes stay unknown and an accepted command is never labelled completed.
"""
from __future__ import annotations

import math
from typing import Any
import colony_modules
import colony_growth


FIELDS = ("benefit", "risk", "cost", "inaction", "uncertainty")
DOMAIN_EFFECTS = {
    "construction": ("Material loss if work is botched; unfinished projects give no shelter",
                     "Materials and builder time", "Existing space and utility shortages persist"),
    "care": ("Treatment can fail; unsafe rescue can expose another pawn",
             "Caregiver time, medicine or food when required", "Patient needs may worsen without care"),
    "work_orders": ("Reassignment may delay the worker's other duties",
                    "Worker time; travel and inputs depend on the order", "Current jobs and shortages continue"),
    "economy_diplomacy": ("Trade consumes supplies; travel leaves fewer defenders",
                          "Goods, food, silver or travel time as applicable", "Population or income opportunity may expire"),
    "defense": ("Combat can injure allies; preparation is not protection until ready",
                "Defender time and equipment", "Current threat or defensive weakness persists"),
    "corpse_management": ("Exposed hauling may endanger a worker",
                          "Hauling and processing time", "Decay and corpse exposure continue"),
    "strategy": ("Progress can divert effort from immediate survival",
                 "Research or planning time when work is assigned", "Long-term bottleneck remains"),
}


def effects(action: str, snapshot: dict[str, Any], description: str, domain: str) -> dict[str, str]:
    module = colony_modules.owner(action)
    if module is not None:
        assessed = module.assess(action, snapshot)
        result = {key: str(assessed.get(key) or "Unknown") for key in FIELDS}
        return with_feedback(result, action, snapshot)
    risk, cost, inaction = DOMAIN_EFFECTS.get(domain, DOMAIN_EFFECTS["strategy"])
    result = dict(benefit=description, risk=risk, cost=cost, inaction=inaction,
                  uncertainty="Order acceptance does not prove the intended result")
    if action in {"hold_survival", "leave_wildlife_alone"}:
        result.update(benefit="Allow current work, eating or rest to continue",
                      risk="Unassigned urgent work receives no new order",
                      cost="Time passes; no new materials spent",
                      inaction="Existing needs and threats continue")
    if action in {"harvest_food_crops_early", "harvest_at_risk_crops"}:
        result.update(risk="Early harvest loses remaining growth and later yield",
                      inaction="Dying crops may perish; healthy crops may mature")
    elif action == "plan_colonist_augmentation":
        result.update(risk="Surgery failure, recovery and ideology penalties",
                      cost="Owned part, medicine and qualified surgeon time",
                      inaction="Current body part and its limitations remain")
    elif action == "build_power":
        result.update(risk="Disconnected or unfueled generators supply no consumers",
                      cost="Construction, fuel or variable renewable supply",
                      inaction="Unpowered consumers remain offline")
    elif action == "build_ship":
        plan = snapshot.get("development", {}).get("ship_construction") or {}
        result.update(benefit=f"Build {len((plan.get('ready_layout') or {}).get('buildings') or [])} currently funded connected ship parts",
                      risk="Blueprints do not work until built; reactor startup later triggers raids",
                      cost=f"Missing materials {plan.get('shortages')}; preserve ongoing project supplies",
                      inaction=f"{plan.get('remaining')} unplanned parts remain; caskets require completed beams",
                      uncertainty="Native placement is checked now; observed connected readiness is checked again before startup")
    elif action in {"create_growing_zone", "configure_crop"}:
        result.update(risk="Frost, heat, blight or premature replacement can lose crops",
                      cost="Sowing labor; food arrives only after growth and harvest",
                      inaction="Existing fields continue; unplanted land produces no crop")
    elif action in {"designate_safe_hunting", "prioritize_hunting"}:
        result.update(risk="Revenge or hostile travel route may injure a hunter",
                      cost="Hunting, hauling, butchering and cooking labor",
                      inaction="Prey remains alive; stored food keeps declining")
    dev = snapshot.get("development") or {}
    # Concrete emergency facts augment opportunity cost; they do not silently
    # select a strategy or manufacture a probability of death.
    downed = sum(bool(p.get("downed")) for p in snapshot.get("colonists") or [])
    if downed and domain not in {"care", "defense"}:
        result["cost"] = f"{downed} downed colonists compete for available workers; " + result["cost"]
    elif dev.get("construction_projects") and domain == "construction":
        result["cost"] = f"{len(dev['construction_projects'])} unfinished projects already need labor; " + result["cost"]
    return with_feedback(result, action, snapshot)


def with_feedback(result: dict[str, str], action: str, snapshot: dict[str, Any]) -> dict[str, str]:
    feedback = (snapshot.get("development") or {}).get("outcome_feedback") or {}
    if feedback.get("action") == action:
        result["uncertainty"] = (f"Previous {feedback.get('command')}: {feedback.get('status')}; "
                                 "completion unverified. " + result["uncertainty"])
    return result


def decision_facts(state: dict[str, Any]) -> dict[str, Any]:
    """Facts relevant across alternatives, excluding catalog and option prose."""
    needs = state.get("needs") or {}
    result = {"endgame": (state.get("course") or {}).get("endgame") or state.get("endgame"),
              "goal_requirements": state.get("goal_requirements"),
              "last_expedition_attempt": state.get("last_expedition_attempt"),
              "people": state.get("people"), "threats": state.get("threats"),
              "food_days": needs.get("food_runway_days_estimate", state.get("food_runway_days_estimate")),
              "downed": needs.get("downed", state.get("downed")),
              "heat": state.get("heat"), "cold": state.get("cold"), "course": state.get("course")}
    return {key: value for key, value in result.items() if value is not None and value != {}}


def recreation_pressure(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Observed low joy and mood, not a predicted mental-break probability."""
    affected = []
    for pawn in snapshot.get("colonists") or []:
        if any(pawn.get(flag) for flag in ("dead", "is_dead", "downed", "is_downed",
                                          "in_mental_state", "is_in_mental_state")):
            continue
        joy, mood = pawn.get("joy"), pawn.get("mood")
        if all(isinstance(v, (int, float)) and not isinstance(v, bool)
               and math.isfinite(v) and 0 <= v <= 1 for v in (joy, mood)):
            if joy < .2 and mood < .4:
                affected.append((joy, mood))
    if not affected:
        return None
    return {"people": len(affected), "joy_min": round(min(p[0] for p in affected), 3),
            "mood_min": round(min(p[1] for p in affected), 3)}


def survival_wait_state(snapshot: dict[str, Any]) -> dict[str, int]:
    """Describe current workers without claiming an earlier order progressed."""
    live = {str(p["id"]): p for p in (snapshot.get("combat") or {}).get("colonists") or []
            if p.get("id") is not None}
    result = {"people": 0, "unavailable": 0, "idle": 0, "jobs_observed": 0, "unknown_jobs": 0}
    for pawn in snapshot.get("colonists") or []:
        actor = live.get(str(pawn.get("id")), {})
        if pawn.get("dead") or pawn.get("is_dead") or actor.get("is_dead"):
            continue
        result["people"] += 1
        if any(pawn.get(flag) or actor.get(flag) for flag in (
                "downed", "is_downed", "in_mental_state", "is_in_mental_state", "is_drafted")):
            result["unavailable"] += 1
            continue
        job = str(pawn.get("current_job") or actor.get("current_job") or "").lower()
        if job in {"", "unknown"}:
            result["unknown_jobs"] += 1
        elif job in {"wait", "wait_wander", "gotowander", "wander", "wait_maintainposture"}:
            result["idle"] += 1
        else:
            result["jobs_observed"] += 1
    return result


def attention_facts(snapshot: dict[str, Any], *, roofed_sleeping_places: int | None = None) -> dict[str, Any]:
    """Root comparisons get live needs before lossy, general context packing.

    A shelter deficit used to survive fit_model_context but disappear from
    decision_facts. The final action comparison consequently saw no shelter
    deficit at all. Keep this small and ordered by immediate consequences.
    """
    dev = snapshot.get("development") or {}
    people = snapshot.get("colonists") or []
    resources = (snapshot.get("map") or {}).get("resources") or {}
    sheltered = roofed_sleeping_places
    # Keep measured hazards together so short comparison prompts cannot retain
    # food while dropping thermal stage or blood loss at the end of the state.
    import math

    def number(value):
        try:
            result = float(value)
            return round(result, 3) if math.isfinite(result) else None
        except (TypeError, ValueError, OverflowError):
            return None

    care_people = [pawn for pawn in people if not pawn.get("is_dead") and not pawn.get("dead")]
    thermal = {}
    for pawn in care_people:
        for h in pawn.get("health_conditions") or []:
            if not isinstance(h, dict) or h.get("def_name") not in {"Hypothermia", "Heatstroke"}:
                continue
            name = h["def_name"]
            severity = number(h.get("severity"))
            if severity is None:
                continue
            old = thermal.get(name)
            if old is None or severity > old["severity"]:
                stage = h.get("cur_stage_index")
                thermal[name] = {"severity": severity,
                                 "stage": stage if isinstance(stage, int) and not isinstance(stage, bool) and stage >= 0 else None,
                                 "life_threatening": bool(h.get("life_threatening"))}
    bleed_rate = max((number(p.get("bleeding_rate")) or 0 for p in care_people), default=0)
    least_food = min((number(p.get("hunger")) for p in care_people
                      if number(p.get("hunger")) is not None), default=None)
    malnutrition = max((number(h.get("severity")) or 0
                        for p in care_people for h in p.get("health_conditions") or []
                        if isinstance(h, dict) and h.get("def_name") == "Malnutrition"), default=0)
    dependent_hungry = sum(bool(p.get("downed") or p.get("is_downed"))
                          and number(p.get("hunger")) is not None and number(p.get("hunger")) <= .1
                          for p in care_people)
    recreation = recreation_pressure(snapshot)
    animals = [a for a in snapshot.get("animals") or [] if not a.get("dead")]
    animal_bleed = max((number(a.get("bleeding_rate")) or 0 for a in animals), default=0)
    care_risks = None
    food_stock = number(resources.get("nutrition"))
    food_days = round(food_stock / (1.6 * len(care_people)), 1) if food_stock is not None and care_people else None
    if thermal or bleed_rate >= .05 or animal_bleed >= .05 or malnutrition >= .15 or dependent_hungry or recreation or (food_days is not None and food_days < 5):
        care_risks = {"meals": resources.get("meals"), "least_food_level": least_food,
                      "bleed_rate_max": bleed_rate,
                      "downed": sum(bool(p.get("downed") or p.get("is_downed")) for p in care_people),
                      "threats": (snapshot.get("map") or {}).get("enemies", 0)}
        if food_days is not None and food_days < 5:
            care_risks["food_days"] = food_days
            care_risks["stored_nutrition"] = food_stock
        if animal_bleed >= .05:
            care_risks["animal_bleed_max"] = animal_bleed
            care_risks["downed_animals"] = sum(bool(a.get("downed")) for a in animals)
        if malnutrition:
            care_risks["malnutrition_max"] = malnutrition
        if dependent_hungry:
            care_risks["dependent_hungry"] = dependent_hungry
        if recreation:
            care_risks["recreation_deprived"] = recreation
    if thermal:
        roofed_rooms = [room for room in dev.get("rooms") or []
                        if not room.get("touches_map_edge") and not room.get("is_prison_cell")
                        and room.get("open_roof_count") == 0 and room.get("contained_beds_ids")]
        temperatures = [value for room in roofed_rooms if (value := number(room.get("temperature"))) is not None]
        care_risks = {"thermal": thermal, "outside_c": number((dev.get("weather") or {}).get("temperature")),
                      "roofed_sleepers": sheltered,
                      "roofed_bed_room_c": [min(temperatures), max(temperatures)] if temperatures else "unverified",
                      **care_risks,
                      "home_fires": sum(bool(fire.get("in_home"))
                                        for fire in (dev.get("fire_situation") or {}).get("fires") or []
                                        if isinstance(fire, dict))}
    facts = {
        "care_risks": care_risks,
        "development": colony_growth.development_briefing(snapshot),
        "threats": (snapshot.get("map") or {}).get("enemies", 0),
        "downed": sum(bool(p.get("downed")) for p in people),
        "people": len(people),
        "unroofed_sleepers": max(0, len(people) - sheltered) if sheltered is not None else None,
        "meals": resources.get("meals"),
        "least_food_level": min((float(p["hunger"]) for p in people if p.get("hunger") is not None), default=1),
        "pending_builds": len(dev.get("construction_projects") or []),
        "building_now": sum(str(p.get("current_job") or "").lower().startswith(
            ("construct", "build", "finishframe", "placeframe")) for p in people),
        "outside_c": (dev.get("weather") or {}).get("temperature"),
        "endgame": (dev.get("doctrine") or {}).get("endgame"),
    }
    return {key: value for key, value in facts.items() if value is not None}


def parameter_facts(snapshot: dict[str, Any], action: str,
                    *, roofed_sleeping_places: int | None = None) -> dict[str, Any]:
    """Carry measured colony constraints into the selected action's questions.

    A fitted root state is not enough: detailed comparisons reserve only a
    short prefix for it. Keep these bounded facts independent of JSON order
    in the broader strategy, history and description fields.
    """
    import math

    dev = snapshot.get("development") or {}
    stock = dev.get("item_counts") or {}
    people = [p for p in snapshot.get("colonists") or []
              if not p.get("dead") and not p.get("is_dead")]
    temperature = (dev.get("weather") or {}).get("temperature")
    if isinstance(temperature, (int, float)) and math.isfinite(temperature):
        temperature = round(temperature, 1)
    else:
        temperature = None
    if action=="build_animal_barn":
        import colony_husbandry as husbandry
        plan=husbandry.planning_context(snapshot)
        return {"action":action,"outside_c":temperature,"people":len(people),
            "downed":sum(bool(p.get("downed")) for p in people),
            "animal_comfort":husbandry.comfort_intersection(snapshot.get("animals") or []),
            "feed_reserve_target":plan.get("reserve_target_nutrition"),
            "feed_cover_days":plan.get("stock_cover_days_if_delivered"),
            "hay":stock.get("Hay") if "item_counts" in dev else None,
            "unfinished":len(dev.get("construction_projects") or [])}
    return {
        "action": action,
        "wood": stock.get("WoodLog", 0) if "item_counts" in dev else None,
        "steel": stock.get("Steel", 0) if "item_counts" in dev else None,
        "roofed_beds": roofed_sleeping_places,
        "unfinished": len(dev.get("construction_projects") or []),
        "people": len(people),
        "meals": ((snapshot.get("map") or {}).get("resources") or {}).get("meals"),
        "outside_c": temperature,
        "threats": (snapshot.get("map") or {}).get("enemies", 0),
        "downed": sum(bool(p.get("downed")) for p in people),
    }


def outcome_summary(feedback: dict[str, Any]) -> str:
    if not feedback:
        return ""
    # Status comes first; even a long mod action identifier cannot erase it.
    return f"{feedback.get('status')}; {feedback.get('command', 'unknown')}; completion unverified; action={feedback.get('action', 'unknown')}"
