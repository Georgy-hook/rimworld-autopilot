"""Model-selected ordinary protection from allied murderous rage or Berserk.

Observe native hostility; never force recovery or invent a permanent Berserk victim.
"""
from laya_decisions import ask_laya_choice
from colony_retry import failure_record, recent
import rimworld_laya as bridge

ACTIONS={'mental_safety_response'}
DESCRIPTIONS={'mental_safety_response':'Protect allies from murderous rage or Berserk using an eligible ordinary move, arrest attempt or rescue, or observe. Concurrent raid defense and urgent care remain necessary.'}
LABELS={'mental_safety_response':'защита от агрессии союзника'}
DOMAINS={'mental_safety_response':'care'}
ENDPOINT='/api/v1/mental-safety/'


def read(client,snapshot):
    data=client.get(ENDPOINT+'context',map_id=snapshot['map']['id'])
    if not isinstance(data,dict) or data.get('available') is not True or data.get('map_id')!=snapshot['map']['id'] or any(not isinstance(data.get(k),list) for k in ('options','orders','threats')):
        raise bridge.RimApiError('Incomplete mental safety context')
    return data


def allied_mental_threats(combat):
    return [p for p in combat.get('colonists') or [] if not p.get('is_dead') and not p.get('is_downed')
            and p.get('is_in_mental_state') and p.get('mental_state_def') in {'Berserk', 'MurderousRage'}]


def reconcile_defence(client, snapshot, state):
    """Native owns exact job identity; Python requests only a stale recorded lease."""
    combat = snapshot.get('combat') or {}
    allies = {p.get('id') for p in combat.get('colonists') or []}
    need = (state.get('allied_defence_pending') or allied_mental_threats(combat)
            or any(p.get('current_job') in {'AttackStatic', 'AttackMelee'}
                   and p.get('current_job_target_id') in allies for p in combat.get('colonists') or []))
    if not need:
        return {'cancelled': [], 'pending': False}
    try:
        data = read(client, snapshot)
    except bridge.RimApiError:
        state['allied_defence_pending'] = True
        return {'cancelled': [], 'outcome_unknown': True}
    leases = data.get('defence_orders') or []
    state['allied_defence_pending'] = bool(leases)
    cancelled = []
    for row in leases:
        if row.get('stale') is not True or not row.get('key'):
            continue
        try:
            result = client.post(ENDPOINT + 'order', body={'map_id': snapshot['map']['id'], 'defence_key': row['key']})
            if isinstance(result, dict) and result.get('applied') is True:
                cancelled.append(row.get('actor_id'))
        except bridge.RimApiError:
            pass
    if cancelled:
        # Refresh before care or raid selects actors; cancellation does not undraft.
        try:
            snapshot['combat'] = client.get('/api/v1/combat/state', map_id=snapshot['map']['id'])
        except bridge.RimApiError:
            return {'cancelled': cancelled, 'outcome_unknown': True}
    return {'cancelled': cancelled, 'pending': bool(leases)}


def collect(client,snapshot):
    if not allied_mental_threats(snapshot.get('combat') or {}):
        return {'available':True,'map_id':snapshot['map']['id'],'options':[],'orders':[],'threats':[],'blocker':''}
    return read(client,snapshot)


def _scope(plan):return str((plan.get('session'),plan.get('key')))


def _memory(state,tick):
    memory=state.setdefault('mental_safety',{})
    if tick<memory.get('tick',tick):memory.clear()
    memory['tick']=tick
    failed=memory.setdefault('failed',{})
    for key,row in list(failed.items()):
        if not isinstance(row,dict) or not recent(row,tick,3000):failed.pop(key)
    while len(failed)>64:failed.pop(next(iter(failed)))
    return memory


def _observed(data,plan):
    row=next((r for r in data['orders'] if r.get('actor_id')==plan['actor_id']),{})
    if plan['kind']=='evacuate':return row.get('job')=='Goto' and row.get('cell')==plan.get('cell')
    return (row.get('job')==('Arrest' if plan['kind']=='arrest' else 'Rescue')
            and row.get('target_id')==(plan['aggressor_id'] if plan['kind']=='arrest' else plan['victim_id'])
            and row.get('bed_id')==plan.get('bed_id'))


