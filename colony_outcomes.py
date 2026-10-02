"""Bounded command/outcome memory without assuming causation or completion."""
from __future__ import annotations

from typing import Any


def measurements(snapshot: dict[str, Any]) -> dict[str, Any]:
    people = snapshot.get("colonists") or []
    dev = snapshot.get("development") or {}
    resources = (snapshot.get("map") or {}).get("resources") or {}
    return {"colonists_on_map": len(people),
            "downed": sum(bool(p.get("downed")) for p in people),
            "meals": resources.get("meals"),
            "nutrition": resources.get("nutrition"),
            "construction_projects": len(dev.get("construction_projects") or []),
            "finished_research": len(dev.get("finished_research") or []),
            "threats": (snapshot.get("map") or {}).get("enemies")}


def reconcile(snapshot: dict[str, Any], map_state: dict[str, Any]) -> dict[str, Any]:
    snapshot.setdefault("development", {}).pop("outcome_feedback", None)
    tick = int((snapshot.get("game") or {}).get("tick") or 0)
    prior = map_state.get("last_action_observation")
    if not isinstance(prior, dict):
        return {}
    if tick < prior["tick"]:
        # Save reload/replay is a different timeline; do not attribute its
        # changes to the previous order or feed obsolete results into Laya.
        map_state.pop("last_action_observation", None)
        feedback = {"status": "timeline_reset"}
        snapshot["development"]["outcome_feedback"] = feedback
        return feedback
    if tick == prior["tick"]:
        feedback = {"action": prior["action"], "command": prior["command"],
                    "status": "awaiting_game_progress", "completion": "unverified"}
        snapshot["development"]["outcome_feedback"] = feedback
        return feedback
    after = measurements(snapshot)
    changes = {key: {"before": value, "after": after.get(key)}
               for key, value in prior["before"].items()
               if value is not None and after.get(key) is not None and value != after[key]}
    feedback = {"action": prior["action"], "command": prior["command"],
                "reason": prior.get("reason", ""), "elapsed_ticks": tick - prior["tick"],
                "status": "observed_changes" if changes else "no_measured_change",
                "changes": changes, "causation": "not_established", "completion": "unverified"}
    snapshot.setdefault("development", {})["outcome_feedback"] = feedback
    return feedback


def record(snapshot: dict[str, Any], map_state: dict[str, Any], action: str, result: Any) -> None:
    applied = result.get("applied") if isinstance(result, dict) else None
    command = "accepted" if applied is True else "not_applied" if applied is False else "unconfirmed"
    map_state["last_action_observation"] = {
        "tick": int((snapshot.get("game") or {}).get("tick") or 0),
        "action": action, "command": command,
        "reason": str(result.get("reason") or result.get("error") or "")[:160] if isinstance(result, dict) else "",
        "before": measurements(snapshot)}
