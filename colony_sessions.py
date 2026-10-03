"""Complete live native choices before normal work can supersede them."""
from __future__ import annotations
from typing import Any
import time
from laya_decisions import ask_laya_choice
import colony_modules



def transition_signature(value):
    """Observation identity without clocks, labels or ordinary movement drift."""
    import colony_affordances
    def stable(v):
        if isinstance(v, dict):
            transient = {'tick', 'ticks', 'expires_in_ticks', 'time', 'mood', 'food', 'name',
                         'position', 'current_job', 'job', 'inspect', 'key', '_transition_memory',
                         'bleed_rate', 'bleeding_rate', 'pain', 'severity', 'health', 'description',
                         'effect_description', 'temperature', 'distance', 'distance_to_nearest_opponent',
                         'eligible_actions', 'options_filtered', 'recent_configuration_effects'}
            fixed_cell = v.get('kind') in ('cell', 'odyssey', 'world-targeting') or v.get('operation') in ('land', 'place')
            result = {k: stable(x) for k, x in v.items()
                      if k not in transient and (k not in {'x', 'z'} or fixed_cell)}
            if fixed_cell and isinstance(v.get('position'), dict):
                result['target_cell'] = {k: v['position'].get(k) for k in ('x', 'z')}
            bleeding = v.get('bleed_rate', v.get('bleeding_rate'))
            health = v.get('health')
            if isinstance(health, (int, float)):
                result['health_urgency'] = 'critical' if health < .5 else 'injured' if health < .8 else 'stable'
            if isinstance(bleeding, (int, float)):
                result['bleeding_urgency'] = 'critical' if bleeding >= 2 else 'active' if bleeding > .05 else 'none'
            job = v.get('current_job', v.get('job'))
            if job in {'TendPatient', 'Rescue', 'FeedPatient', 'DoBill', 'EnterCryptosleepCasket', 'CarryToCryptosleepCasket'}:
                result['protected_job'] = job
            return result
        if isinstance(v, list):
            import json
            return sorted((stable(x) for x in v), key=lambda x: json.dumps(x, sort_keys=True, default=str))
        return v
    return colony_affordances.state_fingerprint(stable(value))



def target_readiness(context):
    fields = ('session_id', 'map_id', 'effect_identity', 'source', 'effect_cost', 'caster_facts')
    option_fields = ('target_id', 'kind', 'definition', 'hostile', 'downed', 'clinical', 'actual_cost',
                     'roof', 'fire', 'allies_within_five', 'affected_allies', 'hostiles_within_twenty')
    rows = []
    for row in context.get('options') or []:
        facts = {key: row.get(key) for key in option_fields}
        if row.get('kind') == 'cell':
            facts.update(x=row.get('x'), z=row.get('z'), position=row.get('position'))
        rows.append(facts)
    return transition_signature({**{key: context.get(key) for key in fields}, 'options': rows})


def transition_wait(memory, key, readiness):
    prior = memory.get(key)
    if not isinstance(prior, dict) or prior.get('readiness') != readiness or prior.get('status') not in ('accepted', 'rejected', 'unknown'):
        return False
    until = prior.get('until')
    return prior.get('status') in ('accepted', 'rejected') or (isinstance(until, (int, float)) and time.time() < until)


def transition_record(memory, key, readiness, result, *, recovery_seconds=60):
    accepted = isinstance(result, dict) and result.get('applied') is True
    reason = str((result or {}).get('reason', '') if isinstance(result, dict) else result).lower()
    deterministic = any(token in reason for token in ('invalid_contract', 'unsupported_action', 'unsupported contract'))
    memory[key] = {'readiness': readiness, 'status': 'accepted' if accepted else 'rejected' if deterministic else 'unknown',
                   'until': time.time() + recovery_seconds}
    while len(memory) > 128:
        memory.pop(next(iter(memory)))



