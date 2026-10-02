"""Observed DLC hazards and native mech/containment choices, without instant effects."""
from __future__ import annotations
from typing import Any
from laya_decisions import ask_laya_choice

DESCRIPTIONS = {
    "specialists_mech_mode": "Choose a controlled mech group's normal work, recharge or dormant self-charge policy. Compare energy and labor with charger power and wastepack pollution; all members are affected.",
    "specialists_suppress_entity": "Send an available enabled warden on a normal feasible entity suppression job. Lower activity can reduce escape risk but takes labor and can reduce study speed; unsafe containment is still unsafe.",
}
LABELS = {"specialists_mech_mode": "режим работы механической группы", "specialists_suppress_entity": "подавление активности сущности"}
ACTIONS = set(DESCRIPTIONS)
DOMAINS = {"specialists_mech_mode": "work_orders", "specialists_suppress_entity": "care"}

def summary(snapshot: dict) -> dict:
    """Compact model facts; all detailed instances remain in the readonly context."""
    context = snapshot.get("development", {}).get("specialists", {})
    if not context or context.get("available") is False:
        return {"available": False}
    energies = [{"pawn_id": m.get("pawn_id"), "energy": m.get("energy"), "mode": g.get("mode")} for g in context.get("mech_groups") or [] for m in g.get("mechs") or [] if isinstance(m.get("energy"), (int, float)) and m["energy"] < .2]
    entities = [{"platform_id": e.get("platform_id"), "strength": e.get("containment_strength"), "minimum": e.get("minimum_strength"), "activity": e.get("activity")} for e in context.get("entities") or [] if isinstance(e.get("minimum_strength"), (int, float)) and isinstance(e.get("containment_strength"), (int, float)) and e["containment_strength"] < e["minimum_strength"]]
    resources = [{"pawn_id": p.get("pawn_id"), "resource": r.get("def_name"), "level": r.get("level"), "target": r.get("target")} for p in context.get("gene_pawns") or [] for r in p.get("resources") or [] if isinstance(r.get("level"), (int, float)) and isinstance(r.get("target"), (int, float)) and r["level"] < r["target"]]
    needs = [{"pawn_id": p.get("pawn_id"), "need": n.get("def_name"), "level": n.get("level")} for p in context.get("gene_pawns") or [] for n in p.get("needs") or [] if isinstance(n.get("level"), (int, float)) and n["level"] < .2]
    return {"low_energy_mechs": {"count": len(energies), "examples": energies[:4]},
            "unsafe_containment": {"count": len(entities), "examples": entities[:4]},
            "pollution_waste": {"pollution_percent": context.get("pollution_percent"), "unfrozen_wastepacks": sum(int(w.get("count") or 0) for w in context.get("wastepacks") or [] if not w.get("frozen"))},
            "low_gene_resources": {"count": len(resources), "examples": resources[:4]},
            "low_gene_needs": {"count": len(needs), "examples": needs[:4]}}

def collect(client: Any, snapshot: dict) -> dict:
    try:
        result = client.get("/api/v1/specialists/context", map_id=snapshot["map"]["id"])
        if not isinstance(result, dict):
            return {"available": False, "reason": "invalid_context"}
        result["hazard_summary"] = {
            "pollution_percent": result.get("pollution_percent"),
            "unfrozen_wastepacks": sum(int(w.get("count") or 0) for w in result.get("wastepacks") or [] if not w.get("frozen")),
            "mechs_below_20_percent_energy": [m.get("pawn_id") for g in result.get("mech_groups") or [] for m in g.get("mechs") or [] if isinstance(m.get("energy"), (int, float)) and m["energy"] < .2],
            "insufficient_containment_platforms": [e.get("platform_id") for e in result.get("entities") or [] if isinstance(e.get("minimum_strength"), (int, float)) and isinstance(e.get("containment_strength"), (int, float)) and e["containment_strength"] < e["minimum_strength"]],
            "gene_resources": [{"pawn_id": p.get("pawn_id"), "resources": p.get("resources"), "needs": [(n.get("def_name"), n.get("level")) for n in p.get("needs") or []]} for p in result.get("gene_pawns") or [] if p.get("resources") or p.get("needs")],
            "limits": "Hazards are observations; suppression cannot repair weak containment, and recharge cannot provide safe waste storage.",
        }
        return result
    except Exception as exc:
        return {"available": False, "reason": str(exc)}

def prepare(snapshot: dict, map_state: dict) -> list[str]:
    context = snapshot.setdefault("development", {}).setdefault("specialists", {})
    options = {a: {} for a in ACTIONS}
    if context.get("biotech_active"):
        for group in context.get("mech_groups") or []:
            for mode in group.get("mode_options") or []:
                if mode != group.get("mode"):
                    key = f"{group['mechanitor_id']}:{group['group_index']}:{mode}"
                    options["specialists_mech_mode"][key] = {"kind": "mech_mode", "mechanitor_id": group["mechanitor_id"], "group_index": group["group_index"], "value": mode, "context": group}
    if context.get("anomaly_active"):
        for entity in context.get("entities") or []:
            for worker in entity.get("worker_options") or []:
                key = f"{entity['platform_id']}:{worker['pawn_id']}"
                options["specialists_suppress_entity"][key] = {"kind": "suppress", "platform_id": entity["platform_id"], "worker_id": worker["pawn_id"], "context": {"entity": entity, "worker": worker}}
    context["options"] = options
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    return [a for a, rows in options.items() if rows and tick - int((map_state.get("issued") or {}).get("specialists:" + a, -1000000)) >= 15000]

