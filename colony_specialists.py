"""Observed DLC hazards and native mech/containment choices, without instant effects."""
from __future__ import annotations
from typing import Any
import json
import time
from laya_decisions import ask_laya_choice
from colony_retry import failure_record, recent as retry_recent

DESCRIPTIONS = {
    "specialists_royal_assign": "Assign an existing native qualifying bedroom or throne to a noble or royal guest. Compare ownership, guest needs and room requirements; this changes ownership and cannot improve room quality or guarantee hospitality.",
    "specialists_policy": "Compare native desired psyfocus and meditation timetable, Gauranlen pruning/caste or entity capture/study/extraction policy against labor, containment and irreversible consequences.",
    "specialists_permit": "Choose an owned native royal permit option comparing free use, cooldown or honor payment and its impact on noble progression; explicitly select any subsequent native target or confirmation.",
    "specialists_genetics": "Design a native xenogerm from whole powered genepacks, compare genes, metabolism/food cost, complexity and archites, then request normal assembly or defer.",
    "specialists_mech_boss": "Compare an eligible native mechanitor boss summon job with preparation and defer; this deliberately attracts a hostile boss wave to unlock higher mech technology through real combat and research.",
    "specialists_ritual": "Choose a native Ideology or Anomaly ritual command, configure its participants and role change, compare actual blockers/quality/offerings, then explicitly request Begin or defer. Effects require ordinary ritual work.",
    "specialists_mech_mode": "Choose a controlled mech group's normal work, recharge or dormant self-charge policy. Compare energy and labor with charger power and wastepack pollution; all members are affected.",
    "specialists_suppress_entity": "Send an available enabled warden on a normal feasible entity suppression job. Lower activity can reduce escape risk but takes labor and can reduce study speed; unsafe containment is still unsafe.",
}
LABELS = {"specialists_mech_mode": "режим работы механической группы", "specialists_suppress_entity": "подавление активности сущности"}
LABELS["specialists_royal_assign"] = "назначить подходящую королевскую комнату"
LABELS["specialists_ritual"] = "участники и проведение ритуала"
LABELS["specialists_genetics"] = "гены и сборка ксеногерма"
LABELS["specialists_mech_boss"] = "вызов босса механоидов"
LABELS["specialists_permit"] = "использование королевского разрешения"
LABELS["specialists_policy"] = "политика медитации, дриад и изучения сущностей"
ACTIONS = set(DESCRIPTIONS)
DOMAINS = {"specialists_mech_mode": "work_orders", "specialists_suppress_entity": "care"}
DOMAINS["specialists_royal_assign"] = "care"
DOMAINS["specialists_ritual"] = "strategy"
DOMAINS["specialists_genetics"] = "strategy"
DOMAINS["specialists_mech_boss"] = "strategy"
DOMAINS["specialists_permit"] = "strategy"
DOMAINS["specialists_policy"] = "strategy"
NATIVE_SPECIALISTS = {"specialists_policy": ("policies", "/api/v1/specialists/policies"),"specialists_ritual": ("rituals", "/api/v1/specialists/rituals"),
                      "specialists_genetics": ("genetics", "/api/v1/specialists/genetics"),
                      "specialists_mech_boss": ("mech_bosses", "/api/v1/specialists/mech-bosses"),
                      "specialists_permit": ("permits", "/api/v1/specialists/permits")}
PENDING_WINDOWS = ("Dialog_BeginRitual", "Dialog_BeginPsychicRitual", "Dialog_BeginGravshipLaunch", "Dialog_CreateXenogerm", "Dialog_ChangeDryadCaste")


def pending_action(context):
    if (context.get("policies") or {}).get("configuring"):
        return "specialists_policy"
    if (context.get("rituals") or {}).get("configuring"):
        return "specialists_ritual"
    if (context.get("genetics") or {}).get("configuring"):
        return "specialists_genetics"
    return None

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
        for key, endpoint in NATIVE_SPECIALISTS.values():
            try:
                result[key] = client.get(endpoint, map_id=snapshot["map"]["id"])
            except Exception as exc:
                result[key] = {"available": False, "reason": str(exc)}
        return result
    except Exception as exc:
        return {"available": False, "reason": str(exc)}