def transition_memory(map_state, bucket, snapshot):
    import math
    map_id = (snapshot.get('map') or {}).get('id')
    map_key = bucket + '_map'
    if map_id is not None:
        if map_state.get(map_key) not in (None, map_id): map_state.pop(bucket, None)
        map_state[map_key] = map_id
    tick = (snapshot.get('game') or {}).get('tick')
    clock_key = bucket + '_tick'
    prior_tick = map_state.get(clock_key)
    if isinstance(tick, int) and not isinstance(tick, bool):
        if isinstance(prior_tick, int) and tick < prior_tick:
            map_state.pop(bucket, None)
        map_state[clock_key] = tick
    memory = map_state.get(bucket)
    if not isinstance(memory, dict):
        memory = {}; map_state[bucket] = memory
    for key, row in list(memory.items()):
        if not isinstance(key, str) or not isinstance(row, dict) or not isinstance(row.get('readiness'), str) or row.get('status') not in ('accepted', 'rejected', 'unknown') or isinstance(row.get('until'), bool) or not isinstance(row.get('until'), (int, float)) or not math.isfinite(row['until']):
            memory.pop(key, None)
    while len(memory) > 128:
        memory.pop(next(iter(memory)))
    return memory


def bind_campaign(state: dict, evidence: Any) -> None:
    """A saved native campaign identity separates a new game from a new map."""
    if not isinstance(evidence, dict) or not evidence.get("campaign_id"):
        return
    identity = str(evidence["campaign_id"])
    prior = state.get("campaign") or {}
    if prior.get("id") and prior["id"] != identity:
        for key in ("maps", "active_map_key", "native_session", "outcome"):
            state.pop(key, None)
        prior = {}
    state["campaign"] = {**prior, "id": identity}


