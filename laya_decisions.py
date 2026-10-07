"""Typed Laya choice protocol shared by development and combat.

An option set is not a prewritten plan: callers discover feasible affordances
from live RimWorld state, then use this adapter to keep every option reachable
within the decision head's limited prompt budget.
"""

from __future__ import annotations

import json
from typing import Any


class NoFeasibleChoice(ValueError):
    """An affordance expired; this is not a failed model inference."""

    def __init__(self, question_id: str):
        self.question_id = question_id
        super().__init__(f"No feasible options for {question_id}")


def _consequence_state(agent: Any, state: dict[str, Any], options: dict[str, str]) -> dict[str, Any]:
    """Pack both upside and downside for each compared option, within budget.

    Allocate by field, not by prefix of a giant JSON document. Otherwise a long
    benefit description erases every risk appearing later in the observation.
    No extra model critique call or uncalibrated risk score is introduced.
    """
    tokenizer = getattr(agent, "tok", None)
    config = getattr(agent, "cfg", {}) or {}
    budget = int(config.get("max_len", 512)) - int(config.get("head_max_len", 192)) - 8
    if budget < 96:
        raise ValueError("Laya state budget is too small for consequence comparisons")
    fields = ("benefit", "risk", "cost", "inaction", "uncertainty")
    source = state.get("option_effects") or {}
    facts = state.get("decision_facts") or state.get("choice_context") or {}
    visible = {"facts": facts, "effects": {key: {field: str((source.get(key) or {}).get(field) or "Unknown")
                                                      for field in fields} for key in options}}
    if state.get("last_outcome"):
        visible["last_outcome"] = str(state["last_outcome"])
    if tokenizer is None:
        return visible

    # Cache only within this prediction: bounded lifetime, no accumulating map
    # histories or large model/tokenizer references held across colonies.
    counts: dict[str, int] = {}

    def size(value: Any) -> int:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
        if text not in counts:
            counts[text] = len(tokenizer(text, add_special_tokens=False)["input_ids"])
        return counts[text]

    def clip(value: Any, limit: int) -> str:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if size(text[:mid]) <= limit:
                lo = mid
            else:
                hi = mid - 1
        return text[:lo]

    # Start with equal field budgets. Risk and benefit cannot be crowded out
    # by one another, and a long action ID is counted in the complete envelope.
    limit = max(4, (budget - 100) // max(1, len(options) * len(fields)))
    care_risks = facts.get("care_risks") if isinstance(facts, dict) else None
    quest_colony = facts.get("quest_colony") if isinstance(facts, dict) else None
    protected_units = {key: value for key, value in (("care_risks", care_risks), ("quest_colony", quest_colony))
                       if isinstance(value, dict) and value}
    joint_facts = "care_risks" in protected_units and "quest_colony" in protected_units
    if joint_facts:
        # The quest collector and clinical collector overlap. Preserve one
        # complete observation instead of spending the window on duplicate keys.
        care_risks = dict(care_risks)
        for clinical_key, colony_key in (("meals", "meals"), ("downed", "downed"), ("threats", "enemies"),
                                         ("bleed_rate_max", "bleeding")):
            if clinical_key in care_risks and colony_key in quest_colony and care_risks[clinical_key] == quest_colony[colony_key]:
                care_risks.pop(clinical_key)
        protected_units["care_risks"] = care_risks
    protected_facts = bool(protected_units)
    compact_thermal = False
    # The collector bounds this factual unit: preserve current clinical and
    # recreation needs together, including cases without a thermal condition.
    visible["facts"] = protected_units if protected_facts else clip(facts, min(64, budget // 5))
    if "last_outcome" in visible:
        visible["last_outcome"] = clip(visible["last_outcome"], 32)
    for row in visible["effects"].values():
        for field in fields:
            row[field] = clip(row[field], limit)
    while size(visible) > budget:
        # Shrink all compared options symmetrically, retaining named fields.
        if limit > 2:
            limit -= 1
            for row in visible["effects"].values():
                for field in fields:
                    row[field] = clip(row[field], limit)
        elif protected_facts and "last_outcome" in visible:
            visible.pop("last_outcome")
        elif joint_facts and not compact_thermal and isinstance(care_risks.get("thermal"), dict):
            # Retain every condition/value/stage/danger flag in readable text.
            # This is a lossless change of representation, not prefix clipping.
            compact_thermal = True
            care_risks["thermal"] = "; ".join(
                str(name) + " " + ", ".join(f"{key} {value}" for key, value in row.items())
                if isinstance(row, dict) else f"{name} {row}"
                for name, row in care_risks["thermal"].items())
        elif visible["facts"] and not protected_facts:
            visible["facts"] = clip(visible["facts"], max(0, size(visible["facts"]) - 4))
        else:
            raise ValueError("Consequence envelope exceeds Laya state budget")
    return visible


def _bounded_question(agent: Any, instructions: str, options: dict[str, str]) -> dict[str, Any]:
    """Reserve Laya's short decision head for every option, not just the first few."""
    tokenizer = getattr(agent, "tok", None)
    if tokenizer is None:
        return {"type": "choice", "instructions": instructions, "criteria": options}
    config = getattr(agent, "cfg", {}) or {}
    head_limit = int(config.get("head_max_len", 192))
    def clip(prefix: str, value: str, budget: int) -> str:
        lo, hi = 0, len(value)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if len(tokenizer(prefix + value[:mid], add_special_tokens=False)["input_ids"]) <= budget:
                lo = mid
            else:
                hi = mid - 1
        return value[:lo]

    instruction = clip("choice question: ", str(instructions), 28)
    per_option = min(45, max(8, (head_limit - 36) // max(1, len(options)) - 1))
    criteria = {}
    for key, value in options.items():
        criteria[key] = clip(f" {key}: ", str(value), per_option)
    return {"type": "choice", "instructions": instruction, "criteria": criteria}


def _detailed_state(agent: Any, state: dict[str, Any], options: dict[str, str]) -> dict[str, Any]:
    """Reserve space for both alternatives before the encoder truncates state."""
    facts = state.get("choice_context") or state.get("decision_facts") or {k: state[k] for k in
        ("growth", "trade", "owned_parts", "patient_roles_beliefs") if k in state}
    visible = {"decision_facts": facts, "alternatives": options, "colony": state}
    tokenizer = getattr(agent, "tok", None)
    if tokenizer is None:
        return visible
    config = getattr(agent, "cfg", {}) or {}
    budget = max(64, int(config.get("max_len", 512)) - int(config.get("head_max_len", 192)) - 8)

    def encode(value: Any) -> str:
        return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)

    def size(value: Any) -> int:
        payload = encode(value)
        try:
            return len(tokenizer(payload, add_special_tokens=False, truncation=True,
                                 max_length=budget + 1)["input_ids"])
        except TypeError:
            return len(tokenizer(payload, add_special_tokens=False)["input_ids"])

    def clip(value: Any, limit: int) -> str:
        payload = encode(value)
        lo, hi = 0, len(payload)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if size(payload[:mid]) <= limit:
                lo = mid
            else:
                hi = mid - 1
        return payload[:lo]

    # Small explicit facts are a complete record, not prose to cut mid-JSON.
    # Callers with larger domain context still receive bounded text, while
    # concise parameter prerequisites survive every narrowing comparison.
    protected_facts = isinstance(facts, dict) and bool(facts) and size(facts) <= budget // 3
    visible = {"decision_facts": facts if protected_facts else clip(facts, budget // 3),
               "alternatives": {k: clip(v, budget // 3) for k, v in options.items()},
               "colony": clip(state, budget // 6)}
    # JSON keys/escaping take space too. Shrink the largest text, keeping every
    # option key and a fair prefix of both descriptions in the bounded state.
    while size(visible) > budget:
        entries = [(visible, "colony")]
        if not protected_facts:
            entries.append((visible, "decision_facts"))
        entries.extend((visible["alternatives"], k) for k in options)
        container, key = max(entries, key=lambda pair: len(pair[0][pair[1]]))
        text = container[key]
        if not text:
            raise ValueError("Detailed comparison facts and option identifiers exceed Laya state budget")
        container[key] = text[:max(0, len(text) * 4 // 5)]
    return visible


def ask_laya_choice(agent: Any, state: dict[str, Any], question_id: str,
                    instructions: str, options: dict[str, str], *, detailed: bool = False) -> tuple[str, dict[str, Any]]:
    """Run a bounded tournament: every offered option is actually seen by Laya."""
    if not options:
        raise NoFeasibleChoice(question_id)
    if len(options) == 1:
        selected = next(iter(options))
        return selected, {"question": {"id": question_id, "instructions": instructions, "criteria": options},
                          "answers": {question_id: {"choice": selected, "confidence": 1.0,
                          "probabilities": {selected: 1.0}, "resolved_without_model": True}}}
    remaining = dict(options)
    narrowing: list[dict[str, Any]] = []
    round_number = 0
    consequences = bool(state.get("option_effects"))
    tokenizer = getattr(agent, "tok", None)
    config = getattr(agent, "cfg", {}) or {}
    state_budget = int(config.get("max_len", 512)) - int(config.get("head_max_len", 192)) - 8
    oversized = tokenizer is not None and len(tokenizer(
        json.dumps(state, ensure_ascii=False, default=str), add_special_tokens=False)["input_ids"]) > state_budget
    # Legacy event/doctrine/commerce callers can supply unbounded state too.
    # Never rely on build_sequence silently truncating it after we log it as seen.
    detailed = detailed or (oversized and not consequences)
    group_size = 2 if detailed or consequences else 6

    def predict(stage_id: str, chunk: dict[str, str]) -> dict[str, Any]:
        question = _bounded_question(agent, instructions, chunk)
        # The decision head has a small option-description budget. Medical,
        # crop and equipment comparisons reserve space for both alternatives
        # before the broader colony context can be truncated.
        visible = (_consequence_state(agent, state, chunk) if consequences else
                   _detailed_state(agent, state, chunk) if detailed else state)
        result = agent.predict(visible, {stage_id: question})
        result["question"] = {"id": stage_id, **question}
        result["visible_state"] = visible
        tokenizer = getattr(agent, "tok", None)
        if tokenizer is not None:
            config = getattr(agent, "cfg", {}) or {}
            result["prompt_budget"] = {
                "state_tokens": len(tokenizer(json.dumps(visible, ensure_ascii=False, default=str),
                                               add_special_tokens=False)["input_ids"]),
                "state_budget": int(config.get("max_len", 512)) - int(config.get("head_max_len", 192)) - 8,
                "compared_options": len(chunk),
            }
        return result

    while len(remaining) > group_size:
        rows = list(remaining.items())
        winners: dict[str, str] = {}
        for index in range(0, len(rows), group_size):
            chunk = dict(rows[index:index + group_size])
            if len(chunk) == 1:
                winners.update(chunk)
                continue
            stage_id = f"{question_id}_round_{round_number}_{index // group_size}"
            stage = predict(stage_id, chunk)
            selected = str((stage.get("answers") or {}).get(stage_id, {}).get("choice") or "")
            if selected not in chunk:
                raise ValueError(f"Laya returned invalid option {selected!r} for {stage_id}")
            winners[selected] = chunk[selected]
            narrowing.append(stage)
        remaining = winners
        round_number += 1
    raw = predict(question_id, remaining)
    selected = str((raw.get("answers") or {}).get(question_id, {}).get("choice") or "")
    if selected not in remaining:
        raise ValueError(f"Laya returned invalid option {selected!r} for {question_id}")
    if narrowing:
        raw = {**raw, "narrowing": narrowing}
    return selected, raw
