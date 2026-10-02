"""Domain boundaries for observation, proposals, native choice and execution.

Only registered Python modules can execute commands. A model selects an action
identifier and typed parameters, never code or a URL. Collection failures are
visible and suppress that domain's proposals until a fresh read succeeds.
"""
from __future__ import annotations

import importlib
import time
from functools import lru_cache
from typing import Any


MODULE_NAMES = ("production", "society", "progression", "specialists")


@lru_cache(maxsize=1)
def modules() -> tuple[Any, ...]:
    loaded = tuple(importlib.import_module(f"colony_{name}") for name in MODULE_NAMES)
    actions: set[str] = set()
    for name, module in zip(MODULE_NAMES, loaded):
        for method in ("collect", "prepare", "choose", "execute", "assess"):
            if not callable(getattr(module, method, None)):
                raise TypeError(f"{module.__name__} lacks {method}")
        for action in module.ACTIONS:
            if action in actions or not action.startswith(name + "_"):
                raise ValueError(f"Invalid or duplicate module action {action}")
            if action not in module.DESCRIPTIONS or action not in module.DOMAINS:
                raise ValueError(f"Incomplete module action {action}")
            actions.add(action)
    return loaded


def owner(action: str) -> Any | None:
    return next((module for module in modules() if action in module.ACTIONS), None)


def signals(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Compact nonzero domain hazards; detailed subjects stay in their module."""
    result = {}
    for module in modules():
        summarize = getattr(module, "summary", None)
        if summarize is None:
            continue
        for key, value in summarize(snapshot).items():
            if isinstance(value, dict):
                if int(value.get("count") or 0) > 0:
                    result[key] = value["count"]
                if int(value.get("unfrozen_wastepacks") or 0) > 0:
                    result["unfrozen_wastepacks"] = value["unfrozen_wastepacks"]
    return result


def collect(client: Any, snapshot: dict[str, Any]) -> None:
    dev = snapshot.setdefault("development", {})
    status = dev.setdefault("module_status", {})
    for name, module in zip(MODULE_NAMES, modules()):
        started = time.perf_counter()
        try:
            data = module.collect(client, snapshot)
            if not isinstance(data, dict):
                raise TypeError("module observation must be an object")
            if data.get("available") is False:
                raise ValueError(str(data.get("reason") or "module context unavailable"))
            dev[name] = data
            status[name] = {"available": True}
        except Exception as exc:
            # No stale fallback: obsolete targets are worse than an unavailable
            # discretionary capability. Other domains can still care for people.
            dev[name] = {}
            status[name] = {"available": False, "error": str(exc)[:240]}
            snapshot.setdefault("warnings", []).append(f"{name}: {str(exc)[:240]}")
        status[name]["read_ms"] = round((time.perf_counter() - started) * 1000, 1)


def prepare(snapshot: dict[str, Any], map_state: dict[str, Any]) -> list[str]:
    result: list[str] = []
    dev = snapshot.setdefault("development", {})
    for name, module in zip(MODULE_NAMES, modules()):
        if (dev.get("module_status", {}).get(name) or {}).get("available") is False:
            continue
        proposed = module.prepare(snapshot, map_state)
        if any(action not in module.ACTIONS for action in proposed):
            raise ValueError(f"{name} proposed an unregistered action")
        result.extend(proposed)
    dev["module_candidates"] = list(dict.fromkeys(result))
    return dev["module_candidates"]


def choose(agent: Any, state: dict[str, Any], action: str,
           snapshot: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    module = owner(action)
    if module is None:
        raise ValueError(f"Unknown module action {action}")
    return module.choose(agent, state, action, snapshot)


def execute(client: Any, snapshot: dict[str, Any], map_state: dict[str, Any],
            action: str, selected: dict[str, Any]) -> dict[str, Any]:
    module = owner(action)
    if module is None:
        raise ValueError(f"Unknown module action {action}")
    result = module.execute(client, snapshot, map_state, action, selected)
    if not isinstance(result, dict) or not isinstance(result.get("applied"), bool):
        raise TypeError(f"{action} must report applied=true/false; command acceptance is not completion")
    return result
