"""Loaded native abilities and thing interactions, with staged bounded choices."""
from __future__ import annotations
from typing import Any
from laya_decisions import ask_laya_choice

DESCRIPTIONS = {
    "affordances_ability": "Use a learned native ability after comparing effect, costs, target health, ideology and allied exposure.",
    "affordances_interaction": "Choose an available native interaction with a real building or item: study, biosculpting, gene extraction, shuttles or other loaded mechanics.",
    "affordances_scanner": "Prepare or cancel a native subcore scanner after comparing ingredients, donor needs and whether this scanner destroys its occupant's brain.",
}
LABELS = {"affordances_ability": "применить доступную способность", "affordances_interaction": "взаимодействовать с объектом", "affordances_scanner": "сканер субядер"}
ACTIONS = set(DESCRIPTIONS)
DOMAINS = {"affordances_ability": "care", "affordances_interaction": "work_orders", "affordances_scanner": "work_orders"}

def collect(client: Any, snapshot: dict) -> dict:
    data = client.get("/api/v1/affordances/context", map_id=snapshot["map"]["id"])
    return data if isinstance(data, dict) else {"available": False, "reason": "invalid_context"}

def prepare(snapshot: dict, map_state: dict) -> list[str]:
    dev = snapshot.setdefault("development", {}).setdefault("affordances", {})
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    cooldowns = map_state.setdefault("affordance_cooldowns", {})
    for key, previous in list(cooldowns.items()):
        if previous > tick:
            cooldowns.pop(key)
    options = {a: {} for a in ACTIONS}
    for row in dev.get("options") or []:
        action = {"ability": "affordances_ability", "menu": "affordances_interaction", "scanner": "affordances_scanner"}.get(row.get("kind"))
        if action and row.get("key") and tick - int(cooldowns.get(row["key"], -1000000)) >= 2500:
            options[action][row["key"]] = row
    dev["candidates"] = options
    return [a for a, rows in options.items() if rows and tick - int(cooldowns.get(a, -1000000)) >= 2500]

def assess(action: str, snapshot: dict) -> dict:
    return {"benefit": "Execute a real currently offered game action; learned abilities and loaded content remain available.",
            "risk": "Native legality does not imply benefit. Conversion, extraction, bloodfeeding or long pod cycles may injure, anger or remove a needed worker.",
            "cost": "Check exact ability charges/focus/heat, ingredient use, work interruption and time away.",
            "inaction": "Keep resources and current jobs; an untreated condition or unmet DLC need may persist.",
            "uncertainty": "Native descriptions and current target facts apply. The resulting job or next dialogue is not completion."}


def evidence(row: dict) -> dict:
    """Bound changes affecting a decision; never put extra fields in the API order."""
    def stable(value):
        if isinstance(value, float):
            return round(value, 2)
        if isinstance(value, dict):
            return {k: stable(v) for k, v in value.items()}
        if isinstance(value, list):
            return [stable(v) for v in value]
        return value
    return stable({k: row.get(k) for k in ("cost", "risk", "pawn", "target_pawn", "target_hostile", "affected_allies")})

def choose(agent: Any, state: dict, action: str, snapshot: dict) -> tuple[dict, dict]:
    rows = snapshot.get("development", {}).get("affordances", {}).get("candidates", {}).get(action) or {}
    if not rows:
        return {"defer": True}, {"reason": "no_live_options"}
    # First choose one mechanical purpose, then one target, then a worker. The
    # growing count of objects never consumes the model's small context window.
    raw_steps = []
    for stage, field in (("purpose", "label"), ("target", "target_id"), ("worker", "pawn_id")):
        groups: dict[str, list[dict]] = {}
        for row in rows.values():
            groups.setdefault(str(row.get(field)), []).append(row)
        criteria, effects = {}, {}
        aliases = {f"p{index}": key for index, key in enumerate(groups)}
        for key, group in aliases.items():
            members = groups[group]
            row = members[0]
            criteria[key] = (f"{row.get('label')}; {row.get('target')}; "
                             f"worker {row.get('pawn', {}).get('name')}; {len(members)} native options")
            facts = row.get("target_pawn") or row.get("pawn") or {}
            effects[key] = {
                "benefit": str(row.get("description") or row.get("label") or "")[:400],
                "risk": f"{row.get('risk')}; allies in area {row.get('affected_allies')}; target hostile {row.get('target_hostile')}",
                "cost": str(row.get("cost") or "Native job: labor, ingredients and time away from colony work."),
                "inaction": f"Keep present job and conditions: {row.get('inspect') or facts.get('conditions')}",
                "uncertainty": f"Current target/worker facts: {facts}; success and consequences not yet observed.",
            }
        criteria["defer"] = "Keep current jobs and resources; reconsider later."
        effects["defer"] = assess(action, snapshot)
        key, raw = ask_laya_choice(agent, {"option_effects": effects, "decision_facts": {
            "endgame": state.get("endgame"), "threats": snapshot.get("map", {}).get("enemies"),
            "downed": sum(bool(p.get("downed")) for p in snapshot.get("colonists") or [])}},
            action + "_" + stage, "Compare this actual effect and its downside, including doing nothing.", criteria)
        raw_steps.append(raw)
        if key == "defer":
            return {"defer": True}, {"steps": raw_steps}
        selected = groups[aliases[key]]
        rows = {row["key"]: row for row in selected}
    # Every remaining option has the same observed label, target and worker.
    # Refuse ambiguity instead of picking a potentially different hidden action.
    if len(rows) != 1:
        return {"defer": True}, {"steps": raw_steps, "reason": "ambiguous_native_action"}
    row = next(iter(rows.values()))
    return {**{k: row[k] for k in ("key", "kind", "pawn_id", "target_id", "ability", "label") if k in row},
            "decision_evidence": evidence(row)}, {"steps": raw_steps}

def execute(client: Any, snapshot: dict, map_state: dict, action: str, selected: dict) -> dict:
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    memory = map_state.setdefault("affordance_cooldowns", {})
    if selected.get("defer"):
        memory[action] = tick
        return {"applied": False, "reason": "laya_deferred"}
    live = collect(client, snapshot)
    keys = ("kind", "pawn_id", "target_id", "ability", "label")
    payload = {k: selected[k] for k in keys if k in selected}
    match = [row for row in live.get("options") or [] if row.get("key") == selected.get("key")
             and {k: row[k] for k in keys if k in row} == payload]
    expected = {"affordances_ability": "ability", "affordances_interaction": "menu", "affordances_scanner": "scanner"}.get(action)
    if len(match) != 1 or payload.get("kind") != expected:
        return {"applied": False, "reason": "selection_no_longer_feasible"}
    if "decision_evidence" in selected and selected["decision_evidence"] != evidence(match[0]):
        return {"applied": False, "reason": "actor_target_or_cost_changed"}
    result = client.post("/api/v1/affordances/order", body={"map_id": snapshot["map"]["id"], **payload})
    memory[str(selected["key"])] = tick
    return result if isinstance(result, dict) and isinstance(result.get("applied"), bool) else {
        "applied": False, "reason": "invalid_native_response"}

def summary(snapshot: dict) -> dict:
    context = snapshot.get("development", {}).get("affordances", {})
    return {"native_abilities": {"count": len(context.get("abilities") or [])},
            "native_interactions": {"count": len(context.get("options") or [])}}