QUERY_FIELDS = ("operation", "map_id", "thing_id", "label", "pawn_id", "role_id", "selected", "permit", "faction_id", "policy", "value", "session_id")
BODY_FIELDS = ("kind", "mechanitor_id", "group_index", "value", "platform_id", "worker_id", "pawn_id", "thing_id")


def _payload(row, action):
    fields = QUERY_FIELDS if action in NATIVE_SPECIALISTS else BODY_FIELDS
    return {k: row[k] for k in fields if k in row}


def _key(row, action):
    return json.dumps(_payload(row, action), sort_keys=True)


def _subject(row, action):
    family = row.get('operation') if action == 'specialists_policy' else row.get('kind') if action == 'specialists_royal_assign' else (action + ':' + str(row.get('permit'))) if action == 'specialists_permit' else action
    target = row.get('pawn_id') or row.get('thing_id') or row.get('platform_id') or row.get('mechanitor_id') or row.get('session_id') or 'native'
    return str(family) + ':' + str(target) + (':' + str(row['group_index']) if row.get('group_index') is not None else '')


def _fingerprint(value):
    return json.dumps(value, sort_keys=True, default=str)


def _readiness(row, action):
    native = row.get('context') or {}
    result = {'session_id': native.get('session_id'), 'map_id': native.get('map_id')}
    if row.get('operation') == 'begin':
        keys = ('configuration', 'quality', 'blockers', 'can_begin', 'complexity', 'metabolism', 'archites', 'max_complexity')
        result.update({k: native.get(k) for k in keys if k in native})
        result['selected_packs'] = [p for p in native.get('packs') or [] if p.get('selected')]
    if action == 'specialists_mech_mode':
        result['energy_bands'] = [int(float(m.get('energy') or 0) * 4) for m in native.get('mechs') or []]
        result['mode'] = native.get('mode')
    if action == 'specialists_suppress_entity':
        entity = native.get('entity') or {}
        result['activity_band'] = int(float(entity.get('activity') or 0) * 4)
        result['unsafe'] = float(entity.get('containment_strength') or 0) < float(entity.get('minimum_strength') or 0)
    if action in ('specialists_mech_boss', 'specialists_permit'):
        result.update({k: row[k] for k in ('hostile_pawns', 'mobile_defenders', 'favor', 'on_cooldown') if k in row})
    if action == 'specialists_policy':
        result.update({k: row[k] for k in ('pruning_hours', 'warning', 'desired', 'max_dryads') if k in row})
    return result


def _material(native):
    return _fingerprint({'material_state': native.get('material_state'), 'blockers': native.get('blockers'), 'can_begin': native.get('can_begin'),
                         'capacity': native.get('max_complexity'),
                         'packs': [(p.get('thing_id'), p.get('powered'), p.get('genes')) for p in native.get('packs') or []]})


def pending_blocker(context):
    action = pending_action(context)
    if action and not (context.get(NATIVE_SPECIALISTS[action][0]) or {}).get('session_id'):
        return 'Native dialog identity unavailable; continuation requires a fresh window session.'
    if action and not (context.get('options') or {}).get(action):
        return 'No eligible native continuation; wait for readiness or inspect the dialog.'
    return None


def _native_effect(row, action, snapshot):
    base = assess(action, snapshot)
    facts = '; '.join(f'{k}={row[k]}' for k in ('favor', 'on_cooldown', 'hostile_pawns', 'mobile_defenders', 'strength', 'minimum', 'current', 'desired', 'pruning_hours', 'pawn_health') if k in row)
    explanation = '; '.join(str(row[k]) for k in ('description', 'genes', 'disabled_work', 'consequence', 'warning') if k in row)
    return {**base, 'benefit': facts + '; ' + str(row.get('label') or row.get('operation')) + '; ' + explanation,
            'cost': facts + '; ' + base['cost'] + '; ' + explanation,
            'risk': facts + '; current job=' + str(row.get('pawn_job') or row.get('current_job')) + '; ' + base['risk'] + '; ' + explanation}


