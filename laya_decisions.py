"""Typed Laya choice protocol shared by development and combat.

An option set is not a prewritten plan: callers discover feasible affordances
from live RimWorld state, then use this adapter to keep every option reachable
within the decision head's limited prompt budget.
"""

from __future__ import annotations

import json
from typing import Any


def _bounded_question(agent: Any, instructions: str, options: dict[str, str]) -> dict[str, Any]:
    """Reserve Laya's short decision head for every option, not just the first few."""
    tokenizer = getattr(agent, "tok", None)
    if tokenizer is None:
        return {"type": "choice", "instructions": instructions, "criteria": options}
    config = getattr(agent, "cfg", {}) or {}
    head_limit = int(config.get("head_max_len", 192))
    instruction = str(instructions)
    while len(tokenizer(f"choice question: {instruction}", add_special_tokens=False)["input_ids"]) > 28:
        instruction = instruction[:max(8, len(instruction) - 16)]
    per_option = min(45, max(8, (head_limit - 36) // max(1, len(options)) - 1))
    criteria = {}
    for key, value in options.items():
        description = str(value)
        while description and len(tokenizer(f" {key}: {description}", add_special_tokens=False)["input_ids"]) > per_option:
            description = description[:max(0, len(description) - 12)]
        criteria[key] = description
    return {"type": "choice", "instructions": instruction, "criteria": criteria}


def _detailed_state(agent: Any, state: dict[str, Any], options: dict[str, str]) -> dict[str, Any]:
    """Reserve space for both alternatives before the encoder truncates state."""
    facts = state.get("choice_context") or {k: state[k] for k in
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

    visible = {"decision_facts": clip(facts, budget // 3),
               "alternatives": {k: clip(v, budget // 3) for k, v in options.items()},
               "colony": clip(state, budget // 6)}
    # JSON keys/escaping take space too. Shrink the largest text, keeping every
    # option key and a fair prefix of both descriptions in the bounded state.
    while size(visible) > budget:
        entries = [(visible, "decision_facts"), (visible, "colony")]
        entries.extend((visible["alternatives"], k) for k in options)
        container, key = max(entries, key=lambda pair: len(pair[0][pair[1]]))
        text = container[key]
        if not text:
            break
        container[key] = text[:max(0, len(text) * 4 // 5)]
    return visible


def ask_laya_choice(agent: Any, state: dict[str, Any], question_id: str,
                    instructions: str, options: dict[str, str], *, detailed: bool = False) -> tuple[str, dict[str, Any]]:
    """Run a bounded tournament: every offered option is actually seen by Laya."""
    if not options:
        raise ValueError(f"No feasible options for {question_id}")
    if len(options) == 1:
        selected = next(iter(options))
        return selected, {"question": {"id": question_id, "instructions": instructions, "criteria": options},
                          "answers": {question_id: {"choice": selected, "confidence": 1.0,
                          "probabilities": {selected: 1.0}, "resolved_without_model": True}}}
    remaining = dict(options)
    narrowing: list[dict[str, Any]] = []
    round_number = 0
    group_size = 2 if detailed else 6

    def predict(stage_id: str, chunk: dict[str, str]) -> dict[str, Any]:
        question = _bounded_question(agent, instructions, chunk)
        # The decision head has a small option-description budget. Medical,
        # crop and equipment comparisons reserve space for both alternatives
        # before the broader colony context can be truncated.
        visible = _detailed_state(agent, state, chunk) if detailed else state
        result = agent.predict(visible, {stage_id: question})
        result["question"] = {"id": stage_id, **question}
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
