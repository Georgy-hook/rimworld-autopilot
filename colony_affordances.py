"""Loaded native abilities and thing interactions, with staged bounded choices."""
from __future__ import annotations
from typing import Any
import hashlib
import json
from laya_decisions import ask_laya_choice
from colony_retry import failure_record, recent as retry_recent

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

def semantic_identity(row: dict) -> str:
    payload = {k: row.get(k) for k in ("kind", "pawn_id", "target_id", "ability", "label")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]


def state_fingerprint(value: Any) -> str:
    """Keep discrete clinical urgency, costs and consequences, not float noise."""
    def discrete(v):
        if isinstance(v, dict):
            return {**({"health_band": "critical" if v["health"] < .5 else "injured" if v["health"] < .8 else "stable"} if isinstance(v.get("health"), (int, float)) else {}),
                    **{k: discrete(x) for k, x in v.items() if k not in {"health", "bleed_rate", "severity", "food", "mood", "job", "name"}}}
        if isinstance(v, list): return [discrete(x) for x in v]
        if isinstance(v, float): return round(v, 2)
        return v
    return hashlib.sha256(json.dumps(discrete(value), sort_keys=True).encode()).hexdigest()[:24]


def _remember(memory, row, tick, retry_ticks, *, accepted=False, failed=False):
    memory[semantic_identity(row)] = {**(failure_record(tick) if failed else {"tick": tick}), "retry_ticks": retry_ticks,
                                      "fingerprint": None if accepted else row.get("retry_fingerprint") or state_fingerprint(evidence(row))}


def prepare(snapshot: dict, map_state: dict) -> list[str]:
    dev = snapshot.setdefault("development", {}).setdefault("affordances", {})
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    cooldowns = map_state.setdefault("affordance_cooldowns", {})
    for key, previous in list(cooldowns.items()):
        if not isinstance(previous, dict) or not isinstance(previous.get("tick"), int) or not isinstance(previous.get("retry_ticks"), int) or not retry_recent(previous, tick, previous["retry_ticks"]):
            cooldowns.pop(key)
    options = {a: {} for a in ACTIONS}
    for row in dev.get("options") or []:
        action = {"ability": "affordances_ability", "menu": "affordances_interaction", "scanner": "affordances_scanner"}.get(row.get("kind"))
        prior = cooldowns.get(semantic_identity(row)) or {}
        fingerprint = state_fingerprint(evidence(row))
        cooling = bool(prior) and (prior.get("fingerprint") is None or prior["fingerprint"] == fingerprint)
        if action and row.get("key") and not cooling:
            options[action][row["key"]] = row
    dev["candidates"] = options
    return [a for a, rows in options.items() if rows]

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
    result = stable({k: row.get(k) for k in ("cost", "risk", "pawn", "target_pawn", "target_hostile", "affected_allies", "scanner_facts")})
    for field in ("pawn", "target_pawn"):
        if isinstance(result.get(field), dict):
            # Natural hunger/mood drift and switching between ordinary jobs do
            # not invalidate an unchanged action. Native execution still checks
            # availability/protected jobs. Clinical stage/identity remain bound.
            for transient in ("food", "mood", "job", "name"):
                result[field].pop(transient, None)
    return result