def prepare(snapshot: dict, map_state: dict) -> list[str]:
    context = snapshot.setdefault("development", {}).setdefault("specialists", {})
    options = {a: {} for a in ACTIONS}
    ritual = context.get("rituals") or {}
    rows = ritual.get("choices") or [] if ritual.get("configuring") else [{**r, "operation": "open"} for r in ritual.get("commands") or []]
    for index, row in enumerate(rows):
        options["specialists_ritual"][str(index)] = {"kind": "ritual", **row, "context": ritual}
    if ritual.get("configuring") and ritual.get("can_begin"):
        options["specialists_ritual"]["begin"] = {"kind": "ritual", "operation": "begin", "label": f"Begin {ritual.get('label')}", "context": ritual}
    if ritual.get("configuring"):
        options["specialists_ritual"]["cancel"] = {"kind": "ritual", "operation": "cancel", "label": "Cancel ritual preparations", "context": ritual}
    genetics = context.get("genetics") or {}
    if genetics.get("available"):
        if genetics.get("configuring"):
            options["specialists_genetics"]["cancel"] = {"kind": "genetics", "operation": "cancel", "label": "Cancel gene design", "context": genetics}
            for row in genetics.get("packs") or []:
                if row.get("powered") or row.get("selected"):
                    options["specialists_genetics"][str(row["thing_id"])] = {**row, "kind": "genetics", "operation": "select", "selected": not row.get("selected"),
                        "label": ("Remove " if row.get("selected") else "Add ") + row["label"], "context": genetics}
            if any(row.get("selected") for row in genetics.get("packs") or []):
                options["specialists_genetics"]["name"] = {"kind": "genetics", "operation": "name", "label": "Choose a native generated xenogerm name", "context": genetics}
            if genetics.get("can_begin"):
                options["specialists_genetics"]["begin"] = {"kind": "genetics", "operation": "begin", "label": "Begin xenogerm assembly", "context": genetics}
        else:
            for row in genetics.get("assemblers") or []:
                if row.get("can_open"):
                    options["specialists_genetics"][str(row["thing_id"])] = {**row, "kind": "genetics", "operation": "open", "label": "Design xenogerm at assembler", "context": genetics}
    for index, row in enumerate((context.get("mech_bosses") or {}).get("options") or []):
        options["specialists_mech_boss"][str(index)] = {**row, "kind": "mech_boss", "context": context.get("mech_bosses")}
    for index, row in enumerate((context.get("permits") or {}).get("options") or []):
        options["specialists_permit"][str(index)] = {**row, "kind": "permit", "context": context.get("permits")}
    for index, row in enumerate((context.get("policies") or {}).get("choices") or []):
        options["specialists_policy"][str(index)] = {**row, "kind": "policy", "context": context.get("policies")}
    for row in context.get("royal_assignments") or []:
        if row.get("kind") in ("royal_bed", "royal_throne") and row.get("pawn_id") is not None and row.get("thing_id") is not None:
            options["specialists_royal_assign"][f"{row['kind']}:{row['pawn_id']}:{row['thing_id']}"] = {
                "kind": row["kind"], "pawn_id": row["pawn_id"], "thing_id": row["thing_id"], "context": row}
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
    memory = map_state.get('specialists_memory')
    if not isinstance(memory, dict):
        memory = {}
        map_state['specialists_memory'] = memory
    now = time.time()
    for bucket in ('issued', 'deferred', 'failed'):
        records = memory.get(bucket) or {}
        if not isinstance(records, dict):
            memory.pop(bucket, None); continue
        for key, record in list(records.items()):
            paused = isinstance(record, dict) and bucket == 'failed' and record.get('paused')
            timestamp = record.get('time' if paused else 'tick') if isinstance(record, dict) else None
            if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
                del records[key]; continue
            active = (0 <= now - timestamp < 2) if paused else retry_recent(record, tick, 60 if bucket == 'failed' else 15000, now=now)
            if not active:
                del records[key]
        if not records:
            memory.pop(bucket, None)
    sessions = memory.get('sessions')
    if not isinstance(sessions, dict):
        sessions = {}; memory['sessions'] = sessions
    active_sessions = set()
    for action, (name, _) in NATIVE_SPECIALISTS.items():
        native = context.get(name) or {}
        sid = native.get('session_id') if native.get('configuring') else None
        if not sid:
            continue
        active_sessions.add(sid)
        session = sessions.get(sid)
        if not isinstance(session, dict):
            session = {'edges': [], 'named': []}; sessions[sid] = session
        if not isinstance(session.get('edges'), list):
            session['edges'] = []
        if not isinstance(session.get('named'), list):
            session['named'] = []
        session['edges'] = [edge for edge in session['edges'] if isinstance(edge, list) and len(edge) == 2 and all(isinstance(k, str) for k in edge)][-32:]
        session['named'] = [name for name in session['named'] if isinstance(name, str)][-16:]
        config = _fingerprint(native.get('configuration'))
        material = _material(native)
        pending = session.pop('pending', None)
        if not isinstance(pending, dict) or not isinstance(pending.get('from'), str) or not isinstance(pending.get('option'), str):
            pending = None
        if pending and config != pending['from']:
            session['edges'] = (session['edges'] + [[pending['from'], pending['option']]])[-32:]
        elif session.get('material') not in (None, material):
            session['edges'] = []
        elif session.get('configuration') not in (None, config) and not pending:
            session['edges'] = []  # External actual configuration change.
        session.update(configuration=config, material=material)
        native['recent_configuration_effects'] = session.get('last_effect')
        for key, row in list(options[action].items()):
            row['session_id'] = sid
            row['map_id'] = native.get('map_id', snapshot['map']['id'])
            if row.get('operation') in ('begin', 'cancel'):
                continue
            composition = _fingerprint((native.get('configuration') or {}).get('selected_packs'))
            if [config, _key(row, action)] in session['edges'] or (row.get('operation') == 'name' and composition in session['named']):
                del options[action][key]
                native['repeat_blocker'] = 'Repeated configuration transition suppressed; Begin, Cancel and new configurations remain explicit.'
    for sid in list(sessions):
        if sid not in active_sessions:
            del sessions[sid]
    if not sessions:
        memory.pop('sessions', None)
    for action, rows in options.items():
        for key, row in list(rows.items()):
            native = row.get('context') or {}
            if not native.get('configuring') and row.get('map_id') not in (None, snapshot['map']['id']):
                del rows[key]; continue
            if row.get('operation') == 'cancel':
                continue
            failed = (memory.get('failed') or {}).get(_key(row, action))
            subject = _subject(row, action)
            deferred = (memory.get('deferred') or {}).get(subject)
            if (failed and failed.get('state') in (None, _fingerprint(_readiness(row, action)))) or (not native.get('configuring') and (((memory.get('issued') or {}).get(subject) and (memory['issued'][subject].get('state') in (None, _fingerprint(_readiness(row, action))))) or (deferred and deferred.get('state') == _fingerprint(_readiness(row, action))))):
                del rows[key]
    if not memory:
        map_state.pop('specialists_memory', None)
    import colony_sessions
    replay = colony_sessions.transition_memory(map_state, 'specialist_transitions', snapshot)
    for action, rows in options.items():
        for key, row in list(rows.items()):
            readiness = colony_sessions.transition_signature({'payload': _payload(row, action), 'readiness': _readiness(row, action), 'material': _material(row.get('context') or {}), 'configuration': (row.get('context') or {}).get('configuration')})
            if colony_sessions.transition_wait(replay, _key(row, action), readiness):
                del rows[key]
    context['eligible_actions'] = [a for a, rows in options.items() if rows]
    return context['eligible_actions']