def assess(action: str, snapshot: dict) -> dict:
    if action == "specialists_mech_mode":
        return {"benefit": "Work provides type-supported labor; recharge restores energy; dormant self-charge needs no charger.", "cost": "Recharge occupies powered chargers and creates wastepacks; dormancy sacrifices work and defense.", "risk": "The policy affects every group member. Chargers or safe waste storage may be unavailable.", "inaction": "Current mode continues; energy or lost labor may remain a problem.", "uncertainty": "Mode does not guarantee a free compatible charger, job, or safe power supply."}
    return {"benefit": "Normal suppression reduces entity activity when the job completes.", "cost": "Warden labor; reduced activity may reduce study knowledge rate.", "risk": "Suppression does not repair inadequate containment or guarantee no escape.", "inaction": "Activity and containment pressure can persist while wardens wait.", "uncertainty": "Reservations, path, worker status and entity state can change before completion."}

def choose(agent: Any, state: dict, action: str, snapshot: dict) -> tuple[dict, dict]:
    context = snapshot.get("development", {}).get("specialists", {})
    plans = context.get("options", {}).get(action) or {}
    effects = assess(action, snapshot)
    targets = {}
    for row in plans.values():
        if row["kind"] == "mech_mode":
            g = row["context"]
            target = f"{row['mechanitor_id']}:{row['group_index']}"
            targets[target] = f"Group-wide policy; {g.get('mechanitor_name')} group {g.get('group_index')}; mode {g.get('mode')}; energy {[(m.get('name'), m.get('energy')) for m in g.get('mechs') or []]}"
        else:
            e = row["context"]["entity"]
            targets[str(row["platform_id"])] = f"Containment {e.get('containment_strength')} required {e.get('minimum_strength')}; {e.get('name')} activity {e.get('activity')}; suppression costs study speed"
    if not targets:
        return {"defer": True}, {"reason": "no_live_specialist_options"}
    targets["defer"] = "Preserve current policy and labor; energy or activity problems may remain."
    target, first = ask_laya_choice(agent, {"choice_context": {"risk": effects["risk"], "cost": effects["cost"]}, "colony": state}, action + "_target", "Choose a live target, or defer.", targets, detailed=True)
    if target == "defer":
        return {"defer": True}, first
    plans = {k: row for k, row in plans.items() if (f"{row['mechanitor_id']}:{row['group_index']}" if row["kind"] == "mech_mode" else str(row["platform_id"])) == target}
    descriptions = {}
    for key, row in plans.items():
        if row["kind"] == "mech_mode":
            g = row["context"]
            descriptions[key] = f"{row['value']}: group-wide lost labor/power/waste tradeoff; {g.get('mechanitor_name')} group {g.get('group_index')} current {g.get('mode')}; members {[(m.get('name'), m.get('energy')) for m in g.get('mechs') or []]}"
        else:
            e, w = row["context"]["entity"], row["context"]["worker"]
            descriptions[key] = f"Labor and study-speed cost; {w.get('name')} Social {w.get('social')}, suppression rate {w.get('suppression_rate')}; {e.get('name')} activity {e.get('activity')}, strength {e.get('containment_strength')} required {e.get('minimum_strength')}"
    descriptions["defer"] = "Keep current policy and workers; energy/activity hazards may persist."
    target_context = next(iter(plans.values()))["context"]
    if action == "specialists_suppress_entity":
        e = target_context["entity"]
        target_context = {"strength": e.get("containment_strength"), "minimum_strength": e.get("minimum_strength"), "activity": e.get("activity"), "suppression_enabled": e.get("suppression_enabled"), "threshold": e.get("suppress_above"), "study_factor": e.get("study_factor"), "mode": e.get("containment_mode")}
    else:
        g = target_context
        energies = [m.get("energy") for m in g.get("mechs") or [] if isinstance(m.get("energy"), (int, float))]
        target_context = {"mode": g.get("mode"), "minimum_energy": min(energies, default=None), "maximum_energy": max(energies, default=None), "member_count": len(g.get("mechs") or []), "recharge_limits": [g.get("recharge_min"), g.get("recharge_max")]}
    visible = {"choice_context": {"target": target_context, "pollution": context.get("pollution_percent"), "wastepacks": {"count": sum(int(w.get("count") or 0) for w in context.get("wastepacks") or []), "unfrozen": sum(int(w.get("count") or 0) for w in context.get("wastepacks") or [] if not w.get("frozen"))}, "chargers": context.get("chargers"), "effects": effects}, "colony": state}
    key, raw = ask_laya_choice(agent, visible, action, DESCRIPTIONS[action], descriptions, detailed=True)
    raw["specialist_target_choice"] = first
    return ({"defer": True} if key == "defer" else {k: v for k, v in plans[key].items() if k != "context"}), raw

def execute(client: Any, snapshot: dict, map_state: dict, action: str, selected: dict) -> dict:
    if selected.get("defer"):
        map_state.setdefault("issued", {})["specialists:" + action] = int(snapshot.get("game", {}).get("tick") or 0)
        return {"applied": False, "reason": "laya_deferred"}
    payload = {k: selected[k] for k in ("kind", "mechanitor_id", "group_index", "value", "platform_id", "worker_id") if k in selected}
    live = collect(client, snapshot)
    prepare({"map": snapshot["map"], "development": {"specialists": live}}, {})
    rows = live.get("options", {}).get(action) or {}
    if not any({k: v for k, v in row.items() if k != "context"} == payload for row in rows.values()):
        return {"applied": False, "reason": "selection_no_longer_feasible"}
    result = client.post("/api/v1/specialists/order", body={"map_id": snapshot["map"]["id"], **payload})
    if isinstance(result, dict) and result.get("applied"):
        map_state.setdefault("issued", {})["specialists:" + action] = int(snapshot.get("game", {}).get("tick") or 0)
    return result if isinstance(result, dict) else {"applied": False, "reason": "invalid_response"}
