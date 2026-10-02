"""Explicit consequences for the decision model; no invented success scores.

These are grounded affordance summaries, not a simulated future or a model's
hidden reasoning. Costs and downside are supplied before selection. Unknown
outcomes stay unknown and an accepted command is never labelled completed.
"""
from __future__ import annotations

from typing import Any
import colony_modules


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
              "people": state.get("people"), "threats": state.get("threats"),
              "food_days": needs.get("food_runway_days_estimate", state.get("food_runway_days_estimate")),
              "downed": needs.get("downed", state.get("downed")),
              "heat": state.get("heat"), "cold": state.get("cold"), "course": state.get("course")}
    return {key: value for key, value in result.items() if value is not None and value != {}}


def outcome_summary(feedback: dict[str, Any]) -> str:
    if not feedback:
        return ""
    # Status comes first; even a long mod action identifier cannot erase it.
    return f"{feedback.get('status')}; {feedback.get('command', 'unknown')}; completion unverified; action={feedback.get('action', 'unknown')}"