def assess(action: str, snapshot: dict) -> dict:
    if action == "specialists_royal_assign":
        return {"benefit": "Assign current qualifying native royal room ownership.", "cost": "Existing bedroom/throne becomes assigned to this pawn.",
                "risk": "Room and availability may change; hospitality mood, food and defense still matter.", "inaction": "Noble or guest room requirements may remain unmet.",
                "uncertainty": "Assignment does not construct furniture, increase impressiveness or complete Royal Ascent."}
    if action == "specialists_policy":
        return {"benefit": "Enable ordinary focus recovery, dryad specialization or anomaly study through native policy and jobs.", "cost": "Meditation/pruning/containment labor, time away from work and actual extraction resources.", "risk": "Higher pruning targets consume worker hours; caste changes require cocoon downtime; entity capture/transfer exposes handlers and extraction can damage entities. Containment strength remains critical.", "inaction": "Preserve current policies and labor; desired focus, dryad products or discoveries remain delayed.", "uncertainty": "Policy does not grant focus, connection strength, dryads, research or bioferrite instantly."}
    if action == "specialists_permit":
        return {"benefit": "Native military aid, workers, resources, shuttle or orbital support from an owned royal permit.", "cost": "Native cooldown or honor payment shown by the option; honor spent can delay noble ranks and Royal Ascent.",
                "risk": "Aid does not guarantee safety; orbital strikes can harm allies and resources. Target choices remain explicit.", "inaction": "Preserve free use/honor for future need while current shortage or threat persists.", "uncertainty": "Permit eligibility and target validation are engine checks; requesting aid does not prove its outcome."}
    if action == "specialists_genetics":
        return {"benefit": "Build a model-selected xenogerm through normal powered assembler work.", "cost": "Archite capsules when required, work, power and gene infrastructure; implantation separately costs medicine and recovery.", "risk": "Whole packs may include unwanted or conflicting genes; poor metabolism raises food demand. Replacement may cancel unfinished assembly.", "inaction": "Preserve current genes and production; desired biological capabilities remain unavailable.", "uncertainty": "Conflicts and prerequisites follow native rules; beginning assembly never grants a finished xenogerm or implanted genes."}
    if action == "specialists_mech_boss":
        return {"benefit": "Boss loot can unlock stronger mech technology after a real battle.", "cost": "Defense, healing, summon labor, subsequent research and production.", "risk": "Deliberately attracts a lethal hostile wave; stronger mechs increase energy and waste obligations.", "inaction": "Preserve readiness and prepare defenses while higher tech remains locked.", "uncertainty": "An eligible summon is not evidence that this colony can defeat the boss."}
    if action == "specialists_ritual":
        return {"benefit": "Ordinary ideology ceremonies, role changes, celebrations or researched psychic ritual effects.", "cost": "Participant labor, offerings, duration and repeat-quality penalties.",
                "risk": "Doctors and defenders leave work; some targets undergo irreversible effects. Native quality is a range, not guaranteed success.", "inaction": "Preserve labor and resources; missed obligations or desired role/psychic benefits remain.", "uncertainty": "Native blockers, participant eligibility and quality change; Begin is never completed outcome."}
    if action == "specialists_mech_mode":
        return {"benefit": "Work provides type-supported labor; recharge restores energy; dormant self-charge needs no charger.", "cost": "Recharge occupies powered chargers and creates wastepacks; dormancy sacrifices work and defense.", "risk": "The policy affects every group member. Chargers or safe waste storage may be unavailable.", "inaction": "Current mode continues; energy or lost labor may remain a problem.", "uncertainty": "Mode does not guarantee a free compatible charger, job, or safe power supply."}
    return {"benefit": "Normal suppression reduces entity activity when the job completes.", "cost": "Warden labor; reduced activity may reduce study knowledge rate.", "risk": "Suppression does not repair inadequate containment or guarantee no escape.", "inaction": "Activity and containment pressure can persist while wardens wait.", "uncertainty": "Reservations, path, worker status and entity state can change before completion."}

