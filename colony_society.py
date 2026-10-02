"""Live human needs and reversible care, prisoner and learning policies."""
from __future__ import annotations
from typing import Any
from laya_decisions import ask_laya_choice

DESCRIPTIONS = {
    "society_medical_care": "Choose a patient's permitted medicine ceiling. Treatment still requires a doctor, access and supplies; compare illness and immunity with medicine scarcity.",
    "society_prisoner_policy": "Choose whether to recruit, reduce resistance or maintain a held prisoner. Recruitment takes warden time and adds food and shelter needs; conversion is a separate choice.",
    "society_free_time": "Give a child learning time or an adult recreation time by changing one work hour. Ordinary autonomous activities need accessible facilities and awake companions; lost work may matter.",
    "society_baby_safe": "Carry an exposed baby to a native safe destination. Compare caregiver exposure and lost labor with leaving the baby in danger.",
    "society_baby_feed": "Choose normal breastfeeding, bottle feeding or delivery to a lactating mother. Use native hunger, lactation, childcare, food and reservation eligibility.",
    "society_baby_play": "Have an available adult play with an awake baby through normal childcare. Play and caregiver recreation grow only as the job runs.",
    "society_teach": "Send a feasible teacher to a child waiting at a school desk. Lessons need native teacher availability, desk reservations and compatible skills.",
    "society_hemogen_feed": "Administer or deliver an available hemogen pack through the native doctor/warden workgiver. Compare hemogen need with scarce transfusion stock.",
    "society_deathrest": "Start normal deathrest in a reachable suitable roofed bed. The pawn loses several days of work and defense; premature interruption can lose benefits.",
    "society_deathrest_wake": "Choose whether to wake automatically after completing deathrest. Keeping a pawn asleep preserves rest but delays work and defense.",
    "society_drug_policy": "Assign an existing drug policy to this adult. Compare every permission, scheduled dose, addiction/dependency, stock and beliefs.",
    "society_drug_entry": "Change one drug permission or schedule in a personal copy of this pawn's policy. Withdrawal, overdose, dependency, medical prevention and drug-related traits matter.",
    "society_growth_prepare": "Prepare a pending native growth moment's offered options once, as opening the game letter does. This does not select awards or reroll an existing offer.",
    "society_growth": "Select only the exact trait and passion awards offered by a pending growth letter. Consider permanent drawbacks, existing skills, genes and future work; defer is available.",
    "society_medical_recipe": "Queue a loaded native therapeutic medical recipe with qualified doctor, ingredients, correct part and bed. Compare cure or transfusion against normal care, anesthesia, failure and irreversible amputation or donor blood loss.",
}
LABELS = {"society_medical_care": "допуск лекарств пациенту", "society_prisoner_policy": "план общения с пленником", "society_free_time": "время учёбы и отдыха"}
ACTIONS = set(DESCRIPTIONS)
DOMAINS = {"society_medical_care": "care", "society_prisoner_policy": "economy_diplomacy", "society_free_time": "work_orders"}
DOMAINS.update({a: 'care' for a in ACTIONS if a not in DOMAINS})
LABELS.update({a: a.removeprefix('society_') for a in ACTIONS if a not in LABELS})
CARE_JOBS = {"BottleFeedBaby","BreastfeedCarryToMom","BringBabyToSafetyUnforced","CarryToMomAfterBirth","BabySuckle","BabyPlay","PlayStatic","PlayWalking","PlayToys","Lessonreceiving","TendPatient", "Rescue", "FeedPatient", "DoBill", "Deathrest", "Breastfeed", "BottlefeedBaby", "BringBabyToSafety", "Lessongiving", "PrisonerInterrogateIdentity"}
NATIVE_FIELDS = ('kind', 'pawn_id', 'worker_id', 'target_id', 'letter_id', 'value')

def summary(snapshot: dict) -> dict:
    context = snapshot.get('development', {}).get('society', {})
    return {'dependent_children': {'count': sum((p.get('development') or {}).get('stage') == 'Baby' for p in context.get('people') or [])},
            'pending_growth_moments': {'count': len(context.get('growth_moments') or [])},
            'society_native_options': {'count': len(context.get('native_options') or [])}}

def collect(client: Any, snapshot: dict) -> dict:
    try:
        context = client.get("/api/v1/society/context", map_id=snapshot["map"]["id"])
        return context if isinstance(context, dict) else {"available": False, "reason": "invalid_context"}
    except Exception as exc:
        return {"available": False, "reason": str(exc)}