def _distance(data,plan):
    row=next((r for r in data['orders'] if r.get('actor_id')==plan['actor_id']),{})
    if plan['kind']=='evacuate':target=plan.get('cell') or {}
    else:target=next((r.get('position') or {} for r in data['orders'] if r.get('actor_id')==(plan['aggressor_id'] if plan['kind']=='arrest' else plan['victim_id'])),{})
    pos=row.get('position') or {}
    return sum((pos[k]-target[k])**2 for k in ('x','z')) if all(k in pos and k in target for k in ('x','z')) else None


def _signature(data):
    return str((sorted((str(t.get('session')),str(t.get('victim_id')),str(t.get('target_id'))) for t in data.get('threats') or []),
                sorted(str(p.get('key')) for p in data.get('options') or [])))


def prepare(snapshot,state):
    data=snapshot.setdefault('development',{}).get('mental_safety') or {}
    tick=int(snapshot.get('game',{}).get('tick') or 0);memory=_memory(state,tick)
    plans={p['key']:p for p in data.get('options') or [] if isinstance(p,dict) and p.get('kind') in ('evacuate','arrest','rescue') and p.get('session') and p.get('key') and _scope(p) not in memory['failed']}
    data['plans']=plans
    if memory.get('active'):return []
    observed=memory.get('observe') or {}
    if isinstance(observed,dict) and observed.get('signature')==_signature(data) and recent(observed,tick,600):return []
    return ['mental_safety_response'] if data.get('threats') else []


def choose(agent,state,action,snapshot):
    data=snapshot['development']['mental_safety'];plans=data.get('plans') or {}
    rows={f'o{i}':p for i,p in enumerate(plans.values())}
    effects={k:{'benefit':f"{p.get('kind')} actor#{p.get('actor_id')} protects ally#{p.get('victim_id')} from ally#{p.get('aggressor_id')}; {p.get('label')}",'risk':f"native arrest acceptance {p.get('arrest_chance')}; {p.get('risk')}",'cost':'Actor time; ordinary arrest may imprison an ally; raid defense remains needed',
                'inaction':'Nearby allies remain at risk; Berserk can change targets','uncertainty':'Accepted job is not completed protection'} for k,p in rows.items()}
    effects['observe']={'benefit':'Preserve current care/defense','risk':data.get('blocker') or 'Aggressor may kill victim, including while downed',
                       'cost':'No protection order','inaction':'Allied mental threat continues; Berserk may change targets','uncertainty':'No safe eligible option may exist'}
    choice,raw=ask_laya_choice(agent,{**state,'decision_facts':{**(state.get('decision_facts') or {}),'mental_risks':[{k:t.get(k) for k in ('aggressor_id','victim_id','mental_state','named_victim','job','target_id')} for t in data.get('threats')[:4]]},'option_effects':effects},
        'mental_safety_response','Protect allies from the observed mental threat; Berserk has no permanent named victim. Weigh concurrent raid and care. Ordinary arrest can fail.',
        {**{k:p.get('label') for k,p in rows.items()},'observe':'Observe; preserve defense/care, victim remains at risk'},detailed=True)
    if choice not in {*rows,'observe'}:raise ValueError('Unverified mental protection choice')
    return {'plan':rows.get(choice),'considered':list(plans.values())},raw


def _adopt(memory,plan,data,tick):
    memory['active']={'plan':plan,'progress':failure_record(tick,90),'best_distance':_distance(data,plan)}


def execute(client,snapshot,state,action,selected):
    tick=int(snapshot.get('game',{}).get('tick') or 0);memory=_memory(state,tick);plan=selected.get('plan')
    if not plan:
        memory['observe']={**failure_record(tick,30),'signature':_signature(snapshot.get('development',{}).get('mental_safety') or {})}
        for p in selected.get('considered') or []:memory['failed'][_scope(p)]=failure_record(tick,15)
        return {'applied':False,'reason':'laya_observed_mental_risk','blocks_development':False}
    if memory.get('active'):return {'applied':False,'reason':'mental_response_pending','blocks_development':False}
    offered=(snapshot.get('development',{}).get('mental_safety',{}).get('plans') or {}).get(plan.get('key'))
    if offered!=plan:return {'applied':False,'reason':'unverified_mental_plan'}
    try:
        fresh=read(client,snapshot)
        if not any(p==plan for p in fresh['options']):return {'applied':False,'reason':'mental_choice_changed'}
        response=client.post(ENDPOINT+'order',body={'map_id':snapshot['map']['id'],'key':plan['key'],'session':plan['session']})
        rejected=isinstance(response,dict) and response.get('applied') is False
    except bridge.RimApiError:
        rejected=False;response={'outcome_unknown':True}
    try:
        data=read(client,snapshot)
        if _observed(data,plan):
            _adopt(memory,plan,data,tick)
            return {'applied':True,'reason':'mental_safety_job_observed','completion':'unverified','response':response,'blocks_development':False}
        memory['failed'][_scope(plan)]=failure_record(tick,30)
        return {'applied':False,'reason':'mental_safety_job_not_observed','response':response,'blocks_development':False}
    except bridge.RimApiError:
        if rejected:memory['failed'][_scope(plan)]=failure_record(tick,30)
        else:memory['active']={'plan':plan,'unknown':True,'progress':failure_record(tick,90)}
        return {'applied':False,'outcome_unknown':True,'reason':'mental_safety_readback_unknown','blocks_development':False}