def choose(agent: Any, state: dict, action: str, snapshot: dict) -> tuple[dict, dict]:
    context = snapshot.get("development", {}).get("specialists", {})
    plans = context.get("options", {}).get(action) or {}
    effects = assess(action, snapshot)
    if action == "specialists_royal_assign":
        if not plans:
            return {"defer": True}, {"reason": "no_live_royal_assignment"}
        choices = {key: row["context"].get("label") or key for key, row in plans.items()}
        choices["defer"] = "Preserve current ownership; requirements may remain unmet."
        option_effects = {key: {**effects, "benefit": (row["context"].get("label") or key) + "; " + str(row["context"].get("description") or "")}
                          for key, row in plans.items()}
        option_effects["defer"] = effects
        key, raw = ask_laya_choice(agent, {"option_effects": option_effects}, action, DESCRIPTIONS[action], choices, detailed=True)
        return ({"defer": True} if key == "defer" else {k: v for k, v in plans[key].items() if k != "context"}), raw
    if action in NATIVE_SPECIALISTS:
        def target(row):
            return str(row.get("pawn_id") or row.get("thing_id") or row.get("operation") or "ritual")
        targets = {target(row): row.get("pawn") or row.get("label") or target(row) for row in plans.values()}
        pending = pending_action(context) == action
        if not pending:
            targets["defer"] = "Prepare and preserve current work."
        focused, first = ask_laya_choice(agent, {"colony": state, "option_effects": {key: next((_native_effect(row, action, snapshot) for row in plans.values() if target(row) == key), effects) for key in targets}}, action + "_target",
                                         "Choose one native specialist target or defer.", targets, detailed=True)
        if focused == "defer":
            return {"defer": True}, first
        plans = {key: row for key, row in plans.items() if target(row) == focused}
        choices = {key: row.get("label") or key for key, row in plans.items()}
        if not pending:
            choices["defer"] = "Keep preparations and current participants; defer this decision."
        native = context.get(NATIVE_SPECIALISTS[action][0]) or {}
        facts = {key: native.get(key) for key in ("label", "description", "quality", "blockers", "complexity", "metabolism", "archites", "max_complexity", "warning", "recent_configuration_effects", "repeat_blocker") if key in native}
        selected, raw = ask_laya_choice(agent, {"colony": state, "decision_facts": facts,
                                       "option_effects": {key: _native_effect(row, action, snapshot) for key, row in plans.items()}}, action,
                                       DESCRIPTIONS[action], choices, detailed=True)
        raw["specialist_target_choice"] = first
        return ({"defer": True} if selected == "defer" else plans[selected]), raw
    targets = {}
    for row in plans.values():
        if row["kind"] == "mech_mode":
            g = row["context"]
            target = f"{row['mechanitor_id']}:{row['group_index']}"
            levels = [m.get("energy") for m in g.get("mechs") or [] if isinstance(m.get("energy"), (int, float))]
            targets[target] = f"Energy {min(levels, default=None)}–{max(levels, default=None)}; {len(g.get('mechs') or [])} mechs; {g.get('mechanitor_name')} group {g.get('group_index')}; mode {g.get('mode')}"
        else:
            e = row["context"]["entity"]
            targets[str(row["platform_id"])] = f"Containment {e.get('containment_strength')} required {e.get('minimum_strength')}; {e.get('name')} activity {e.get('activity')}; suppression costs study speed"
    if not targets:
        return {"defer": True}, {"reason": "no_live_specialist_options"}
    targets["defer"] = "Preserve current policy and labor; energy or activity problems may remain."
    target, first = ask_laya_choice(agent, {"option_effects": {key: {**effects, "benefit": label + "; " + effects["benefit"]} for key, label in targets.items()}, "colony": state}, action + "_target", "Choose a live target, or defer.", targets, detailed=True)
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
    option_effects = {}
    for key, description in descriptions.items():
        row = plans.get(key)
        if row and row["kind"] == "mech_mode":
            group = row["context"]
            levels = [m.get("energy") for m in group.get("mechs") or [] if isinstance(m.get("energy"), (int, float))]
            salient = f"Energy {min(levels, default=None)}–{max(levels, default=None)}, {len(group.get('mechs') or [])} mechs; {row['value']}."
            cost = f"Mode {group.get('mode')} → {row['value']}; chargers {len(context.get('chargers') or [])}; unfrozen waste {sum(int(w.get('count') or 0) for w in context.get('wastepacks') or [] if not w.get('frozen'))}. "
        elif row:
            entity, worker = row["context"]["entity"], row["context"]["worker"]
            salient = f"Activity {entity.get('activity')}, strength {entity.get('containment_strength')} vs required {entity.get('minimum_strength')}; suppression rate {worker.get('suppression_rate')}."
            cost = f"Worker {worker.get('name')} Social {worker.get('social')}; study factor {entity.get('study_factor')}. "
        else:
            salient, cost = description, "Preserve current worker jobs. "
        option_effects[key] = {**effects, "benefit": salient + " " + effects["benefit"],
                               "cost": cost + effects["cost"], "risk": salient + " " + effects["risk"]}
    visible["option_effects"] = option_effects
    key, raw = ask_laya_choice(agent, visible, action, DESCRIPTIONS[action], descriptions, detailed=True)
    raw["specialist_target_choice"] = first
    return ({"defer": True} if key == "defer" else {k: v for k, v in plans[key].items() if k != "context"}), raw

