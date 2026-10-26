from __future__ import annotations

from typing import Any
import math

CLINICAL_CARE_JOBS = {'tendpatient', 'rescue', 'feedpatient'}


def active_clinical_care(row: dict[str, Any]) -> bool:
    name=str(row.get('current_job') or '').casefold()
    return name in CLINICAL_CARE_JOBS or name=='dobill' and row.get('has_care_job') is True


def protected_care_retreat_ids(snapshot: dict[str, Any]) -> set[int]:
    """Native IDs refer only to an exact still-running care escape job."""
    facts = snapshot.get('combat') or {}
    named = set(facts.get('care_retreat_pawn_ids') or [])
    return {p['id'] for p in facts.get('colonists') or [] if p.get('id') in named
            and p.get('current_job') == 'Goto' and not any(p.get(k) for k in ('is_dead', 'is_downed', 'is_in_mental_state'))}


def self_tend_candidates(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """A new self-tend order must not replace care already owned by this pawn."""
    details = {p.get('id'): p for p in snapshot.get('colonists') or []}
    retreating = protected_care_retreat_ids(snapshot)
    return [p for p in (snapshot.get('combat') or {}).get('colonists') or []
            if p.get('tendable_now') and not p.get('is_dead') and not p.get('is_downed')
            and not p.get('is_in_mental_state') and not active_clinical_care(p)
            and p.get('id') not in retreating
            and not ((details.get(p.get('id'), {}).get('skills') or {}).get('Medicine') or {}).get('disabled')
            and not ((details.get(p.get('id'), {}).get('work_priorities') or {}).get('Doctor') or {}).get('disabled')
            and float(p.get('manipulation', 1) if p.get('manipulation') is not None else 1) > 0
            and float(p.get('moving', 1) if p.get('moving') is not None else 1) >= .65
            and opponent_distance(p, 0) > 4 and safe_new_self_tend(snapshot, p)]


def stable_patient_self_tend_binding(snapshot, doctor):
    """Only exact stable-patient care may yield to major doctor self-bleeding."""
    context = (snapshot.get('development') or {}).get('resilience') or {}
    if (context.get('available') is not True
            or any(context.get(key) for key in ('error', 'errors', 'read_errors'))):
        return None
    if (str(doctor.get('current_job') or '').casefold() != 'tendpatient'
            or type(doctor.get('queued_job_count')) is not int or doctor['queued_job_count'] != 0
            or doctor.get('carrying_pawn_id') or doctor.get('carrying_player_pawn')
            or doctor.get('is_drafted')
            or doctor.get('id') not in medically_capable_ids(snapshot)
            or not safe_new_self_tend(snapshot, doctor)):
        return None
    own = native_care_patient(snapshot, doctor)
    rate = own.get('bleeding_total')
    if (own.get('bleeding_evidence_complete') is not True or own.get('tendable_now') is not True
            or not isinstance(rate, (int, float)) or isinstance(rate, bool)
            or not math.isfinite(rate) or rate < 1.5):
        return None
    old_id = doctor.get('current_job_target_id')
    if not isinstance(old_id, int) or isinstance(old_id, bool) or old_id == doctor.get('id'):
        return None
    old_live = next((p for p in (snapshot.get('combat') or {}).get('colonists') or []
                     if p.get('id') == old_id and not p.get('is_dead')), None)
    if old_live is None:
        return None
    old = native_care_patient(snapshot, old_live)
    previous_rate = old.get('bleeding_total')
    if (old.get('bleeding_evidence_complete') is not True
            or not isinstance(previous_rate, (int, float)) or isinstance(previous_rate, bool)
            or not math.isfinite(previous_rate) or previous_rate != 0):
        return None
    conditions = old.get('conditions')
    if not isinstance(conditions, list) or any(not isinstance(h, dict) for h in conditions):
        return None
    for condition in conditions:
        if condition.get('visible') is False or condition.get('def_name') == 'BloodLoss':
            continue
        if (not condition.get('def_name') or not isinstance(condition.get('life_threatening'), bool)
                or not isinstance(condition.get('immunity_can_develop'), bool)
                or not isinstance(condition.get('tendable_now'), bool)):
            return None
        immunity = condition.get('immunity')
        if (condition.get('life_threatening')
                or condition.get('immunity_can_develop') and (
                    not isinstance(immunity, (int, float)) or isinstance(immunity, bool)
                    or not math.isfinite(immunity) or immunity < 1)
                or condition.get('tendable_now') and (
                    'infection' in condition['def_name'].casefold()
                    or not isinstance(condition.get('lethal_severity'), (int, float))
                    or not math.isfinite(condition['lethal_severity'])
                    or condition.get('lethal_severity', 0) > 0)):
            return None
    return {'reassign_from_patient_id': old_id,
            'care_yield_reason': 'stable_patient_to_critically_bleeding_doctor_self_tend'}


def safe_new_self_tend(snapshot: dict[str, Any], pawn: dict[str, Any]) -> bool:
    """Starting treatment needs time out of contact and incoming fire.

    Existing clinical jobs retain their separate protection and escape contract.
    """
    if not new_treatment_window(snapshot, pawn):
        return False
    here = _cell(pawn)
    for enemy in live_hostiles(snapshot):
        there = _cell(enemy)
        distance = math.dist(here, there) if here is not None and there is not None else opponent_distance(pawn, 0)
        if distance <= 18 or enemy.get('current_job_target_id') == pawn.get('id'):
            return False
        if pawn.get('id') in (enemy.get('shootable_opponent_ids') or []):
            return False
        if enemy.get('has_ranged_weapon') and not isinstance(enemy.get('shootable_opponent_ids'), list):
            if distance <= float(enemy.get('weapon_range') or 35) + 3:
                return False
    return True


def native_care_patient(snapshot: dict[str, Any], pawn: dict[str, Any]) -> dict[str, Any]:
    """Join clinical dictionaries by identity without changing combat strings."""
    return next((p for p in (snapshot.get('development') or {}).get('resilience', {}).get('patients') or []
                 if str(p.get('pawn_id')) == str(pawn.get('id'))), {})


def medically_capable_ids(snapshot: dict[str, Any]) -> set[int]:
    """Numerical Medicine skill alone does not establish legal, mobile care."""
    return {p['id'] for p in (snapshot.get('combat') or {}).get('colonists') or []
            if p.get('id') is not None and p.get('medical_work_enabled') is True
            and not any(p.get(k) for k in ('is_dead', 'is_downed', 'is_in_mental_state'))
            and all(isinstance(p.get(k), (int, float)) and math.isfinite(p[k]) and p[k] > .1
                    for k in ('consciousness', 'moving', 'manipulation'))}


def critical_field_treatment(snapshot: dict[str, Any], pawn: dict[str, Any]) -> bool:
    """Keep urgent field-care choices; chronic immunity zero is not a race."""
    native = native_care_patient(snapshot, pawn)
    detail = next((p for p in [*(snapshot.get('colonists') or []), *(snapshot.get('animals') or [])]
                   if str(p.get('id')) == str(pawn.get('id'))), {})
    bleeding = native.get('bleeding_total', pawn.get('bleeding_rate', detail.get('bleeding_rate')))
    if isinstance(bleeding, (int, float)) and math.isfinite(bleeding) and bleeding >= 1.5:
        return True
    deadline = native.get('bleedout_ticks')
    if (native.get('bleeding_evidence_complete') is True and isinstance(deadline, (int, float))
            and math.isfinite(deadline) and 0 <= deadline <= 1200
            and isinstance(bleeding, (int, float)) and bleeding >= .1):
        return True
    conditions = native.get('conditions') if isinstance(native.get('conditions'), list) else detail.get('health_conditions') or []
    for condition in conditions:
        if (not isinstance(condition, dict) or not condition.get('tendable_now')
                or condition.get('def_name') in {'Hypothermia', 'Heatstroke', 'Frostbite', 'BloodLoss', 'Malnutrition', 'ToxicBuildup'}):
            continue
        immunity = condition.get('immunity')
        if (condition.get('life_threatening') is True
                or condition.get('immunity_can_develop') is True and isinstance(immunity, (int, float)) and 0 <= immunity < 1):
            return True
        lethal, severity = condition.get('lethal_severity'), condition.get('severity')
        if (condition.get('can_ever_kill') is True and isinstance(lethal, (int, float)) and lethal > 0
                and isinstance(severity, (int, float)) and severity >= lethal * .5):
            return True
    return False


def new_treatment_window(snapshot: dict[str, Any], pawn: dict[str, Any]) -> bool:
    """A temporarily blocked ray does not shelter a new routine treatment.

    This gates new choices only. Critical field care remains a risk to compare;
    existing care and its exact native escape contract are not interrupted.
    """
    threats = live_hostiles(snapshot)
    if not threats or critical_field_treatment(snapshot, pawn):
        return True
    if ranged_capable(pawn) and any(is_abduction_threat(enemy, snapshot) for enemy in threats):
        return False  # Compare interception before starting another routine gunner's treatment.
    clinical = native_care_patient(snapshot, pawn)
    enclosed = (clinical.get('room_id') is not None and clinical.get('room_outdoors') is False
                and clinical.get('room_roof_complete') is True)
    here = _cell(pawn)
    for enemy in threats:
        there = _cell(enemy)
        distance = math.dist(here, there) if here is not None and there is not None else opponent_distance(pawn, 0)
        if (not math.isfinite(distance) or distance <= 18
                or enemy.get('current_job_target_id') == pawn.get('id')
                or pawn.get('id') in (enemy.get('shootable_opponent_ids') or [])):
            return False
        if enemy.get('has_ranged_weapon') or enemy.get('is_building'):
            loaded_range = enemy.get('weapon_range')
            if not isinstance(loaded_range, (int, float)) or not math.isfinite(loaded_range) or loaded_range <= 0:
                loaded_range = 35
            if distance <= loaded_range + 8 and not enclosed:
                return False
    return True


def opponent_distance(row: dict[str, Any], unknown: float = 9999) -> float:
    """Preserve contact at zero; missing/nonfinite telemetry cannot prove distance."""
    value = row.get("distance_to_nearest_opponent")
    if value is None:
        return unknown
    try:
        distance = float(value)
    except (TypeError, ValueError):
        return unknown
    return distance if math.isfinite(distance) and distance >= 0 else unknown


def _cell(row: dict[str, Any] | None) -> tuple[float, float] | None:
    position = (row or {}).get("position") or {}
    if position.get("x") is None or position.get("z") is None:
        return None
    return float(position["x"]), float(position["z"])


def live_hostiles(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in [*((snapshot.get("combat") or {}).get("hostiles") or []), *((snapshot.get("combat") or {}).get("hostile_buildings") or [])]
            if not row.get("is_dead") and not row.get("is_downed") and row.get("active_threat", True)]


def contact_opponents(snapshot: dict[str, Any], pawn: dict[str, Any]) -> list[dict[str, Any]]:
    """Exact live contact; aggregate nearest distance can include downed enemies."""
    here=_cell(pawn)
    if here is None:
        return []
    return [enemy for enemy in live_hostiles(snapshot)
            if not enemy.get('is_building') and _cell(enemy) is not None
            and math.dist(here,_cell(enemy)) <= 1.5]


def stationary_firing_candidate(row: dict[str, Any], snapshot: dict[str, Any] | None = None) -> bool:
    """An exposed mobile gun needs a cover review; an immobile gun can still fire."""
    if snapshot is not None and float(row.get('moving', 1)) >= .65:
        allies={p.get('id'):p for p in (snapshot.get('combat') or {}).get('colonists') or []}
        for enemy in live_hostiles(snapshot):
            if is_kidnapper(enemy):
                return False  # A fleeing carrier still requires the predictive firing window.
            if is_abduction_threat(enemy, snapshot) and enemy.get('id') not in (row.get('shootable_opponent_ids') or []):
                return False  # Missing lanes need interception; an actual shot remains useful.
            pursued=allies.get(enemy.get('current_job_target_id'))
            if (pursued and enemy.get('current_job') in {'AttackMelee','PredatorHunt'}
                    and _cell(enemy) is not None and _cell(pursued) is not None
                    and math.dist(_cell(enemy),_cell(pursued)) <= 8
                    and enemy.get('id') not in (row.get('shootable_opponent_ids') or [])):
                return False  # A missing lane needs review; an actual covering shot remains useful.
    exposure = row.get('incoming_ranged_exposure')
    return (ranged_capable(row) and isinstance(row.get('shootable_opponent_ids'), list)
            and not (isinstance(exposure, (int, float)) and math.isfinite(exposure)
                     and exposure > .6 and float(row.get('moving', 1)) >= .65))


def held_defensive_corridor(snapshot: dict[str, Any]) -> bool:
    """A healthy firing group must not abandon a still working native choke."""
    foes=live_hostiles(snapshot)
    if not foes or any(p.get('has_ranged_weapon') or p.get('is_building') or is_abduction_threat(p, snapshot) for p in foes):
        return False
    if any(opponent_distance(p,0)<=3 for p in foes):return False
    guns=[p for p in snapshot.get('combat',{}).get('colonists') or []
          if ranged_capable(p) and not p.get('is_dead') and not p.get('is_downed')]
    if any(p.get('bleeding_rate') is None or p.get('health') is None or p.get('moving') is None for p in guns):return False
    if any(float(p.get('bleeding_rate') or 0)>0 or float(p.get('health',1))<.85
           or float(p.get('moving',1))<.85 or p.get('is_in_mental_state') for p in guns):
        return False
    ready=[p for p in guns if p.get('is_drafted') and has_clear_shot(p,foes)
           and (p.get('current_job')=='AttackStatic' or p.get('is_warming_up'))]
    if len(ready)<2 or len(foes)>len(ready)*2:return False
    observed={p.get('id') for p in foes}
    return any(sum(enemy in (p.get('defended_approach_target_ids') or []) for p in ready)>=2 for enemy in observed)


def engaged_fighter_ids(snapshot: dict[str, Any]) -> set[int]:
    """An actual shot/contact or committed strike, not the drafted waiting job."""
    targets = {p.get('id'): p for p in live_hostiles(snapshot)}
    result = set()
    for pawn in (snapshot.get('combat') or {}).get('colonists') or []:
        if pawn.get('is_dead') or pawn.get('is_downed') or not pawn.get('is_drafted'):
            continue
        job = str(pawn.get('current_job') or '').casefold()
        target = targets.get(pawn.get('current_job_target_id'))
        actual = pawn.get('is_warming_up') is True or job in {'attackmelee', 'castverb'}
        if job == 'attackstatic' and target and has_clear_shot(pawn, [target]):
            actual = True
        if (job == 'goto' and pawn.get('combat_plan') in {'preemptive_strike', 'intercept_kidnapper'}
                and set(pawn.get('queued_attack_target_ids') or []).intersection(targets)):
            actual = True
        if actual and pawn.get('id') is not None:
            result.add(int(pawn['id']))
    return result


def safe_work_actor_ids(snapshot: dict[str, Any], *, allow_idle_drafted: bool = False) -> set[int]:
    """A conservative observed work window, never a declaration of raid victory.

    Missing distance, an assault/kidnap/predator order or an active allied attack
    cannot authorize stand-down. Native route/target guards still govern work.
    Patients can remain with their own caregivers while unrelated workers act.
    """
    hostiles = live_hostiles(snapshot)
    allies = [p for p in (snapshot.get("combat") or {}).get("colonists") or [] if not p.get("is_dead")]
    if not hostiles or not allies:
        return set()
    for enemy in hostiles:
        if is_kidnapper(enemy):
            return set()
        if not enemy.get("is_building") and not hostile_is_preparing(enemy):
            return set()
    radius = max(35, max((float(e.get("weapon_range") or 0) + 12 for e in hostiles), default=35))
    if any(opponent_distance(p, float('inf')) <= 12 for p in allies):
        return set()  # A nearby exposed ally requires defense/care, not optional development.
    protected = protected_emergency_care_ids(snapshot)
    engaged = engaged_fighter_ids(snapshot)
    actors = set()
    for pawn in allies:
        if opponent_distance(pawn, 0) <= radius:
            continue
        if pawn.get("is_downed") or pawn.get("is_in_mental_state") or pawn.get("id") in protected:
            continue
        job = str(pawn.get("current_job") or "").casefold()
        if pawn.get('id') in engaged or job == 'predatorhunt':
            continue
        if pawn.get("is_drafted"):
            idle = job in {'wait_combat', 'wait', 'wait_maintainposture', 'attackstatic'}
            idle |= job == 'goto' and pawn.get('combat_plan') not in {'preemptive_strike','intercept_kidnapper'} and not pawn.get('queued_attack_target_ids')
            if not allow_idle_drafted or not idle:
                continue
        if pawn.get("id") is not None:
            actors.add(int(pawn["id"]))
    return actors


def care_at_bedside(row: dict[str, Any], snapshot: dict[str, Any]) -> bool | None:
    """A queued medical job may still be walking across the map."""
    if isinstance(row.get('care_at_bedside'), bool):
        return row['care_at_bedside']
    target = row.get('care_target_position')
    patient_id = row.get('care_target_id')
    if patient_id is None:
        feeding = str(row.get('current_job') or '').casefold() in {'feedpatient', 'bottlefeedbaby'}
        patient_id = row.get('current_job_target_id_b' if feeding else 'current_job_target_id')
        if not feeding: target = target or row.get('current_job_target_position')
    if not isinstance(target, dict):
        target_row = next((p for p in snapshot.get('combat', {}).get('colonists', [])
                           if p.get('id') == patient_id), {})
        target = target_row.get('position')
    origin = _cell(row); destination = _cell({'position': target}) if isinstance(target, dict) else None
    if origin is None or destination is None:
        return None  # Older snapshots without actual target facts retain protection.
    return (origin[0] - destination[0]) ** 2 + (origin[1] - destination[1]) ** 2 <= 4


def protected_response_ids(snapshot: dict[str, Any]) -> set[int]:
    """Verify the actual named response, yielding only to evidenced immediate danger."""
    combat=snapshot.get('combat') or {}
    people={p.get('id'):p for p in combat.get('colonists') or []}
    detailed={p.get('id'):p for p in snapshot.get('colonists') or []}
    protected=set()
    for plan in combat.get('protected_response_plans') or []:
        if not isinstance(plan,dict) or plan.get('kind') not in ('evacuate','arrest','rescue'):continue
        actor=people.get(plan.get('actor_id')) or {};rage=people.get(plan.get('aggressor_id')) or {}
        if (actor.get('is_dead') or actor.get('is_downed') or actor.get('is_in_mental_state')
            or not actor.get('id') or rage.get('mental_state_def') not in {'MurderousRage','Berserk'}
            or not rage.get('is_in_mental_state') or not plan.get('session')
            or rage.get('mental_state_session')!=plan['session']
            or (rage.get('mental_state_def')=='MurderousRage' and rage.get('mental_state_target_id')!=plan.get('victim_id'))):continue
        if plan['kind']=='evacuate':
            cell=actor.get('current_job_cell') or {};wanted=plan.get('cell') or {}
            exact=actor.get('current_job')=='Goto' and all(k in cell and k in wanted and cell[k]==wanted[k] for k in ('x','z'))
        else:
            exact=(actor.get('current_job')==('Arrest' if plan['kind']=='arrest' else 'Rescue')
                and actor.get('current_job_target_id')==(plan.get('aggressor_id') if plan['kind']=='arrest' else plan.get('victim_id'))
                and actor.get('current_job_target_id_b')==plan.get('bed_id'))
        if not exact:continue
        pos=_cell(actor)
        if pos is None:continue
        if any(_cell(e) is not None and math.dist(pos,_cell(e))<=4 for e in live_hostiles(snapshot)):continue
        medical={**detailed.get(actor['id'],{}),**actor}
        bleeding=float(medical.get('bleeding_rate') or 0)
        conditions=[*(detailed.get(actor['id'],{}).get('health_conditions') or []),*(actor.get('health_conditions') or [])]
        life=any(h.get('is_currently_life_threatening') or h.get('life_threatening') for h in conditions if isinstance(h,dict))
        if life or (medical.get('tendable_now') and bleeding>=1.5):continue
        protected.add(actor['id'])
    return protected


def protected_emergency_care_ids(snapshot: dict[str, Any]) -> set[int]:
    """Generic combat cannot cancel clinical care, even near a hostile.

    Leaving a patient is a separate, exact native caregiver_retreat choice.
    Proximity alone does not authorize a group order to take the doctor.
    """
    care_jobs = {'tendpatient', 'rescue', 'feedpatient', 'dobill', 'deathrest', 'breastfeed',
                 'bottlefeedbaby', 'breastfeedcarrytomom', 'bringbabytosafety', 'bringbabytosafetyunforced',
                 'carrytomomafterbirth', 'babysuckle', 'babyplay', 'playstatic', 'playwalking', 'playtoys',
                 'lessongiving', 'lessonreceiving', 'prisonerinterrogateidentity'}
    protected = set()
    for row in (snapshot.get('combat') or {}).get('colonists') or []:
        if str(row.get('current_job') or '').casefold()=='dobill' and row.get('has_care_job') is False:
            continue
        if row.get('id') is not None and not row.get('is_dead') and active_clinical_care(row):
            protected.add(int(row['id']))
            continue
        if (row.get('id') is None or row.get('is_dead') or row.get('is_downed')
                or str(row.get('current_job') or '').lower() not in care_jobs or opponent_distance(row, 0) <= 4):
            continue
        bedside = care_at_bedside(row, snapshot)
        if bedside is False and errand_exposed(snapshot, row.get('position')):
            continue
        protected.add(int(row['id']))
    return protected | protected_response_ids(snapshot) | protected_care_retreat_ids(snapshot)


def ranged_capable(row: dict[str, Any]) -> bool:
    """Low capacity reduces accuracy; native weapon availability decides legality."""
    if not row.get('has_ranged_weapon') or not row.get('can_fight', True): return False
    if row.get('is_dead') or row.get('is_downed') or row.get('is_in_mental_state'): return False
    if isinstance(row.get('ranged_attack_available'), bool): return row['ranged_attack_available']
    return float(row.get('manipulation', 1)) > 0 and float(row.get('sight', 1)) > 0


def unsupported_animal_charge(snapshot: dict[str, Any], attackers: list[dict[str, Any]] | None = None) -> bool:
    """Known large animals do not justify an unsupported novice charge.

    Native combat power is a coarse risk flag, not predicted victory. Contact
    self-defense and withdrawal remain separate choices. A doctor, a distant
    gun or a gun without a firing lane cannot be counted as covering fire.
    """
    def positive(value: Any, default: float = 0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) and number >= 0 else default

    protected = protected_emergency_care_ids(snapshot)
    free = [p for p in (snapshot.get('combat') or {}).get('colonists') or []
            if not any(p.get(k) for k in ('is_dead', 'is_downed', 'is_in_mental_state'))
            and p.get('can_fight', True) and p.get('id') not in protected]
    attackers = [p for p in (attackers if attackers is not None else free)
                 if p in free and not p.get('has_ranged_weapon')
                 and positive(p.get('moving'), 1) >= .65]
    if not attackers:
        return False
    powers = [positive(p.get('combat_power')) for p in attackers]
    if not all(powers):
        return False  # Legacy telemetry cannot prove this relative-power flag.
    prepared = [p for p in attackers if p.get('weapon_def')
                and positive(p.get('health'), 1) >= .75
                and min(positive(p.get(k)) for k in ('moving', 'manipulation', 'consciousness')) >= .8
                and int(p.get('melee_skill') or 0) >= 6 and positive(p.get('armor_sharp')) >= .4]
    for enemy in live_hostiles(snapshot):
        if not enemy.get('is_animal') or positive(enemy.get('health'), 1) < .5:
            continue
        if positive(enemy.get('combat_power')) < 2 * max(powers):
            continue
        cover = [p for p in free if p not in attackers and ranged_capable(p)
                 and positive(p.get('health'), 1) >= .6
                 and isinstance(p.get('shootable_opponent_ids'), list) and has_clear_shot(p, [enemy])]
        if len(prepared) < 2 and not (prepared and cover):
            return True
    return False


def is_kidnapper(row: dict[str, Any]) -> bool:
    """A hostile must carry our pawn with observed kidnapping/exit intent."""
    if row.get('is_colonist') is True and not row.get('kidnapping_intent'):
        return False
    text=' '.join(str(row.get(k) or '') for k in ('current_job','lord_job_type','lord_toil_name')).lower()
    intent = row.get("kidnapping_intent") or "kidnap" in text or 'exitmap' in text or row.get('exit_map_on_arrival') is True
    return bool(row.get("carrying_pawn_id") and row.get("carrying_player_pawn") is True and intent)


def is_abduction_threat(row: dict[str, Any], snapshot: dict[str, Any]) -> bool:
    """Keep a confirmed carrier separate from an observed native pickup attempt."""
    if is_kidnapper(row):
        return True
    if (row.get('is_colonist') is True or row.get('is_hostile') is False
            or row.get('kidnapping_intent') is not True or row.get('current_job') != 'Kidnap'):
        return False
    return any(p.get('id') == row.get('current_job_target_id') and p.get('is_downed') is True
               and not p.get('is_dead') for p in (snapshot.get('combat') or {}).get('colonists') or [])


def intercept_capable(row: dict[str, Any], snapshot: dict[str, Any]) -> bool:
    if not ranged_capable(row) or row.get('id') in protected_emergency_care_ids(snapshot):
        return False
    targets = [e for e in live_hostiles(snapshot) if is_abduction_threat(e, snapshot)]
    visible = row.get('shootable_opponent_ids')
    if isinstance(visible, list) and any(e.get('id') in visible for e in targets):
        return True  # Native legal fire in place does not require running capacity.
    return bool(targets) and all(isinstance(row.get(k), (int, float)) and math.isfinite(row[k]) and row[k] >= .65
                                for k in ('moving', 'manipulation', 'sight'))


def carried_patient_ids(snapshot: dict[str, Any]) -> set[int]:
    """A carried ally must be released before a new bedside care assignment."""
    combat=snapshot.get('combat') or {}
    return {int(row['carrying_pawn_id']) for row in [*(combat.get('colonists') or []),*(combat.get('hostiles') or [])]
            if row.get('carrying_pawn_id') is not None}


def native_tactical_options(snapshot: dict[str, Any], tactic: str) -> dict[str, dict[str, Any]]:
    protected = protected_emergency_care_ids(snapshot)
    if tactic == 'caregiver_retreat':
        people = {p.get('id'): p for p in (snapshot.get('combat') or {}).get('colonists') or []}
        return {f"{o['fighter_id']}:{o['target_id']}": o
                for o in (snapshot.get('combat') or {}).get('native_options') or []
                if o.get('tactic') == tactic and o.get('fighter_id') in people
                and active_clinical_care(p := people[o['fighter_id']])
                and not any(p.get(k) for k in ('is_dead', 'is_downed', 'is_in_mental_state', 'carrying_pawn_id'))
                and o.get('expected_current_job') == p.get('current_job')
                and o.get('expected_care_patient_id') == (p.get('care_target_id') or
                    p.get('current_job_target_id_b' if str(p.get('current_job') or '').casefold() == 'feedpatient'
                          else 'current_job_target_id'))}
    return {f"{o['fighter_id']}:{o['target_id']}:{o.get('defense_building_id', 0)}": o
            for o in snapshot.get("combat", {}).get("native_options") or []
            if o.get("tactic") == tactic and o.get("fighter_id") not in protected}


def threat_radius(hostile: dict[str, Any]) -> float:
    """Keep ordinary errands outside a hostile's reach and a hive's guard area."""
    radius = max(22.0, min(55.0, float(hostile.get("weapon_range") or 0) + 8.0))
    if "defendandexpandhive" in str(hostile.get("lord_job_type") or "").lower() \
            and hostile_is_preparing(hostile):
        # A passive hive should not make the colony's food store unusable
        # while still denying pickup of guns and jelly in its defended area.
        return 20.0
    return radius


def errand_exposed(snapshot: dict[str, Any], destination: dict[str, Any] | None,
                   origin: dict[str, Any] | None = None) -> bool:
    """Reject a pickup, harvest or haul when its target or direct route meets a live threat.

    RimWorld may choose a longer path around terrain, so this is a conservative
    feasibility check, not proof that a route is safe. Missing coordinates also
    cannot justify ordering a civilian into an active threat.
    """
    hostiles = live_hostiles(snapshot)
    if not hostiles:
        return False
    target = _cell({"position": destination})
    start = _cell({"position": origin}) if origin is not None else None
    if target is None or (origin is not None and start is None):
        return True
    for hostile in hostiles:
        enemy = _cell(hostile)
        if enemy is None:
            return True
        radius_squared = threat_radius(hostile) ** 2
        if (target[0] - enemy[0]) ** 2 + (target[1] - enemy[1]) ** 2 <= radius_squared:
            return True
        if start is None:
            continue
        dx, dz = target[0] - start[0], target[1] - start[1]
        fraction = max(0.0, min(1.0, ((enemy[0] - start[0]) * dx
                                       + (enemy[1] - start[1]) * dz) / max(1.0, dx * dx + dz * dz)))
        closest = (start[0] + fraction * dx, start[1] + fraction * dz)
        if (closest[0] - enemy[0]) ** 2 + (closest[1] - enemy[1]) ** 2 <= radius_squared:
            return True
    return False


# These are strategic templates, not scripts with fixed coordinates.  RIMAPI
# resolves positions against the live map and rejects every route that crosses
# a friendly trap.  Keeping the catalogue here lets the model compare tactics
# without making the low-level safety code part of its prompt.
TACTICS: dict[str, dict[str, Any]] = {
    "stationary_fire": {
        "label": "Fire from the current position",
        "description": "Keep the current verified firing lane and concentrate fire without unnecessary movement, including a prepared choke. Recheck contact and incoming fire; a wounded shooter can remain exposed.",
        "tags": {"ranged", "defense"},
    },
    "hold_cover": {
        "label": "Hold strong cover",
        "description": "Use nearby walls, barricades, sandbags or shelves and make the enemy cross open ground.",
        "tags": {"general", "ranged", "defense"},
    },
    "focus_fire": {
        "label": "Concentrated fire",
        "description": "All safe shooters attack one high-priority target, reducing enemy damage quickly instead of spreading wounds.",
        "tags": {"general", "ranged"},
    },
    "civilian_retreat": {
        "label": "Withdraw unarmed civilians",
        "description": "Move mobile unarmed colonists away from the nearest hostile along a trap-free path instead of standing still or charging into melee.",
        "tags": {"unarmed", "fallback", "defense"},
    },
    "firing_line": {
        "label": "Safe firing line",
        "description": "Form a spaced line behind cover; adjacent shooters remain inside the short friendly-fire-safe envelope.",
        "tags": {"general", "ranged", "defense"},
    },
    "spread_out": {
        "label": "Disperse against explosives",
        "description": "Keep several cells between fighters to limit rockets, grenades, fire and area psycasts.",
        "tags": {"explosive", "siege", "drop_pod", "mechanoid"},
    },
    "kite": {
        "label": "Kite slow melee enemies",
        "description": "A fast ranged pawn draws pursuit while the firing group shoots; retreat paths must contain no friendly traps.",
        "tags": {"melee_enemy", "animal", "insect", "open_field"},
    },
    "backstep_fire": {
        "label": "Backstep and fire",
        "description": "Mobile shooters take short trap-free steps away from adjacent melee enemies, then fire again without leaving pursuit distance.",
        "tags": {"melee_enemy", "insect", "animal", "ranged"},
    },
    "screen_melee": {
        "label": "Melee screen for shooters",
        "description": "A capable but potentially exposed melee fighter intercepts the closest enemy while supporting shooters concentrate fire.",
        "tags": {"melee_enemy", "insect", "animal", "close_quarters"},
    },
    "melee_assault": {
        "label": "Coordinated melee assault",
        "description": "All mobile armed melee fighters attack together instead of retreating one by one. Closing across open ground can be deadly against guns or stronger enemies; any allied shooters provide covering fire.",
        "tags": {"melee_enemy", "ranged_enemy", "close_quarters", "assault"},
    },
    "melee_hold_line": {
        "label": "Hold a melee group",
        "description": "Gather sword fighters into one nearby group and intercept enemies when they close. This avoids a risky long charge but gives ranged enemies time to shoot and drafted fighters cannot rest or eat.",
        "tags": {"melee_enemy", "defense", "close_quarters"},
    },
    "coordinate_melee_roles": {
        "label": "Assign individual melee roles",
        "description": "Choose each armed melee fighter's role separately: attack, guard, lure, or withdraw. They receive orders in one cycle, so one can draw pursuit while others attack or cover the shooters.",
        "tags": {"melee_enemy", "close_quarters", "general"},
    },
    "lure_enemy": {
        "label": "Move an observed pursuer under covering fire",
        "description": "One mobile pawn moves through a checked escape corridor only while the selected enemy actually pursues them and ready guns fire at that same enemy. A pacifist may move but cannot attack. No new pursuit or hit is guaranteed.",
        "tags": {"defense", "coordination"},
    },
    "contact_melee": {
        "label": "Immediate contact self-defence",
        "description": "Defend against the named adjacent enemy. A gunner first tries a short checked escape and queued shot; melee is the fallback when no such route is feasible. No distant charge, pacifist attack or cancellation of protected patient care.",
        "tags": {"defense", "close_quarters"},
    },
    "advance_to_range": {
        "label": "Bring guns into range",
        "description": "Out-of-range shooters move in short trap-free steps while those already in range keep shooting. Advancing may expose the group.",
        "tags": {"ranged", "assault", "mechanoid", "insect"},
    },
    "withdraw_and_regroup": {
        "label": "Withdraw and regroup",
        "description": "Move the selected mobile fighters beyond immediate enemy reach along trap-free routes; this stops their fire temporarily and enemies may pursue. Once at safe distance, choose a new tactic rather than repeating withdrawal.",
        "tags": {"fallback", "ranged", "melee_enemy", "mechanoid"},
    },
    "staggered_retreat": {
        "label": "Staggered retreat",
        "description": "One element moves to the fallback line while the other covers, preventing a simultaneous rout.",
        "tags": {"general", "fallback", "ranged"},
    },
    "melee_block": {
        "label": "Three-on-one melee block",
        "description": "Hold a one-cell doorway or choke with up to three armored melee pawns and shoot over them from directly behind.",
        "tags": {"melee_enemy", "insect", "animal", "choke"},
    },
    "door_defense": {
        "label": "Doorway defense",
        "description": "Use an owned doorway as a controlled choke with short retreat access to the hospital and inner base.",
        "tags": {"melee_enemy", "drop_pod", "breach", "defense"},
    },
    "killbox_hold": {
        "label": "Hold the prepared kill zone",
        "description": "Occupy the colony's actual funnel and firing positions instead of chasing enemies outside it.",
        "tags": {"assault", "killbox", "defense"},
    },
    "fallback_line": {
        "label": "Withdraw to internal defenses",
        "description": "Use the verified inner firing line when breachers, drop pods or insects bypass the outer defenses.",
        "tags": {"breach", "drop_pod", "insect", "fallback"},
    },
    "wide_flank": {
        "label": "Wide flanking arc",
        "description": "Split healthy shooters between the main position and a safe side angle to negate one-direction cover.",
        "tags": {"siege", "staging", "ranged", "open_field"},
    },
    "pincer": {
        "label": "Two-sided pincer",
        "description": "Use two mutually supporting groups against a static or cover-dependent enemy; never isolate a single pawn.",
        "tags": {"siege", "staging", "cluster", "ranged"},
    },
    "counter_snipe": {
        "label": "Counter-snipe",
        "description": "Only long-range shooters expose themselves; everyone else remains behind cover or in reserve.",
        "tags": {"siege", "sniper", "staging"},
    },
    "rush_ranged": {
        "label": "Melee rush on ranged threats",
        "description": "Armored, mobile melee fighters close on isolated gunners so those enemies cannot continue firing.",
        "tags": {"ranged_enemy", "close_quarters"},
    },
    "emp_control": {
        "label": "EMP control",
        "description": "Stun mechanoids or shields with a verified EMP weapon while conventional fire focuses one disabled target.",
        "tags": {"mechanoid", "shield"},
    },
    "smoke_advance": {
        "label": "Smoke-covered advance",
        "description": "Advance under smoke against turrets or static guns, with melee and short-range weapons protected by the screen.",
        "tags": {"turret", "cluster", "siege"},
    },
    "siege_harass": {
        "label": "Hit-and-run against a siege",
        "description": "Long-range mobile shooters fire from maximum range and withdraw before the preparing enemy can answer.",
        "tags": {"siege", "staging", "open_field"},
    },
    "mortar_counterbattery": {
        "label": "Mortar counter-battery",
        "description": "Use completed, supplied mortars from the protected mortar post instead of crossing the map on foot.",
        "tags": {"siege", "cluster", "mortar"},
    },
    "drop_pod_encircle": {
        "label": "Encircle drop pods",
        "description": "Evacuate civilians, spread armed pawns around the landing room and attack from multiple doors after pods open.",
        "tags": {"drop_pod", "close_quarters"},
    },
    "infestation_choke": {
        "label": "Contain an infestation at a choke",
        "description": "Do not enter the hive room piecemeal; block its exit and concentrate short-range fire behind armored melee.",
        "tags": {"insect", "choke"},
    },
    "infestation_burn": {
        "label": "Controlled infestation burn",
        "description": "Only burn a sealed stone compartment after checking escape routes, temperature exposure and valuable contents.",
        "tags": {"insect", "fire"},
    },
    "cluster_poke": {
        "label": "Wake a mech cluster from range",
        "description": "Use maximum range or indirect fire, then withdraw to prepared EMP and firing positions before machines engage.",
        "tags": {"mechanoid", "cluster", "staging"},
    },
    "intercept_kidnapper": {
        "label": "Intercept a kidnapper",
        "description": "Stop a native pickup attempt on a downed ally or intercept a hostile carrying one. Keep an available shot; moving fighters need a checked firing window and cover.",
        "tags": {"kidnap", "rescue"},
    },
    "covered_rescue": {
        "label": "Rescue under covering fire",
        "description": "A mobile reserve rescues a downed ally only after shooters suppress the nearest threat and the route is clear.",
        "tags": {"rescue", "general"},
    },
    "fire_retreat": {
        "label": "Retreat from fire and heat",
        "description": "Break contact through a non-burning route and use the firefoam-protected fallback rather than fighting in superheated rooms.",
        "tags": {"fire", "fallback"},
    },
    "psycast_control": {
        "label": "Psychic crowd control",
        "description": "Use a feasible hostile psycast such as stun, vertigo, berserk, skip or wall control without exceeding heat or psyfocus limits.",
        "tags": {"psycast", "general"},
    },
    "psycast_support": {
        "label": "Psychic mobility/support",
        "description": "Use a feasible allied psycast such as focus, invisibility, waterskip or skip to rescue, reposition or protect the line.",
        "tags": {"psycast", "rescue", "general"},
    },
    "mortar_reload": {"label": "Reload mortar", "description": "Man an empty mortar and load permitted existing shells with hold fire. Observe the loaded shell before choosing a target.", "tags": {"mortar", "siege"}},
    "attack_structure": {"label": "Attack hostile structure", "description": "Use a feasible normal weapon attack against a visible hostile building or turret; compare range, explosion and shield risks.", "tags": {"turret", "cluster"}},
    "stand_down": {
        "label": "Stand down",
        "description": "Undraft everyone when the combat API verifies that no hostile pawn remains.",
        "tags": {"post_combat"},
    },
}


MECH_TOKENS = ("mech", "scyther", "lancer", "centipede", "pikeman", "militor", "tesseron", "termite", "diabolus", "war queen")
INSECT_TOKENS = ("insect", "megaspider", "spelopede", "megascarab")
EXPLOSIVE_TOKENS = ("grenade", "doomsday", "triple rocket", "inferno", "mortar")


def _text(row: dict[str, Any]) -> str:
    return " ".join(str(row.get(key) or "") for key in ("name", "kind_def", "faction", "weapon_def", "weapon_label", "current_job")).lower()


def _defense_types(snapshot: dict[str, Any]) -> set[str]:
    return {str(row.get("kind") or "").lower() for row in snapshot.get("combat", {}).get("defenses", [])}


def hostile_is_preparing(row: dict[str, Any]) -> bool:
    job = str(row.get("current_job") or "").lower()
    lord_toil = str(row.get("lord_toil_name") or "").lower()
    # A raider pauses in Wait_Combat while aiming during an active assault.
    # Treating that pause as staging repeatedly undrafts the defenders.
    if row.get('is_warming_up') is True or any(token in lord_toil for token in (
            "assault", "breach", "sap", "kidnap", "steal")):
        return False
    if any(token in job for token in ("attack", "breach", "sap", "kidnap", "steal")):
        return False
    animal = row.get('is_animal') is True or (row.get('is_animal') is None and
        str(row.get('kind_def') or '').casefold() in {'rat', 'yorkshireterrier', 'squirrel', 'hare', 'tortoise', 'iguana', 'raccoon'})
    if row.get('is_in_mental_state') and row.get('is_hostile'):
        return False
    if animal:
        return False
    # StageThenAttack names the entire raid, including its later assault.
    # The current toil is authoritative: walking inside a staging camp or a
    # drafted Wait_Combat job alone does not mean the assault has started.
    if any(token in lord_toil for token in ('stage', 'siege')):
        return True
    if job in {'wait_combat', 'goto'}:
        return False
    hive_guard = "defendandexpandhive" in str(row.get("lord_job_type") or "").lower()
    return hive_guard or any(token in job for token in ("wait", "wander", "prepare", "siege")) or any(
        token in lord_toil for token in ("stage", "siege")
    )


def guarded_hive_outside_contact(snapshot: dict[str, Any]) -> bool:
    """Do not approach a hive that is defending its own territory at a distance."""
    hostiles = live_hostiles(snapshot)
    return bool(hostiles) and all(
        "defendandexpandhive" in str(row.get("lord_job_type") or "").lower()
        and hostile_is_preparing(row)
        and opponent_distance(row) > 8
        for row in hostiles
    )


def insect_choke_door(snapshot: dict[str, Any]) -> int | None:
    """Find an owned doorway with walls on both flanks and fighters behind it."""
    combat = snapshot.get("combat") or {}
    walls = {
        (int(pos["x"]), int(pos["z"]))
        for row in combat.get("defenses") or [] if row.get("kind") == "wall"
        for pos in [row.get("position") or {}]
        if pos.get("x") is not None and pos.get("z") is not None
    }
    protected = protected_emergency_care_ids(snapshot)
    fighters = [row for row in combat.get("colonists") or []
                if not row.get("is_dead") and not row.get("is_downed")
                and not row.get("is_in_mental_state") and row.get("can_fight", True)
                and row.get("id") not in protected
                and (row.get("position") or {}).get("x") is not None
                and (row.get("position") or {}).get("z") is not None]
    insects = [row for row in live_hostiles(snapshot)
               if any(token in _text(row) for token in INSECT_TOKENS)
               and (row.get("position") or {}).get("x") is not None
               and (row.get("position") or {}).get("z") is not None]
    options: list[tuple[float, int]] = []
    for door in combat.get("defenses") or []:
        pos = door.get("position") or {}
        if (door.get("kind") != "door" or door.get("id") is None
                or pos.get("x") is None or pos.get("z") is None
                or float(door.get("hit_points_percent") if door.get("hit_points_percent") is not None else 1) < 0.5):
            continue
        x, z = int(pos["x"]), int(pos["z"])
        for insect in insects:
            target = insect["position"]
            dx, dz = int(target["x"]) - x, int(target["z"]) - z
            distance = (dx * dx + dz * dz) ** 0.5
            if distance < 2 or distance > 24:
                continue
            along_x = abs(dx) >= abs(dz)
            if any((int(other["position"]["x"]) - x) * dx <= 0 if along_x
                   else (int(other["position"]["z"]) - z) * dz <= 0
                   for other in insects):
                continue
            flank_a = (x, z - 1) if along_x else (x - 1, z)
            flank_b = (x, z + 1) if along_x else (x + 1, z)
            if flank_a not in walls or flank_b not in walls:
                continue
            if along_x:
                behind = [pawn for pawn in fighters
                          if (int(pawn["position"]["x"]) - x) * dx < 0]
            else:
                behind = [pawn for pawn in fighters
                          if (int(pawn["position"]["z"]) - z) * dz < 0]
            if not behind:
                continue
            if not any(pawn.get("weapon_def") and not pawn.get("has_ranged_weapon")
                       and int(pawn.get("melee_skill") or 0) >= 5
                       and float(pawn.get("armor_sharp") or 0) >= 0.4
                       and float(pawn.get("moving", 1)) >= 0.8
                       for pawn in behind):
                continue
            if sum(bool(pawn.get("has_ranged_weapon"))
                   and float(pawn.get("manipulation", 1)) >= 0.65
                   and float(pawn.get("sight", 1)) >= 0.65 for pawn in behind) < 2:
                continue
            approach = min((int(pawn["position"]["x"]) - x) ** 2
                           + (int(pawn["position"]["z"]) - z) ** 2 for pawn in behind)
            if approach > 20 ** 2:
                continue
            options.append((distance + approach ** 0.5 / 4, int(door["id"])))
    return min(options)[1] if options else None


def has_clear_shot(shooter: dict[str, Any], hostiles: list[dict[str, Any]]) -> bool:
    """Range alone is not a firing lane: walls and closed doors can block it."""
    if not shooter.get("has_ranged_weapon"):
        return False
    shootable = shooter.get("shootable_opponent_ids")
    if shootable is not None:
        live_ids = {int(row["id"]) for row in hostiles if row.get("id") is not None
                    and not row.get("is_dead") and not row.get("is_downed")}
        return bool(live_ids.intersection(int(pawn_id) for pawn_id in shootable))
    # Older installed RIMAPI builds exposed only distance. Keep their behavior
    # while the updated combat-state field is being deployed.
    return 2 < opponent_distance(shooter, 9999) <= float(shooter.get("weapon_range") or 0) + 1


def available_tactics(snapshot: dict[str, Any]) -> dict[str, str]:
    combat = snapshot.get("combat", {})
    hostiles = live_hostiles(snapshot)
    protected = protected_emergency_care_ids(snapshot)
    fighters = [row for row in combat.get("colonists", []) if not row.get("is_dead")
                and not row.get("is_downed") and not row.get("is_in_mental_state")
                and row.get("can_fight", True) and row.get("id") not in protected]
    if not hostiles:
        return {"stand_down": TACTICS["stand_down"]["description"]} if any(row.get("is_drafted") for row in fighters) else {}
    if not fighters:
        return {}

    hostile_text = [_text(row) for row in hostiles]
    hostile_jobs = " ".join(hostile_text)
    defenses = _defense_types(snapshot)
    stationary = [row for row in fighters if stationary_firing_candidate(row, snapshot) and has_clear_shot(row, hostiles)]
    ranged = [row for row in fighters if ranged_capable(row) and float(row.get('manipulation', 1)) >= .65
              and float(row.get('sight', 1)) >= .65 and float(row.get('moving', 1)) >= .65]
    armed_melee = [row for row in fighters if row.get("weapon_def") and not row.get("has_ranged_weapon")
                   and float(row.get("moving", 1)) >= 0.65]
    melee = [row for row in armed_melee if int(row.get("melee_skill") or 0) >= 5
             and float(row.get("moving", 1)) >= 0.8]
    armored_melee = [row for row in melee if float(row.get("armor_sharp") or 0) >= 0.4]
    psycasts = [ability for pawn in fighters for ability in (pawn.get("psycasts") or []) if ability.get("can_cast")]
    has_explosives = any(any(token in text for token in EXPLOSIVE_TOKENS) for text in hostile_text)
    has_insects = any(any(token in text for token in INSECT_TOKENS) for text in hostile_text)
    insects_only = all(any(token in text for token in INSECT_TOKENS) for text in hostile_text)
    has_kidnapper = any(is_abduction_threat(row, snapshot) for row in hostiles)
    staging = bool(fighters) and all(opponent_distance(row, 0) > 35 for row in fighters) and all(
        hostile_is_preparing(row) for row in hostiles
    )

    in_range = [row for row in ranged if has_clear_shot(row, hostiles)]
    exposed_civilians = [row for row in fighters if not row.get("weapon_def")
                         and opponent_distance(row, 9999) <= 18]
    contact = [row for row in ranged if opponent_distance(row, 9999) <= 2]
    names: list[str] = ["hold_cover"] if ranged and len(contact) < len(ranged) else []
    if stationary: names.append("stationary_fire")
    if armed_melee:
        names += ["melee_assault", "melee_hold_line"]
        if len(armed_melee) >= 2:
            names.append("coordinate_melee_roles")
    if ranged and (in_range or len(contact) < len(ranged)):
        names.append("focus_fire")
    if ranged and len(in_range) < len(ranged):
        names.append("advance_to_range")
    retreat_distance = max(18.0, min(45.0, max(
        (float(row.get("weapon_range") or 0) + 4.0 for row in hostiles if row.get("has_ranged_weapon")),
        default=0.0,
    )))
    if any(float(row.get("moving", 1)) > 0
           and opponent_distance(row, 9999) < retreat_distance
           for row in fighters):
        names.append("withdraw_and_regroup")
    if not ranged and not armed_melee and any(float(row.get("moving", 1)) > 0 for row in fighters):
        names.append("civilian_retreat")
    if len(ranged) >= 2:
        names.append("firing_line")
    if len(ranged) >= 2 and has_explosives:
        names.append("spread_out")
    if armored_melee and "door" in defenses:
        names += ["melee_block", "door_defense"]
    if "killbox" in defenses:
        names.append("killbox_hold")
    if "fallback" in defenses or "door" in defenses or "barricade" in defenses:
        names.append("fallback_line")
    if staging and len(ranged) >= 3 and all(float(row.get("moving", 1)) >= 0.8 for row in ranged):
        names += ["wide_flank", "pincer", "siege_harass"]
        if any(float(row.get("weapon_range") or 0) >= 30 for row in ranged):
            names.append("counter_snipe")
    if ranged and (any("drop" in text for text in hostile_text) or "waitmaintainposture" in hostile_jobs):
        names.append("drop_pod_encircle")
    if insects_only and armored_melee and len(ranged) >= 2 and insect_choke_door(snapshot) is not None:
        names.append("infestation_choke")
    if len(ranged) >= 2 and all(not row.get("has_ranged_weapon") for row in hostiles) and (has_insects or any("animal" in text or "manhunter" in text for text in hostile_text)):
        # Kiting is a coordinated lure-and-fire plan. A lone mobile pawn (or a
        # lure already outside pursuit distance) merely abandons the shooters.
        if any(
            float(lure.get("moving", 1)) >= 0.85
            and opponent_distance(lure, 9999) <= 16
            and any(
                support.get("id") != lure.get("id")
                and opponent_distance(support, 9999)
                <= float(support.get("weapon_range") or 0) + 12
                for support in ranged
            )
            for lure in ranged
        ):
            names.append("kite")
    if ranged and all(not row.get("has_ranged_weapon") for row in hostiles):
        if any(opponent_distance(row, 9999) <= 12
               and float(row.get("moving", 1)) >= 0.7 for row in ranged):
            names.append("backstep_fire")
        if any(float(row.get("moving", 1)) >= 0.65
               and int(row.get("melee_skill") or 0) >= 3
               and opponent_distance(row, 9999) <= 20
               for row in melee) and any(
                   opponent_distance(row, 9999)
                   <= float(row.get("weapon_range") or 0) + 1 for row in ranged):
            names.append("screen_melee")
    if any("gun" in text or "sniper" in text or "lancer" in text for text in hostile_text) and armored_melee:
        names.append("rush_ranged")
    if has_kidnapper and any(intercept_capable(row, snapshot) for row in fighters):
        names.insert(0, "intercept_kidnapper")
    if psycasts:
        if any(ability.get("hostile") for ability in psycasts):
            names.append("psycast_control")
        if any(not ability.get("hostile") for ability in psycasts):
            names.append("psycast_support")
    if not names:
        names = ["civilian_retreat"] if any(float(row.get("moving", 1)) > 0 for row in fighters) else []
    insect_contact = insects_only and any(
        opponent_distance(row, 9999) < 18 for row in fighters)
    if insect_contact and not armored_melee and len(armed_melee) < max(2, len(hostiles)):
        # One unarmored founder should not charge an active insect. A larger
        # sword group can still coordinate against a small number of bugs.
        names = [name for name in names if name != "melee_assault"]
        if len(ranged) < 2:
            names = [name for name in names if name not in {"melee_hold_line", "screen_melee"}]
            if not in_range:
                names = [name for name in names if name not in
                         {"hold_cover", "focus_fire", "advance_to_range", "firing_line"}]

    if unsupported_animal_charge(snapshot, armed_melee):
        names = [name for name in names if name not in {'melee_assault', 'rush_ranged'}]

    result: dict[str, str] = {}
    for native_tactic in ("emp_control", "smoke_advance", "mortar_counterbattery", "mortar_reload", "attack_structure", "lure_enemy", "contact_melee"):
        if native_tactical_options(snapshot, native_tactic):
            names.append(native_tactic)
    if ('intercept_kidnapper' in names and all(is_abduction_threat(e, snapshot) for e in hostiles)):
        last_shot = any(float(p.get('moving', 1)) < .65 and stationary_firing_candidate(p, snapshot)
                        and has_clear_shot(p, hostiles) for p in fighters)
        names = [name for name in names if name in {
            'intercept_kidnapper', 'withdraw_and_regroup', 'civilian_retreat',
            'psycast_control', 'psycast_support', 'contact_melee'} or name == 'stationary_fire' and last_shot]
    for name in names:
        if name not in result:
            description = TACTICS[name]["description"]
            if name in {"hold_cover", "firing_line"} and len(in_range) < len(ranged):
                description = (f"Hold cover: only {len(in_range)}/{len(ranged)} guns have a clear firing lane now; "
                               "blocked or out-of-range guns must move around walls before they can shoot."
                               + (" An unarmed ally may be captured." if exposed_civilians else ""))
            elif name in {"focus_fire", "advance_to_range"} and exposed_civilians:
                description = (f"{len(exposed_civilians)} unarmed ally(s) threatened nearby. "
                               "Move distant guns into range and order civilian retreat; guns may be exposed "
                               "or arrive too late.")
            if name == "melee_assault" and ranged:
                ready_support = sum(
                    has_clear_shot(row, hostiles)
                    for row in ranged
                )
                weakest_skill = min(int(row.get("melee_skill") or 0) for row in armed_melee)
                least_armor = min(float(row.get("armor_sharp") or 0) for row in armed_melee)
                strongest_enemy = max(int(row.get("melee_skill") or 0) for row in hostiles)
                description = (f"Charge now: {len(armed_melee)} melee, lowest skill {weakest_skill}, "
                               f"armor {least_armor:.1f}; enemy melee up to {strongest_enemy}. "
                               f"Only {ready_support}/{len(ranged)} guns can cover. "
                               "An unsupported low-skill fighter may lose a limb or die.")
            if name == "focus_fire" and len(in_range) < len(ranged):
                description += (f" Only {len(in_range)}/{len(ranged)} armed shooters have a clear shot now; "
                                "the rest will seek trap-free firing lanes, which may expose them.")
            if name == "focus_fire" and len(in_range) < len(hostiles):
                description += " Risk: fewer shooters are in range than active enemies; other fighters may be left exposed."
            if name == "intercept_kidnapper":
                description += (" Pursue the carrier in long trap-free moves and fire whenever a shot opens; "
                                "this exposes the pursuer and may leave the base undefended.")
            if name in {"withdraw_and_regroup", "civilian_retreat"}:
                slow = [row for row in fighters if 0 < float(row.get("moving", 1)) < 0.65]
                if slow:
                    description += (f" {len(slow)} wounded pawn(s) can still walk slowly; "
                                    "the native route check decides reachability, and faster enemies may catch them.")
            if name in {"focus_fire", "hold_cover", "firing_line"} and any(
                opponent_distance(row, 9999) <= 6 for row in ranged
            ):
                description += " Risk: a nearby melee enemy may prevent a shooter from firing; a short retreat or melee screen may be better."
            result[name] = description
    return result


def psycast_options(snapshot: dict[str, Any], hostile: bool | None = None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for pawn in snapshot.get("combat", {}).get("colonists", []):
        if pawn.get("is_dead") or pawn.get("is_downed") or pawn.get("is_in_mental_state"):
            continue
        for ability in pawn.get("psycasts") or []:
            if not ability.get("can_cast"):
                continue
            if hostile is not None and bool(ability.get("hostile")) != hostile:
                continue
            key = f"{int(pawn['id'])}:{ability.get('def_name')}"
            result[key] = {
                "pawn_id": int(pawn["id"]),
                "pawn": pawn.get("name"),
                **ability,
                "summary": (
                    f"{pawn.get('name')} — {ability.get('label') or ability.get('def_name')}; "
                    f"focus {float(pawn.get('psyfocus') or 0) * 100:.0f}%, "
                    f"heat {float(pawn.get('neural_heat') or 0):.0f}/{float(pawn.get('neural_heat_limit') or 0):.0f}; "
                    f"cost {float(ability.get('psyfocus_cost') or 0) * 100:.1f}% focus, "
                    f"+{float(ability.get('entropy_gain') or 0):.0f} heat; {ability.get('description') or ''}"
                ),
            }
    return result


def choose_default_target(snapshot: dict[str, Any], tactic: str) -> int | None:
    hostiles = live_hostiles(snapshot)
    if not hostiles:
        return None
    active_threats = [row for row in hostiles if not (
        "defendandexpandhive" in str(row.get("lord_job_type") or "").lower()
        and hostile_is_preparing(row)
        and opponent_distance(row) > 8
    )]
    if active_threats:
        hostiles = active_threats
    if tactic == "intercept_kidnapper":
        kidnapping = [row for row in hostiles if is_abduction_threat(row, snapshot)]
        if kidnapping:
            hostiles = kidnapping
    if tactic in {"emp_control", "cluster_poke"}:
        mechs = [row for row in hostiles if any(token in _text(row) for token in MECH_TOKENS)]
        if mechs:
            hostiles = mechs
    fighters = [row for row in snapshot.get("combat", {}).get("colonists", [])
                if not row.get("is_dead") and not row.get("is_downed") and not row.get("is_in_mental_state")
                and row.get("can_fight", True) and _cell(row) is not None]
    def distance(row: dict[str, Any]) -> float:
        position = row.get("position") or {}
        if not fighters or "x" not in position or "z" not in position:
            return opponent_distance(row, float("inf"))
        return min(((float(position["x"]) - float((pawn.get("position") or {}).get("x", position["x"]))) ** 2
                    + (float(position["z"]) - float((pawn.get("position") or {}).get("z", position["z"]))) ** 2) ** 0.5
                   for pawn in fighters)
    return int(max(hostiles, key=lambda row: (
        is_abduction_threat(row, snapshot),
        -(distance(row) // 12 if math.isfinite(distance(row)) else float("inf")),
        float(row.get("combat_power") or 0),
        -float(row.get("health") if row.get("health") is not None else 1),
    )).get("id"))


def threat_facts(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Compact live evidence for tactical choices; unknown mechanics stay explicit."""
    enemies = live_hostiles(snapshot)
    colonists = (snapshot.get("combat") or {}).get("colonists") or []
    return {
        "contact_fighters": [p.get("id") for p in colonists if not p.get("is_dead") and not p.get("is_downed") and opponent_distance(p) <= 2],
        "carriers": [{"id": e.get("id"), "carrying_pawn_id": e.get("carrying_pawn_id"), "job": e.get("current_job")} for e in enemies if is_kidnapper(e)],
        "abduction_attempts": [{"id": e.get("id"), "target_id": e.get("current_job_target_id")}
                               for e in enemies if is_abduction_threat(e, snapshot) and not is_kidnapper(e)],
        "preparing_hostiles": [e.get("id") for e in enemies if hostile_is_preparing(e)],
        "mental_state_colonists": [p.get("id") for p in colonists if p.get("is_in_mental_state")],
        "decision_facts": "Contact distance zero is immediate danger. Carrying a pawn does not prove kidnapping. Preparing enemies can wake or assault. Tactics require live geometry and job validation.",
        "uncertainty": "Visible hostile buildings/native weapon choices are observed; active fires, anomalous regeneration, EMP adaptation, mortar scatter and smoke effectiveness remain uncertain. Templates do not guarantee safety.",
    }
