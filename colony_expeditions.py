"""Read-only native expedition preview followed by an explicit Laya confirmation."""
from __future__ import annotations
from typing import Any, Callable


def _card(plan: dict[str, Any]) -> str:
    return (f"Confirm {plan.get('mode')} plan to {str(plan.get('destination_name') or '')[:32]}; "
            f"team {len(plan.get('pawn_ids') or [])}, prisoners {len(plan.get('prisoners') or [])}; "
            f"{', '.join(str(v)[:24] for v in (plan.get('travelers') or [])[:3])}")


def _effects(plan: dict[str, Any]) -> dict[str, str]:
    diets = plan.get("diets") or []
    policies = sorted({str(row.get("policy") or "default") for row in diets})
    rations = sorted({str(row.get("def_name")) for row in plan.get("manifest") or [] if row.get("def_name") in {"Pemmican", "MealSurvivalPack"}})
    return {
        "benefit": f"Outbound {float(plan['outbound_days']):.2f}d return {float(plan['return_days']):.2f}d; {str(plan.get('destination_name') or '')[:32]}",
        "risk": f"Food {float(plan['food_days']):.2f}d margin {float(plan['food_margin_days']):.2f}d; every traveler/prisoner diet checked; {plan.get('consequences')}",
        "cost": f"Mass {float(plan['mass']):.1f}/{float(plan['capacity']):.1f}kg food {float(plan['food_nutrition']):.1f}nut daily {float(plan['daily_nutrition']):.1f}; gear {float(plan.get('carried_gear_mass') or 0):.1f}",
        "inaction": f"Home {plan['home_defenders']}def med{plan['home_medicine']} food{plan['home_food_items']}items/{float(plan['home_food_nutrition']):.1f}nut; defer retains crew/cargo",
        "uncertainty": "ETA excludes formation/combat/incidents; no foraging/animals; common shelf-stable ration; rottable life at 40C",
    }


def prepare(client: Any, agent: Any, request: dict[str, Any], ask: Callable[..., Any]) -> dict[str, Any]:
    """Preview POST creates no jobs/routes. The chosen confirmed manifest is passed unchanged."""
    preview = client.post("/api/v1/world/caravan/preview", body=request)
    if isinstance(preview, dict) and isinstance(preview.get("data"), dict):
        preview = preview["data"]
    preview = preview if isinstance(preview, dict) else {}
    plans = [row for row in preview.get("plans") or [] if isinstance(row, dict)
             and row.get("essentials") and row.get("manifest") is not None
             and row.get("outbound_days") is not None and row.get("return_days") is not None
             and float(row.get("food_margin_days") or 0) >= float(row.get("margin_days") or 1)]
    if not plans:
        return {"status": "blocked", "applied": False, "reason": "; ".join(map(str, preview.get("blockers") or ["No verified route, roster and ration plan"])),
                "pending": preview.get("pending"), "last_result": preview.get("last_result"), "readiness": preview.get("readiness")}
    indexed = {f"plan_{index + 1}": row for index, row in enumerate(plans)}
    criteria = {key: _card(row) for key, row in indexed.items()}
    effects = {key: _effects(row) for key, row in indexed.items()}
    effects["defer"] = {"benefit": "Keep crew, prisoners and supplies home", "risk": "Opportunity deadline may expire", "cost": "No expedition cost now", "inaction": "Travel/combat/rescue does not start", "uncertainty": "Reconsider live eligibility and stocks later"}
    criteria["defer"] = "Keep travelers, supplies and policy at home; reconsider when circumstances change."
    first = plans[0]
    facts = {"home_reserve_items": first.get("minimum_home_food_items"), "reserve_nutrition": first.get("minimum_home_food_nutrition"),
             "margin_days": first.get("margin_days"), "rations": sorted({v.get("def_name") for v in first.get("manifest") or [] if v.get("def_name") in {"Pemmican", "MealSurvivalPack"}}),
             "policies": sorted({str(v.get("policy") or "default") for v in first.get("diets") or []})}
    choice, raw = ask(agent, {"decision_facts": facts, "option_effects": effects},
                      "expedition_confirmation", "Confirm one exact native expedition plan or defer. ETA excludes formation/combat/incidents; return needs observation and a fresh decision.", criteria)
    selected = indexed.get(str(choice))
    if selected is None:
        return {"status": "deferred", "applied": False, "reason": "Laya deferred expedition", "decision": raw}
    body = {**request, "confirmed": True, **{key: selected[key] for key in ("essentials", "pawn_ids", "home_pawn_ids", "manifest")}}
    return {"status": "confirmed", "body": body, "plan": selected, "decision": raw}


def execute(client: Any, prepared: Any) -> dict[str, Any]:
    if not isinstance(prepared, dict) or prepared.get("status") != "confirmed":
        return {"applied": False, "reason": (prepared or {}).get("reason", "Expedition requires native preview and explicit confirmation"),
                "deliberate_defer": isinstance(prepared, dict) and prepared.get("status") == "deferred",
                "readiness": (prepared or {}).get("readiness")}
    body = prepared["body"]
    result = client.post(f"/api/v1/world/caravan/{body['mode']}/start", body=body)
    if isinstance(result, dict) and isinstance(result.get("data"), dict):
        result = result["data"]
    if not isinstance(result, dict) or result.get("applied") is not True:
        return {"applied": False, "reason": "Native expedition start was not acknowledged", "response": result}
    return {"applied": True, "response": result, "plan": prepared["plan"]}