def prepare(snapshot: dict, map_state: dict) -> list[str]:
    context = snapshot.setdefault("development", {}).setdefault("society", {})
    plans = {action: {} for action in ACTIONS}
    for p in context.get("people") or []:
        pid = p.get("pawn_id")
        if pid is None or p.get("dead"):
            continue
        if p.get("medical_attention") and p.get("care_options"):
            for care in p["care_options"]:
                if care != p.get("medical_care"):
                    plans["society_medical_care"][f"{pid}:{care}"] = {"pawn_id": pid, "kind": "medical", "value": care, "person": p}
        for mode in p.get("prisoner_options") or []:
            if mode != p.get("prisoner_mode"):
                plans["society_prisoner_policy"][f"{pid}:{mode}"] = {"pawn_id": pid, "kind": "prisoner", "value": mode, "person": p}
        needs = {n.get("def_name"): n.get("level") for n in p.get("needs") or []}
        learning = needs.get("Learning")
        joy = needs.get("Joy")
        if not p.get("downed") and not p.get("drafted") and not p.get("mental_state") and p.get("current_job") not in CARE_JOBS and ((isinstance(learning, (int, float)) and learning < .9) or (isinstance(joy, (int, float)) and joy < .5)):
            for hour, assignment in enumerate(p.get("timetable") or []):
                if assignment == "Work":
                    plans["society_free_time"][f"{pid}:{hour}"] = {"pawn_id": pid, "kind": "timetable", "hour": hour, "value": "Joy", "person": p}
    context["options"] = plans
    people = {p['pawn_id']: p for p in context.get('people') or [] if p.get('pawn_id') is not None}
    for option in context.get('native_options') or []:
        action = 'society_' + str(option.get('kind'))
        if action in ACTIONS:
            key = ':'.join(str(option.get(k, '')) for k in ('pawn_id', 'worker_id', 'target_id', 'letter_id', 'value'))
            plans[action][key] = {**option, 'native': True, 'person': people.get(option.get('pawn_id'), {})}
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    eligible = [a for a, rows in plans.items() if rows and (tick < int((map_state.get("issued") or {}).get("society:" + a, -1000000)) or tick - int((map_state.get("issued") or {}).get("society:" + a, -1000000)) >= (600 if a in {'society_baby_feed', 'society_baby_safe', 'society_hemogen_feed'} else 2500 if a in {'society_teach', 'society_baby_play', 'society_growth_prepare', 'society_growth'} else 15000))]
    context['eligible_actions'] = eligible
    return eligible

def assess(action: str, snapshot: dict) -> dict:
    facts = {
        "society_medical_care": ("Permits the selected medicine quality for normal treatment.", "Medicine consumption and doctor time.", "A ceiling does not guarantee medicine or timely treatment; lowering it can worsen care.", "Current restrictions can delay appropriate treatment."),
        "society_prisoner_policy": ("Normal wardens can pursue the selected social goal.", "Warden time, prisoner food and possible new colonist upkeep.", "Recruitment can fail; beliefs and prison breaks still matter.", "A maintained prisoner makes no recruitment progress."),
        "society_free_time": ("Allows ordinary recreation or child learning activities in one hour.", "One hour previously available for work.", "Facilities, safe space and available adults may still be missing.", "Low learning limits growth choices; low recreation contributes to low mood."),
    }
    if action not in facts:
        return dict(benefit=DESCRIPTIONS[action], cost='Worker time, supplies or forgone alternative.', risk='Native eligibility may change; completed effects are not guaranteed.', inaction='Current jobs, policy and unmet needs continue.', uncertainty='Observe actual completion and changing needs.')
    b, c, r, i = facts[action]
    return dict(benefit=b, cost=c, risk=r, inaction=i, uncertainty="Live needs and policy are observed; future jobs and outcomes are not guaranteed.")

def _payload(row: dict) -> dict:
    fields = NATIVE_FIELDS if row.get('native') else ('pawn_id', 'kind', 'value', 'hour')
    return {k: row[k] for k in fields if k in row}


def _effects(row: dict, action: str, context: dict) -> dict:
    if row.get('native'):
        return {k: str((row.get('effects') or {}).get(k) or 'Unknown') for k in ('benefit', 'risk', 'cost', 'inaction', 'uncertainty')}
    p = row.get('person') or {}
    conditions = sorted((h for h in p.get('conditions') or [] if h.get('visible', True)), key=lambda h: (bool(h.get('life_threatening')), h.get('immunity') is not None and h['immunity'] < 1), reverse=True)
    h = conditions[0] if conditions else {}
    needs = {n.get('def_name'): n.get('level') for n in p.get('needs') or []}
    result = assess(action, {})
    if row['kind'] == 'medical':
        result['benefit'] = f"{h.get('def_name')} s={h.get('severity')} i={h.get('immunity')}; {row['value']}"
        result['risk'] = f"beliefs={','.join(p.get('beliefs') or [])}; ceiling not timely treatment"
        result['cost'] = f"stock={context.get('medicine')}; medicine and doctor time"
    elif row['kind'] == 'prisoner':
        result['benefit'] = f"{row['value']}; resistance={p.get('resistance')} certainty={p.get('certainty')}"
        result['risk'] = f"ideology={p.get('ideology')}; replaces {p.get('prisoner_mode')}; prison breaks"
    else:
        result['benefit'] = f"Learning={needs.get('Learning')} Joy={needs.get('Joy')}; hour{row.get('hour')} becomes Joy"
        result['cost'] = f"lose work hour{row.get('hour')}; adults/desks/safe area still required"
        result['risk'] = f"desires={p.get('learning_desires')}; facilities may be missing"
    return result


