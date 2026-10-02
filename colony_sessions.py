"""Complete live native choices before normal work can supersede them."""
from __future__ import annotations
from typing import Any
from laya_decisions import ask_laya_choice
import colony_modules

def ending_result(value: Any) -> dict | None:
    if not isinstance(value, dict) or value.get("victory_verified") is not True:
        return None
    if not isinstance(value.get("ending_tick"), int) or value["ending_tick"] < 0:
        return None
    return {"mode": "victory", "ending": dict(value), "decision": {"choice": "stop_director"},
            "result": {"applied": False, "reason": "native_ending_confirmed"}}


def terminal_result(value: Any) -> dict | None:
    victory = ending_result(value)
    if victory:
        return victory
    if isinstance(value, dict) and value.get("game_over_verified") is True:
        return {"mode": "game-over", "ending": dict(value), "decision": {"choice": "stop_director"},
                "result": {"applied": False, "reason": "native_game_over_confirmed"}}
    return None


def target_group_facts(members: list[dict]) -> str:
    """Keep urgent and hostile subjects visible even when they occur late."""
    health = [r["health"] for r in members if isinstance(r.get("health"), (float, int))]
    bleeding = max((r.get("bleed_rate") or 0 for r in members), default=0)
    examples = sorted(members, key=lambda r: (not r.get("downed"), -(r.get("bleed_rate") or 0),
                      r.get("health") if isinstance(r.get("health"), (float, int)) else 1))[:3]
    return (f"{len(members)} targets; downed {sum(bool(r.get('downed')) for r in members)}; "
            f"hostile {sum(bool(r.get('hostile')) for r in members)}; min health {min(health, default=None)}; "
            f"max bleed {bleeding}; examples " + "; ".join(
                f"{r.get('label')} {str(r.get('conditions') or r.get('inspect') or '')[:100]}" for r in examples))

def target_choice(agent: Any, context: dict, previous: dict | None = None) -> tuple[dict, dict]:
    rows = {r["key"]: r for r in context.get("options") or [] if isinstance(r, dict) and r.get("key")}
    steps = []
    for stage in ("kind", "x_band", "z_band", "target"):
        groups: dict[str, list[dict]] = {}
        for key, row in rows.items():
            group = (str(row.get("kind")) if stage == "kind" else
                     str(int(row.get(stage[0]) or 0) // 16) if stage in {"x_band", "z_band"} else key)
            groups.setdefault(group, []).append(row)
        choices, effects = {}, {}
        for index, (key, members) in enumerate(groups.items()):
            row = members[0]
            facts = target_group_facts(members)
            choices[key] = (f"{stage} {key}: {facts}"
                            if stage != "target" else f"{row.get('label')} at {row.get('x')},{row.get('z')}")
            effects[key] = {
                "benefit": f"{context.get('effect_label')}: {facts}. {context.get('effect_description')}",
                "risk": f"Group fire {any(r.get('fire') for r in members)}, max nearby enemies {max((r.get('hostiles_within_twenty') or 0 for r in members), default=0)}, max nearby allies {max((r.get('allies_within_five') or 0 for r in members), default=0)}. Check collateral effects.",
                "cost": f"{context.get('effect_cost')}; temperature {row.get('temperature')}, roof {row.get('roof')}.",
                "inaction": "Cancel preserves resources but gives up this target/effect.",
                "uncertainty": f"{facts}. Native validity proves legal targeting only.",
            }
        choices["cancel"] = "Cancel this pending native target choice without casting or spending the permit."
        effects["cancel"] = {"benefit": "Keep resources and current jobs.", "risk": "Desired aid or ability is delayed.",
                             "cost": "No cast/permit.", "inaction": "This targeting session closes.", "uncertainty": "A new request can be chosen later."}
        selected, raw = ask_laya_choice(agent, {"option_effects": effects,
            "decision_facts": {"source": context.get("source"), "caster": context.get("caster")},
            "last_outcome": previous or {}}, "native_target_" + stage,
            "Choose the native effect target, including hazards, nearby allies and its original purpose, or cancel.", choices)
        steps.append(raw)
        if selected == "cancel":
            return {"session_id": context["session_id"], "map_id": context["map_id"], "cancel": True,
                    "target_id": 0, "x": 0, "z": 0}, {"steps": steps}
        rows = {r["key"]: r for r in groups[selected]}
    row = next(iter(rows.values()))
    return {"session_id": context["session_id"], "map_id": context["map_id"],
            "target_id": row.get("target_id") or 0, "x": row["x"], "z": row["z"], "cancel": False}, {"steps": steps}

def run_pending(client: Any, agent: Any, snapshot: dict, map_state: dict, *, world_only=False) -> dict | None:
    windows = client.get("/api/v1/ui/windows") or []
    top = next((w for w in reversed(windows) if w.get("force_pause") or w.get("blocks_input")), None)
    targeting = client.get("/api/v1/affordances/targeting") if top is None and not world_only else {}
    if isinstance(targeting, dict) and targeting.get("active"):
        selected, raw = target_choice(agent, targeting, map_state.get("native_intent"))
        result = client.post("/api/v1/affordances/targeting", query=selected)
        return {"mode": "native-target", "decision": {"choice": "cancel" if selected["cancel"] else "target",
                "selected": selected, "raw": raw}, "result": result}
    # No module may reach through a higher unhandled modal window.
    candidates = [m for m in colony_modules.modules()
                  if top and top.get("window_type") in getattr(m, "PENDING_WINDOWS", ())]
    # Archonexus/gravship destination selection is a world target rather than a
    # force-paused Window. The progression module explicitly reports its state.
    if top is None:
        candidates = [m for m in colony_modules.modules() if (not world_only or m.__name__ == "colony_progression")
                      and getattr(m, "peek_pending", lambda _: False)(client)]
    if world_only:
        candidates = [m for m in candidates if m.__name__ == "colony_progression"]
    for module in candidates:
        name = module.__name__.removeprefix("colony_")
        snapshot.setdefault("development", {})[name] = module.collect(client, snapshot)
        module.prepare(snapshot, map_state)
        action = getattr(module, "pending_action", lambda _: None)(snapshot["development"][name])
        if action is None:
            continue
        selected, raw = module.choose(agent, {"pending_native_choice": True}, action, snapshot)
        result = colony_modules.execute(client, snapshot, map_state, action, selected)
        return {"mode": "native-continuation", "decision": {"choice": action, "selected": selected, "raw": raw}, "result": result}
    if top and (not world_only or top.get("window_type") in ("Dialog_ChooseThingsForNewColony", "Dialog_ConfigureIdeo", "Screen_ArchonexusSettlementCinematics")):
        key = str(top.get("window_id")) + ":" + str(top.get("window_type"))
        quiet = map_state.get("blocked_native_window") == key
        map_state["blocked_native_window"] = key
        return {"mode": "native-window-wait", "quiet": quiet,
                "decision": {"choice": "wait_for_native_window", "window": top.get("window_type")},
                "result": {"applied": False, "reason": "pending_native_window", "completion": "unverified"}}
    map_state.pop("blocked_native_window", None)
    return None