def reconcile(client,snapshot,state):
    """Lease only this response; never suppress unrelated defense/care cycles."""
    tick=int(snapshot.get('game',{}).get('tick') or 0);memory=_memory(state,tick);active=memory.get('active')
    if not active:return {'active_ids':[]}
    plan=active['plan']
    observed_rages=allied_mental_threats(snapshot.get('combat') or {})
    combat=snapshot.get('combat') or {}
    if isinstance(combat.get('colonists'),list) and not any(t.get('id')==plan['aggressor_id'] and t.get('mental_state_session')==plan['session'] for t in observed_rages):
        memory.pop('active');return {'active_ids':[],'reason':'mental_state_ended_or_changed_normal_job_retained'}
    try:data=read(client,snapshot)
    except bridge.RimApiError:
        # Never blindly cancel/reassign an unknown job. After a finite window,
        # cease peaceful draft protection so urgent defense/care can take over.
        protection=[plan['actor_id']] if recent(active['progress'],tick,5000) else []
        return {'active_ids':protection,'pending_blocker':'Mental response readback unknown','lease_retained':True,'attention_required':not protection}
    if not any(t.get('session')==plan['session'] and (t.get('mental_state')=='Berserk' or t.get('victim_id')==plan['victim_id']) for t in data['threats']):
        memory.pop('active');return {'active_ids':[],'reason':'mental_state_ended_or_changed_normal_job_retained'}
    snapshot.setdefault('development',{})['mental_safety']=data
    if not _observed(data,plan):
        memory.pop('active');memory['failed'][_scope(plan)]=failure_record(tick,30)
        return {'active_ids':[],'reason':'mental_response_ended_unverified'}
    if active.pop('unknown',False):_adopt(memory,plan,data,tick);active=memory['active']
    distance=_distance(data,plan)
    if distance is not None and (active.get('best_distance') is None or distance<active['best_distance']):
        active.update(best_distance=distance,progress=failure_record(tick,90))
    if recent(active['progress'],tick,5000):return {'active_ids':[plan['actor_id']],'in_progress':True}
    if not any(t.get('session')==plan['session'] for t in data['threats']):
        memory.pop('active');return {'active_ids':[],'reason':'mental_state_ended_normal_job_retained'}
    if recent(active.get('cancel_retry') or {},tick,60):return {'active_ids':[plan['actor_id']],'pending_blocker':'Stalled mental response cancellation pending'}
    active['cancel_retry']=failure_record(tick,10)
    try:client.post(ENDPOINT+'order',body={'map_id':snapshot['map']['id'],'key':plan['key'],'session':plan['session'],'cancel':True,'option':plan})
    except bridge.RimApiError:pass
    try:
        fresh=read(client,snapshot)
        if not _observed(fresh,plan):
            memory.pop('active');memory['failed'][_scope(plan)]=failure_record(tick,30)
            return {'active_ids':[],'reason':'matching_stalled_mental_response_ended'}
    except bridge.RimApiError:pass
    return {'active_ids':[plan['actor_id']],'pending_blocker':'Stalled mental response cancellation pending'}


def assess(action,snapshot):
    data=snapshot.get('development',{}).get('mental_safety') or {}
    return {'benefit':'Protect named allied victim by ordinary move/arrest/rescue',
            'risk':'Arrest resistance, pursuit and concurrent raid; no guaranteed protection',
            'cost':'Selected actor time and possible imprisonment','inaction':'Victim may be killed even downed',
            'uncertainty':data.get('blocker') or 'Actual native job outcome unverified'}