def _growth_choice(agent: Any, row: dict, context: dict, first: dict) -> tuple[dict, dict]:
    moment = next((m for m in context.get('growth_moments') or [] if m.get('letter_id') == row['letter_id'] and m.get('pawn_id') == row['pawn_id']), None)
    if not moment or not moment.get('ready'):
        return {'defer': True}, {'reason': 'growth_offer_not_ready'}
    audit = {'society_person_choice': first}
    defer = {'benefit': 'Wait before permanent awards', 'risk': 'Native timeout may resolve letter', 'cost': 'Forgoes immediate new passion/trait', 'inaction': 'Current child skills remain', 'uncertainty': 'Future roles may become clearer'}
    traits = {str(t['index']): t for t in moment.get('traits') or []}
    if moment.get('no_trait'):
        traits['-2'] = {'label': 'No trait', 'description': 'Forgo offered traits and their drawbacks'}
    trait_index = -1
    if traits:
        choices = {k: t['label'] for k, t in traits.items()}
        effects = {k: {'benefit': t['label'], 'risk': t.get('description', 'Permanent trait'), 'cost': 'Forgoes other offered traits', 'inaction': 'Letter awaits a choice', 'uncertainty': 'Long-term role and trait drawbacks matter'} for k, t in traits.items()}
        choices['defer'], effects['defer'] = 'Wait before selecting awards', defer
        key, raw = ask_laya_choice(agent, {'decision_facts': {'child': moment.get('name'), 'growth_tier': moment.get('growth_tier')}, 'option_effects': effects}, 'society_growth_trait', 'Choose an exact offered trait, an offered no-trait option, or defer.', choices, detailed=True)
        audit['trait_choice'] = raw
        if key == 'defer':
            return {'defer': True}, audit
        trait_index = int(key)
    chosen = []
    passions = {p['def_name']: p for p in moment.get('passions') or []}
    for ordinal in range(int(moment.get('passion_gains') or 0)):
        available = {k: p for k, p in passions.items() if k not in chosen}
        if not available:
            return {'defer': True}, {'reason': 'growth_offer_has_insufficient_passions'}
        effects = {k: {'benefit': f"{k} level={p.get('level')} passion={p.get('current_passion')} +one tier", 'risk': 'Gene effects can modify passion benefit', 'cost': 'Forgoes other offered skills', 'inaction': 'No earned award selected yet', 'uncertainty': p.get('description', 'Future role and work matter')} for k, p in available.items()}
        choices = {k: p.get('label', k) for k, p in available.items()}
        choices['defer'], effects['defer'] = 'Wait before selecting awards', defer
        key, raw = ask_laya_choice(agent, {'decision_facts': {'child': moment.get('name'), 'selected_trait': trait_index, 'already_selected': chosen}, 'option_effects': effects}, 'society_growth_passion_' + str(ordinal), 'Choose one exact offered passion award or defer. Previously chosen skills cannot be repeated.', choices, detailed=True)
        audit['passion_' + str(ordinal)] = raw
        if key == 'defer':
            return {'defer': True}, audit
        chosen.append(key)
    return {**_payload(row), 'trait_index': trait_index, 'skill_defs': chosen}, audit