def _execute(client: Any, snapshot: dict, map_state: dict, action: str, selected: dict) -> dict:
    tick = int(snapshot.get('game', {}).get('tick') or 0)
    memory = map_state.setdefault('specialists_memory', {})
    if selected.get('defer'):
        for row in (snapshot.get('development', {}).get('specialists', {}).get('options', {}).get(action) or {}).values():
            memory.setdefault('deferred', {})[_subject(row, action)] = {'tick': tick, 'state': _fingerprint(_readiness(row, action))}
        return {'applied': False, 'reason': 'laya_deferred'}
    payload = _payload(selected, action)
    def failed():
        memory.setdefault('failed', {})[_key(selected, action)] = {**failure_record(tick), 'time': time.time(), 'paused': bool((selected.get('context') or {}).get('configuring')), 'state': _fingerprint(_readiness(selected, action))}
    try:
        live = collect(client, snapshot)
        prepare({'map': snapshot['map'], 'game': snapshot.get('game') or {}, 'development': {'specialists': live}}, {})
        rows = live.get('options', {}).get(action) or {}
        row = next((row for row in rows.values() if _payload(row, action) == payload), None)
        if row is None or (action in NATIVE_SPECIALISTS and _readiness(row, action) != _readiness(selected, action)):
            failed()
            return {'applied': False, 'reason': 'selected_native_identity_or_relevant_readiness_changed'}
        if action in NATIVE_SPECIALISTS:
            result = client.post(NATIVE_SPECIALISTS[action][1], query={**payload, 'confirmed': True})
            applied = result in ('ritual_native_command_requested', 'ritual_begin_requested', 'ritual_assignment_updated', 'ritual_cancelled', 'gene_design_opened', 'gene_selection_updated', 'gene_name_chosen', 'gene_design_cancelled', 'gene_assembly_requested', 'specialist_policy_requested', 'boss_summon_job_requested', 'permit_native_action_requested')
            outcome = {'applied': applied, 'reason': str(result), 'completed': False}
        else:
            result = client.post('/api/v1/specialists/order', body={'map_id': snapshot['map']['id'], **payload})
            outcome = result if isinstance(result, dict) else {'applied': False, 'reason': 'invalid_response'}
            applied = outcome.get('applied') is True
    except Exception:
        failed(); raise
    if applied:
        native = row.get('context') or {}
        sid = native.get('session_id')
        if sid and native.get('configuring'):
            session = memory.setdefault('sessions', {}).setdefault(sid, {'edges': [], 'named': []})
            session['pending'] = {'from': _fingerprint(native.get('configuration')), 'option': _key(row, action)}
            session['last_effect'] = {'operation': payload, 'result': outcome['reason']}
            if row.get('operation') == 'name':
                session['named'] = (session['named'] + [_fingerprint((native.get('configuration') or {}).get('selected_packs'))])[-16:]
        else:
            memory.setdefault('issued', {})[_subject(row, action)] = {'tick': tick, 'state': _fingerprint(_readiness(row, action))}
    else:
        failed()
    return outcome


def execute(client, snapshot, map_state, action, selected):
    import colony_sessions
    if selected.get('defer'): return _execute(client, snapshot, map_state, action, selected)
    if not selected.get('context'):
        payload = _payload(selected, action)
        rows = snapshot.get('development', {}).get('specialists', {}).get('options', {}).get(action) or {}
        selected = next((row for row in rows.values() if _payload(row, action) == payload), selected)
    key = _key(selected, action)
    readiness = colony_sessions.transition_signature({'payload': _payload(selected, action), 'readiness': _readiness(selected, action), 'material': _material(selected.get('context') or {}), 'configuration': (selected.get('context') or {}).get('configuration')})
    memory = colony_sessions.transition_memory(map_state, 'specialist_transitions', snapshot)
    if colony_sessions.transition_wait(memory, key, readiness):
        return {'applied': False, 'reason': 'native_transition_awaiting_observation'}
    try:
        result = _execute(client, snapshot, map_state, action, selected)
    except Exception:
        colony_sessions.transition_record(memory, key, readiness, {'applied': False, 'reason': 'network_outcome_unknown'})
        raise
    colony_sessions.transition_record(memory, key, readiness, result,
        recovery_seconds=60 if (selected.get('context') or {}).get('configuring') else 30)
    return result