def remember_campaign(state: dict, map_state: dict) -> None:
    campaign = state.get("campaign")
    if not campaign:
        return
    for key in ("doctrine", "doctrine_tick", "income_strategy", "native_intent"):
        if key in map_state:
            # Own the copy: a later per-map reset must not mutate campaign intent.
            import copy
            campaign[key] = copy.deepcopy(map_state[key])

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
            actual = [r.get("actual_cost") for r in members if isinstance(r.get("actual_cost"), dict)]
            native_cost = {"psyfocus": max((r.get("psyfocus") or 0 for r in actual), default=None),
                           "heat": max((r.get("heat") or 0 for r in actual), default=None),
                           "charges": min((r.get("charges") for r in actual if isinstance(r.get("charges"), (int, float)) and r["charges"] >= 0), default=-1)} if actual else context.get("effect_cost")
            stages = [stage for member in members for stage in (member.get("clinical") or {}).get("stages") or []]
            stages.sort(key=lambda r: (not r.get("life_threatening"), -int(r.get("stage") or 0)))
            clinical = ",".join(dict.fromkeys(f"{r.get('def_name')}:{r.get('stage')}{'!' if r.get('life_threatening') else ''}" for r in stages))[:120]
            affected = max((r.get("affected_allies") or 0 for r in members), default=0)
            effects[key] = {
                "benefit": f"{context.get('effect_label')}: {facts}. {context.get('effect_description')}",
                "risk": f"AoE allies {affected}; clinical {clinical}; group fire {any(r.get('fire') for r in members)}, max nearby enemies {max((r.get('hostiles_within_twenty') or 0 for r in members), default=0)}, max nearby allies {max((r.get('allies_within_five') or 0 for r in members), default=0)}. Check collateral effects.",
                "cost": f"Actual maximum cost / minimum charges {native_cost}; temperature {row.get('temperature')}, roof {row.get('roof')}.",
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

def targeting_evidence(context: dict, selected: dict) -> dict | None:
    """Bind consequences of this target; moving identified pawns stay identified."""
    rows = context.get("options") or []
    row = next((r for r in rows if (r.get("target_id") == selected["target_id"] if selected["target_id"]
                                  else not r.get("target_id") and r.get("x") == selected["x"] and r.get("z") == selected["z"])), None)
    if row is None:
        return None
    return {"session_id": context.get("session_id"), "map_id": context.get("map_id"),
            "effect_identity": context.get("effect_identity"), "source": context.get("source"),
            "effect_cost": context.get("effect_cost"), "caster_facts": context.get("caster_facts"),
            **{k: row.get(k) for k in ("target_id", "kind", "definition", "hostile", "downed", "clinical",
                                      "actual_cost", "roof", "fire", "allies_within_five", "affected_allies", "hostiles_within_twenty")}}


def targeting_changed(prior: dict | None, fresh: dict | None) -> bool:
    if prior is None or fresh is None:
        return True
    import colony_affordances
    def clinical_changed(old, new):
        if not isinstance(old, dict) or not isinstance(new, dict):
            return old != new
        if set(old) != set(new):
            return True
        return any(abs(old[k] - new[k]) > .020001 if k in {"health", "bleed_rate"}
                   and isinstance(old[k], (int, float)) and isinstance(new[k], (int, float))
                   else old[k] != new[k] for k in old)
    for key in prior:
        if key in {"clinical", "caster_facts"}:
            if clinical_changed(prior[key], fresh.get(key)):
                return True
        elif key == "actual_cost":
            old, new = prior[key], fresh.get(key)
            if isinstance(old, dict) and isinstance(new, dict):
                if old.get("charges") != new.get("charges") or colony_affordances.evidence_changed(old, new):
                    return True
            elif old != new:
                return True
        elif prior[key] != fresh.get(key):
            return True
    return False

def _target_retry_signature(context, selected=None):
    import colony_affordances
    rows = [{k: r.get(k) for k in ("key", "target_id", "kind", "definition", "hostile", "downed", "clinical", "actual_cost", "roof", "fire", "allies_within_five", "affected_allies", "hostiles_within_twenty")}
            for r in context.get("options") or [] if r.get("kind") != "cell" or selected and not selected.get("target_id") and r.get("x") == selected.get("x") and r.get("z") == selected.get("z")]
    return colony_affordances.state_fingerprint({"session": context.get("session_id"), "map": context.get("map_id"),
        "effect": context.get("effect_identity"), "cost": context.get("effect_cost"), "caster": context.get("caster_facts"), "rows": rows})


def _target_failed(map_state, context, selected):
    signature = _target_retry_signature(context, selected)
    prior = map_state.get("native_target_retry") or {}
    if not isinstance(prior, dict): prior = {}
    delay = min(5, max(1, int(prior.get("delay") or 0) * 2)) if prior.get("signature") == signature else 1
    map_state["native_target_retry"] = {"signature": signature, "selected": selected, "delay": delay, "until": time.time() + delay}

def run_pending(client: Any, agent: Any, snapshot: dict, map_state: dict, *, world_only=False) -> dict | None:
    windows = client.get("/api/v1/ui/windows") or []
    top = next((w for w in reversed(windows) if w.get("force_pause") or w.get("blocks_input")), None)
    targeting = client.get("/api/v1/affordances/targeting") if top is None and not world_only else {}
    if isinstance(targeting, dict) and targeting.get("active"):
        native_memory = transition_memory(map_state, 'native_transition_memory', snapshot)
        transition_key = 'target:' + str(targeting.get('session_id'))
        readiness = target_readiness(targeting)
        if transition_wait(native_memory, transition_key, readiness):
            return _transition_wait_record(bool(top))
        retry = map_state.get("native_target_retry") or {}
        now = time.time()
        if not isinstance(retry, dict) or not isinstance(retry.get("until"), (int, float)) or retry.get("until", 0) > now + 5:
            retry = {}; map_state.pop("native_target_retry", None)
        if targeting.get("options") and retry.get("signature") == _target_retry_signature(targeting, retry.get("selected")) and now < retry.get("until", 0):
            return {"mode": "native-target-wait", "quiet": True, "blocks_development": bool(top), "decision": {"choice": "wait_for_target_retry"},
                    "result": {"applied": False, "reason": "target_retry_cooling", "completion": "unverified"}}
        selected, raw = target_choice(agent, targeting, map_state.get("native_intent"))
        if not selected["cancel"]:
            fresh = client.get("/api/v1/affordances/targeting") or {}
            if not fresh.get("active") or targeting_changed(targeting_evidence(targeting, selected), targeting_evidence(fresh, selected)):
                transition_record(native_memory, transition_key, readiness, {'applied': False, 'reason': 'stale_readback'})
                _target_failed(map_state, fresh if fresh.get("active") else targeting, selected)
                return {"mode": "native-target", "blocks_development": bool(top), "decision": {"choice": "target", "selected": selected, "raw": raw},
                        "result": {"applied": False, "reason": "target_effect_or_consequences_changed", "completion": "unverified"}}
        try:
            result = client.post("/api/v1/affordances/targeting", query=selected)
        except Exception:
            transition_record(native_memory, transition_key, readiness, {'applied': False, 'reason': 'network_outcome_unknown'})
            if not selected["cancel"]: _target_failed(map_state, targeting, selected)
            raise
        if not selected["cancel"] and (not isinstance(result, dict) or result.get("applied") is not True):
            _target_failed(map_state, fresh, selected)
        else:
            map_state.pop("native_target_retry", None)
        transition_record(native_memory, transition_key, readiness, result)
        return {"mode": "native-target", "blocks_development": bool(top) or bool(isinstance(result, dict) and result.get('applied')), "decision": {"choice": "cancel" if selected["cancel"] else "target",
                "selected": selected, "raw": raw}, "result": result}
    map_state.pop("native_target_retry", None)
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
        native_context = snapshot['development'][name]
        if name == 'specialists':
            native_context = {key: value for key, value in native_context.items() if isinstance(value, dict) and value.get('configuring')}
        elif name == 'progression':
            native_context = {key: native_context.get(key) for key in ('world_targeting', 'odyssey', 'ending_selection', 'ending_continuation')}
        native_readiness = transition_signature(native_context)
        module.prepare(snapshot, map_state)
        action = getattr(module, "pending_action", lambda _: None)(snapshot["development"][name])
        if action is None:
            continue
        blocker = getattr(module, "pending_blocker", lambda _: None)(snapshot["development"][name])
        if blocker:
            key = name + ":" + str(action) + ":" + str(blocker)
            quiet = map_state.get("blocked_native_continuation") == key
            map_state["blocked_native_continuation"] = key
            return {"mode": "native-continuation-wait", "quiet": quiet, "blocks_development": bool(top),
                    "decision": {"choice": "wait_for_native_readiness", "action": action},
                    "result": {"applied": False, "blocked": True, "reason": str(blocker), "completion": "unverified"}}
        map_state.pop("blocked_native_continuation", None)
        native_memory = transition_memory(map_state, 'native_transition_memory', snapshot)
        transition_key = module.__name__ + ':' + str(top.get('window_id') if top else '')
        readiness = native_readiness
        if transition_wait(native_memory, transition_key, readiness):
            return _transition_wait_record(bool(top))
        selected, raw = module.choose(agent, {"pending_native_choice": True}, action, snapshot)
        result = colony_modules.execute(client, snapshot, map_state, action, selected)
        transition_record(native_memory, transition_key, readiness, result)
        return {"mode": "native-continuation", "blocks_development": bool(top) or bool(result.get('applied')), "decision": {"choice": action, "selected": selected, "raw": raw}, "result": result}
    if top and (not world_only or top.get("window_type") in ("Dialog_ChooseThingsForNewColony", "Dialog_ConfigureIdeo", "Screen_ArchonexusSettlementCinematics")):
        key = str(top.get("window_id")) + ":" + str(top.get("window_type"))
        quiet = map_state.get("blocked_native_window") == key
        map_state["blocked_native_window"] = key
        return {"mode": "native-window-wait", "quiet": quiet,
                "decision": {"choice": "wait_for_native_window", "window": top.get("window_type")},
                "result": {"applied": False, "reason": "pending_native_window", "completion": "unverified"}}
    map_state.pop("blocked_native_window", None)
    map_state.pop("blocked_native_continuation", None)
    return None



def _transition_wait_record(blocking):
    return {'mode': 'native-transition-wait', 'quiet': True, 'blocks_development': blocking,
            'decision': {'choice': 'wait_for_native_observation'},
            'result': {'applied': False, 'reason': 'native_transition_awaiting_observation', 'completion': 'unverified'}}