def choose(agent: Any, state: dict, action: str, snapshot: dict) -> tuple[dict, dict]:
    context = snapshot.get('development', {}).get('society', {})
    plans = context.get('options', {}).get(action) or {}
    if not plans:
        return {'defer': True}, {'reason': 'no_live_society_options'}
    defer = {'benefit': 'Preserve current jobs/resources/policy', 'risk': 'Unmet needs or illness may persist', 'cost': 'No new supplies/labor', 'inaction': 'Autonomous work continues', 'uncertainty': 'Future outcomes are unknown'}
    persons, person_effects = {}, {}
    for row in plans.values():
        pid = str(row['pawn_id'])
        persons.setdefault(pid, (row.get('person') or {}).get('name') or row.get('label') or pid)
        person_effects.setdefault(pid, _effects(row, action, context))
    persons['defer'], person_effects['defer'] = 'Keep current jobs and policy', defer
    pid, first = ask_laya_choice(agent, {'decision_facts': {'action': action, 'live_people': len(persons)-1}, 'option_effects': person_effects}, action + '_person', 'Choose a live person or defer; compare actual needs, risks and costs.', persons, detailed=True)
    if pid == 'defer':
        return {'defer': True}, first
    plans = {k: row for k, row in plans.items() if str(row['pawn_id']) == pid}
    if action == 'society_growth':
        return _growth_choice(agent, next(iter(plans.values())), context, first)
    workers = {str(row.get('worker_id', 0)) for row in plans.values()}
    if len(workers) > 1:
        choices, effects = {}, {}
        for row in plans.values():
            worker = str(row.get('worker_id', 0))
            choices.setdefault(worker, row.get('label') or worker)
            effects.setdefault(worker, _effects(row, action, context))
        choices['defer'], effects['defer'] = 'Preserve workers', defer
        worker, raw = ask_laya_choice(agent, {'decision_facts': {'person': pid, 'need': person_effects[pid]['benefit']}, 'option_effects': effects}, action + '_worker', 'Choose an available caregiver/teacher/doctor, or defer.', choices, detailed=True)
        first['worker_choice'] = raw
        if worker == 'defer':
            return {'defer': True}, first
        plans = {k: row for k, row in plans.items() if str(row.get('worker_id', 0)) == worker}
    criteria = {k: row.get('label') or f"{row.get('value')} hour={row.get('hour')}" for k, row in plans.items()}
    option_effects = {k: _effects(row, action, context) for k, row in plans.items()}
    criteria['defer'], option_effects['defer'] = 'Keep current policy/jobs; needs may persist', defer
    key, raw = ask_laya_choice(agent, {'decision_facts': {'person': pid, 'diagnosis_need': person_effects[pid]['benefit']}, 'option_effects': option_effects}, action, DESCRIPTIONS[action], criteria, detailed=True)
    raw['society_person_choice'] = first
    return ({'defer': True} if key == 'defer' else _payload(plans[key])), raw


PENDING_WINDOWS = ("Dialog_GrowthMomentChoices",)


def peek_pending(client):
    try:
        return client.get("/api/v1/society/pending") is True
    except Exception:
        return False


def pending_action(context):
    options = context.get("options") or {}
    eligible = context.get("eligible_actions", options)
    if "society_growth_prepare" in eligible and options.get("society_growth_prepare"):
        return "society_growth_prepare"
    if "society_growth" in eligible and options.get("society_growth"):
        return "society_growth"
    return None


def execute(client: Any, snapshot: dict, map_state: dict, action: str, selected: dict) -> dict:
    if selected.get("defer"):
        map_state.setdefault("issued", {})["society:" + action] = int(snapshot.get("game", {}).get("tick") or 0)
        return {"applied": False, "reason": "laya_deferred"}
    live = collect(client, snapshot)
    fresh = {"map": snapshot["map"], "development": {"society": live}}
    prepare(fresh, {})
    rows = live.get("options", {}).get(action, {})
    row = next((r for r in rows.values() if _payload(r) == {k: selected[k] for k in _payload(r) if k in selected}), None)
    if row is None:
        return {"applied": False, "reason": "selection_no_longer_feasible"}
    payload = _payload(row)
    if action == "society_growth":
        moment = next((m for m in live.get("growth_moments") or [] if m.get("letter_id") == row["letter_id"] and m.get("pawn_id") == row["pawn_id"]), None)
        skills, trait = selected.get("skill_defs"), selected.get("trait_index")
        offered_traits = {t["index"] for t in (moment or {}).get("traits") or []}
        if (moment or {}).get("no_trait"):
            offered_traits.add(-2)
        if not offered_traits:
            offered_traits.add(-1)
        offered_skills = {p["def_name"] for p in (moment or {}).get("passions") or [] if p.get("current_passion") != "Major"}
        if not moment or not moment.get("ready") or type(trait) is not int or trait not in offered_traits or not isinstance(skills, list) or any(not isinstance(k, str) for k in skills) or len(set(skills)) != len(skills) or len(skills) != int(moment.get("passion_gains") or 0) or not set(skills).issubset(offered_skills):
            return {"applied": False, "reason": "growth_offer_changed_or_invalid"}
        payload.update(trait_index=trait, skill_defs=skills)
    endpoint = "/api/v1/society/order" if row.get("native") else "/api/v1/society/policy"
    result = client.post(endpoint, body={"map_id": snapshot["map"]["id"], **payload})
    if isinstance(result, dict) and result.get("applied"):
        map_state.setdefault("issued", {})["society:" + action] = int(snapshot.get("game", {}).get("tick") or 0)
    return result if isinstance(result, dict) else {"applied": False, "reason": "invalid_response"}