def evidence_changed(prior: Any, current: Any) -> bool:
    if isinstance(prior, dict) and isinstance(current, dict):
        return set(prior) != set(current) or any(evidence_changed(prior[key], current[key]) for key in prior)
    if isinstance(prior, list) and isinstance(current, list):
        return len(prior) != len(current) or any(evidence_changed(a, b) for a, b in zip(prior, current))
    if isinstance(prior, float) and isinstance(current, float):
        return abs(prior - current) > 0.020001
    return prior != current

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
            scanners = [r["scanner_facts"] for r in members if r.get("scanner_facts")]
            scanner_note = (f"Scanner {','.join(dict.fromkeys(str(r.get('state')) for r in scanners))}; occupant {','.join(dict.fromkeys(str(r.get('occupant_id')) for r in scanners))}; selected person {','.join(dict.fromkeys(str(r.get('selected_pawn_id')) for r in scanners))}; " if scanners else "")
            costs = [r.get("cost") for r in members]
            if all(isinstance(c, dict) for c in costs):
                cost_note = {"psyfocus": max((c.get("psyfocus") or 0 for c in costs), default=0), "heat": max((c.get("heat") or 0 for c in costs), default=0), "charges": min((c["charges"] for c in costs if isinstance(c.get("charges"), (int, float)) and c["charges"] >= 0), default=-1)}
            else:
                cost_note = "; ".join(dict.fromkeys(str(c) for c in costs if c))[:240]
            risks = "; ".join(dict.fromkeys(str(r.get("risk") or "") for r in members))[:240]
            collateral = max((r.get("affected_allies") or 0 for r in members), default=0)
            hostile = any(r.get("target_hostile") for r in members)
            effects[key] = {
                "benefit": scanner_note + str(row.get("description") or row.get("label") or "")[:400],
                "risk": scanner_note + f"maximum allies in area {collateral}; target hostile {hostile}; {risks}",
                "cost": str(cost_note or "Native job: labor, ingredients and time away from colony work."),
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
            return {"defer": True, "defer_options": [{**r, "retry_fingerprint": state_fingerprint(evidence(r))} for r in rows.values()]}, {"steps": raw_steps}
        selected = groups[aliases[key]]
        rows = {row["key"]: row for row in selected}
    # Every remaining option has the same observed label, target and worker.
    # Refuse ambiguity instead of picking a potentially different hidden action.
    if len(rows) != 1:
        return {"defer": True}, {"steps": raw_steps, "reason": "ambiguous_native_action"}
    row = next(iter(rows.values()))
    return {**{k: row[k] for k in ("key", "kind", "pawn_id", "target_id", "ability", "label") if k in row},
            "decision_evidence": evidence(row), "retry_fingerprint": state_fingerprint(evidence(row))}, {"steps": raw_steps}

def execute(client: Any, snapshot: dict, map_state: dict, action: str, selected: dict) -> dict:
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    memory = map_state.setdefault("affordance_cooldowns", {})
    if selected.get("defer"):
        for row in selected.get("defer_options") or []:
            _remember(memory, row, tick, 2500)
        return {"applied": False, "reason": "laya_deferred"}
    try:
        live = collect(client, snapshot)
    except Exception as exc:
        _remember(memory, selected, tick, 150, failed=True)
        return {"applied": False, "reason": "native_context_failed", "error": str(exc)}
    keys = ("kind", "pawn_id", "target_id", "ability", "label")
    payload = {k: selected[k] for k in keys if k in selected}
    match = [row for row in live.get("options") or [] if row.get("key") == selected.get("key")
             and {k: row[k] for k in keys if k in row} == payload]
    expected = {"affordances_ability": "ability", "affordances_interaction": "menu", "affordances_scanner": "scanner"}.get(action)
    if len(match) != 1 or payload.get("kind") != expected:
        _remember(memory, selected, tick, 150, failed=True)
        return {"applied": False, "reason": "selection_no_longer_feasible"}
    prior = selected.get("decision_evidence")
    live_evidence = evidence(match[0])
    # Costs and collateral never use clinical tolerance.
    changed = prior is not None and (any(prior.get(k) != live_evidence.get(k) for k in ("cost", "risk", "target_hostile", "affected_allies", "scanner_facts"))
        or any(evidence_changed(prior.get(k), live_evidence.get(k)) for k in ("pawn", "target_pawn")))
    if changed:
        _remember(memory, selected, tick, 150, failed=True)
        return {"applied": False, "reason": "actor_target_or_cost_changed"}
    try:
        result = client.post("/api/v1/affordances/order", body={"map_id": snapshot["map"]["id"], **payload})
    except Exception as exc:
        _remember(memory, selected, tick, 150, failed=True)
        return {"applied": False, "reason": "native_order_failed", "error": str(exc)}
    valid = isinstance(result, dict) and isinstance(result.get("applied"), bool)
    accepted = valid and result["applied"]
    _remember(memory, selected, tick, 2500 if accepted else 150, accepted=accepted, failed=not accepted)
    return result if valid else {"applied": False, "reason": "invalid_native_response"}


def summary(snapshot: dict) -> dict:
    context = snapshot.get("development", {}).get("affordances", {})
    return {"native_abilities": {"count": len(context.get("abilities") or [])},
            "native_interactions": {"count": len(context.get("options") or [])}}
