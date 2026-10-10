"""Selected-actor wildlife choices. Native chance is distinct from harm heuristic."""
import json
from itertools import combinations
from laya_decisions import ask_laya_choice
from colony_retry import failure_record, recent
DESCRIPTIONS={'wildlife_hunt_plan':'Choose exact wild prey, a capable solo hunter or explicit ranged team, or defer. Native retaliation chance and equipment inform a contextual harm estimate; accepted jobs do not mean a kill.',
              'wildlife_hunt_lifecycle':'Release an observed hunt group or hand a downed wild animal to a normal hunter. Completion must be observed.'}
LABELS={'wildlife_hunt_plan':'охота выбранным охотником или группой','wildlife_hunt_lifecycle':'завершение групповой охоты'}
ACTIONS=set(DESCRIPTIONS)
DOMAINS={a:'work_orders' for a in ACTIONS}


def collect(client,snapshot):
    data=client.get('/api/v1/wildlife/hunt-context',map_id=snapshot['map']['id'])
    if not isinstance(data,dict) or data.get('available') is not True:raise ValueError('wildlife hunt context unavailable')
    try:
        training=client.get('/api/v1/wildlife/training-context',map_id=snapshot['map']['id'])
        data['training']=training if isinstance(training,dict) else {'available':False}
    except Exception as exc:data['training']={'available':False,'reason':str(exc)[:160]}
    merge_training(snapshot,data.get("training") or {})
    return data


def merge_training(snapshot,context):
    if not context.get('available'):return
    index={row['id']:row for row in context.get('animals') or []}
    for animal in snapshot.get('animals') or []:
        progress=index.get(animal.get('id'))
        if not progress:continue
        animal['training_context']=progress
        existing=animal.get('trainables') or []
        if isinstance(existing,dict):existing=list(existing.values())
        native={row['def_name']:row for row in progress.get('trainables') or []}
        previous={row.get('def_name'):row for row in existing}
        animal['trainables']=[{**previous.get(name,{}),**row} for name,row in native.items()]


def training_readback(client,snapshot,animal_id,trainable=None,master_id=None):
    context=client.get('/api/v1/wildlife/training-context',map_id=snapshot['map']['id'])
    if not isinstance(context,dict) or not context.get('available'):return {'observed':False,'reason':'training_readback_unavailable'}
    animal=next((a for a in context.get('animals') or [] if a.get('id')==animal_id),None)
    if not animal:return {'observed':False,'reason':'training_animal_missing'}
    row=next((t for t in animal.get('trainables') or [] if t.get('def_name')==trainable),{})
    observed=bool(row.get('wanted')) if trainable else animal.get('master_id')==master_id and animal.get('follow_drafted') is True
    return {'observed':observed,'reason':'training_policy_observed' if observed else 'training_policy_not_observed',
            'learned':row.get('learned'),'steps':row.get('steps'),'total_steps':row.get('total_steps'),
            'prerequisites':row.get('prerequisites'),'decay_ticks':animal.get('degradation_period_ticks'),
            'completion':'learned' if row.get('learned') else 'learning_unverified'}


def contextual_risk(target,actors,mode):
    """Transparent comparative heuristic, never a victory probability."""
    if not actors or any(not a.get('group_feasible' if mode=='group' else 'solo_feasible') for a in actors):
        return {'label':'unknown','basis':'selected mode not feasible','chance':None}
    fields=('damage','burst','shooting_accuracy','health','range','armor_penetration','armor_sharp','armor_blunt','move_speed','warmup','cooldown','weapon_accuracy','shooter_factor_planned','planned_cover_pass','weather_accuracy','target_size_factor','apparel_sharp_weighted','apparel_blunt_weighted','effective_revenge_damage_event')
    if any(any(a.get(k) is None for k in fields) for a in actors) or target.get('health_scale') is None:
        return {'label':'unknown','basis':'equipment or target stats missing','chance':None}
    armor=max(0,float(target.get('armor_sharp') or 0))
    strength=sum(float(a['damage'])*max(1,float(a['burst']))*min(1,max(.0201,float(a['shooter_factor_planned'])*float(a['weapon_accuracy'])*float(a['planned_cover_pass'])*float(a['weather_accuracy'])*float(a['target_size_factor'])))*float(a['health'])
        / max(.5,float(a['warmup'])+float(a['cooldown'])) / (1+max(0,armor-float(a['armor_penetration']))) for a in actors)
    pack=len(target.get('nearby_pack_ids') or []) if target.get('pack_escalation_enabled') else 0
    pressure=strength/max(1,float(target['health_scale'])*8*max(.1,float(target.get('health',1)))*(1+pack))
    ranges=[float(a['range']) for a in actors]
    mobility=all(float(a['move_speed'])>=float(target.get('move_speed') or 0) for a in actors)
    protection=sum(min(float(a['armor_sharp'])+float(a['apparel_sharp_weighted']),float(a['armor_blunt'])+float(a['apparel_blunt_weighted'])) for a in actors)/len(actors)
    animal_dps=float(target.get('melee_strike') or 20)/max(.5,float(target.get('melee_cycle') or 2))
    chance=max(float(a.get('effective_revenge_damage_event') if a.get('effective_revenge_damage_event') is not None else a.get('effective_revenge_planned') or 0) for a in actors)
    score=pressure*(1.15 if mobility else .8)*(1+min(.5,protection))/max(.5,animal_dps/10)
    if min(ranges)<15:score*=.6
    label='manageable' if score>=2 else 'elevated' if score>=.8 else 'high'
    if chance>.5 and not mobility and len(actors)==1 and label=='manageable':label='elevated'
    return {'label':label,'chance':round(chance,3),'basis':'heuristic DPS/AP/coverage-weighted apparel/natural armor/range/native distance-hit factor/health/pack' ,
            'pressure_index':round(score,2),'injury_basis':'nominal damage per attack cycle vs remaining healthscale/armor and melee strike cycle; no injury time guarantee','pack_candidates':pack,'unknown':'hit rolls, path/target movement, wounds and pack escalation; no kill guarantee'}


def hunt_plans(context):
    plans={}
    rows=context.get('actor_options') or []
    for target in context.get('targets') or []:
        if target.get('hunting_pawn_ids'):continue
        pairs=[a for a in rows if a.get('target_id')==target.get('id')]
        for actor in pairs:
            if actor.get('solo_feasible'):
                key=f"{target['id']}|solo|{actor['pawn_id']}"
                plans[key]={'target':target,'mode':'solo','actors':[actor],'risk':contextual_risk(target,[actor],'solo')}
        joint=set(target.get('joint_group_actor_ids') or [])
        group=[a for a in pairs if a.get('group_feasible') and a.get('pawn_id') in joint]
        # These are actual selectable actors. Laya also has individually chosen
        # pairs and the full team, without treating unrelated bystanders as support.
        group=sorted(group,key=lambda a:a['pawn_id'])[:8]
        if len(group)>=2:
            teams=[group] + [list(pair) for pair in combinations(group,2)] if len(group)>2 else [group]
            for team in teams:
                ids=','.join(str(a['pawn_id']) for a in team)
                plans[f"{target['id']}|group|{ids}"]={'target':target,'mode':'group','actors':team,'risk':contextual_risk(target,team,'group')}
    return plans


def _context(snapshot):return (snapshot.get('development') or {}).get('wildlife') or {}

def active_group_actor_ids(snapshot,map_state):
    lease=map_state.get('wildlife_hunt_group') or {}
    if lease.get('map_id')!=snapshot.get('map',{}).get('id'):return set()
    target=lease.get('target_id');valid=set()
    cells=lease.get('cells') or {}
    for row in _context(snapshot).get('live_orders') or []:
        pid=row.get('pawn_id')
        if pid not in lease.get('pawn_ids',[]) or not row.get('drafted'):continue
        shot=row.get('current_job')=='AttackStatic' and row.get('target_id')==target
        go=row.get('current_job')=='Goto' and target in (row.get('queued_attack_ids') or []) and row.get('current_cell')==cells.get(str(pid))
        if shot or go:valid.add(pid)
    return valid


def protected_group_actor_ids(snapshot,map_state):
    lease=map_state.get('wildlife_hunt_group') or {}
    if lease.get('map_id')!=snapshot.get('map',{}).get('id'):return set()
    if not valid_status(_context(snapshot)):return set(lease.get('pawn_ids') or [])
    return active_group_actor_ids(snapshot,map_state)


def _lifecycle(snapshot,map_state):
    lease=map_state.get('wildlife_hunt_group') or {}
    if not lease:return None
    status=next((r for r in _context(snapshot).get('wild_status') or [] if r.get('id')==lease.get('target_id')),None)
    if status and status.get('downed') and not status.get('dead'):return 'handoff'
    if not status or status.get('dead'):return 'cleanup'
    tick=int(snapshot.get('game',{}).get('tick') or 0)
    health=status.get('health')
    if health is not None and float(health)<float(lease.get('lowest_health',1)):
        lease.update(lowest_health=float(health),progress_tick=tick)
    if tick-int(lease.get('tick',tick))>=5000 or tick-int(lease.get('progress_tick',lease.get('tick',tick)))>=2500:return 'cleanup'
    if not active_group_actor_ids(snapshot,map_state) and not lease.get('pending'):return 'cleanup'
    return None


def retry_signature(plans):
    return json.dumps({key:[p['target'].get('health'),p['target'].get('nearby_pack_ids'),
        [[a.get(k) for k in ('pawn_id','weapon','damage','armor_penetration','apparel_sharp_weighted','apparel_blunt_weighted','health','shooting')] for a in p['actors']]]
        for key,p in plans.items()},sort_keys=True)


def prepare(snapshot,map_state):
    dev=snapshot.setdefault('development',{});context=_context(snapshot)
    dev['wildlife_active_group_ids']=sorted(protected_group_actor_ids(snapshot,map_state))
    if context.get('available') is not True:return []
    plans=hunt_plans(context)
    tick=int(snapshot.get('game',{}).get('tick') or 0)
    memory=map_state.get('wildlife_hunt_retry') or {}
    signature=retry_signature(plans)
    if memory.get('signature')==signature and recent(memory,tick,15000):plans={}
    retries=map_state.get('wildlife_hunt_failed_plans') or {}
    plans={key:p for key,p in plans.items() if not (retries.get(key,{}).get('signature')==retry_signature({key:p}) and recent(retries.get(key,{}),tick,250))}
    if map_state.get('wildlife_hunt_group'):plans={}
    context['plans']=plans
    lifecycle=_lifecycle(snapshot,map_state);context['lifecycle']=lifecycle
    return (['wildlife_hunt_lifecycle'] if lifecycle else []) + (['wildlife_hunt_plan'] if plans else [])


def plan_facts(plan):
    target=plan['target'];actors=plan['actors'];risk=plan['risk']
    def span(key):
        values=[round(float(a.get(key) or 0),2) for a in actors]
        lo,hi=min(values),max(values)
        return f"{lo:g}" if lo==hi else f"{lo:g}-{hi:g}"
    gear=' '.join(f"{label}:{span(key)}" for label,key in [('AP','armor_penetration'),('worn','apparel_sharp_weighted'),
        ('skill','shooting'),('hp','health'),('range','range')])
    gear+=f" needs:{span('rest')}/{span('food')}"
    if any(a.get('malnutrition') is not None for a in actors):
        gear+=f" malnutrition:{span('malnutrition')} consciousness:{span('consciousness')} manipulation:{span('manipulation')}"
    return {'prey':target.get('def'),'mode':plan['mode'],'ids':','.join(str(a['pawn_id']) for a in actors),
            'chance_per_hit':risk.get('chance'),'harm':risk['label'],'pack':risk.get('pack_candidates'),
            'gear':gear,'unknown':'heuristic; no guarantee'}


def target_plan_summary(target,plans):
    options=[p for p in plans.values() if p['target']['id']==target['id']]
    order={'manageable':0,'elevated':1,'high':2,'unknown':3}
    best=min(options,key=lambda p:(order.get(p['risk']['label'],3),len(p['actors'])))
    weapons=sorted({str(a.get('weapon') or 'unknown') for a in best['actors']})
    return (f"{target['def']}: available {best['mode']} {len(best['actors'])} actors {best['risk']['label']}; "
            f"{','.join(weapons)}; meat {target.get('meat')}; participants chosen next")


def choose(agent,state,action,snapshot):
    context=_context(snapshot)
    if action=='wildlife_hunt_lifecycle':return {'mode':context.get('lifecycle')},{'mode':'observed_group_lifecycle'}
    plans=context.get('plans') or {};targets={str(p['target']['id']):p['target'] for p in plans.values()}
    key,raw_target=ask_laya_choice(agent,state,'wildlife_target','Compare actual feasible hunter/team plans or leave wildlife alone. Available strength describes an executable option, not bystanders; exact participants are selected next.',
        {**{key:target_plan_summary(t,plans) for key,t in targets.items()},'defer':'Preserve wildlife and labor.'},detailed=True)
    if key=='defer':return {'defer':True},raw_target
    target_plans={k:p for k,p in plans.items() if str(p['target']['id'])==key}
    criteria={k:f"{p['mode']} ids{[a['pawn_id'] for a in p['actors']]}; harm {p['risk']['label']}; revenge/hit {p['risk'].get('chance')}; {[(a.get('weapon'),a.get('shooting')) for a in p['actors']]}" for k,p in target_plans.items()}
    picked,raw=ask_laya_choice(agent,{**state,'option_effects':{k:{'benefit':f"{p['target'].get('meat')} meat if killed/butchered",'risk':str(p['risk']),'cost':'selected actors leave work; group remains drafted','inaction':'wildlife remains; food need unresolved','uncertainty':'comparative heuristic, no success guarantee'} for k,p in target_plans.items()}},'wildlife_force','Compare actual solo hunter or explicit team; only selected ids participate.',{**criteria,'defer':'Prepare food or gear first.'},detailed=True)
    if picked=='defer':return {'defer':True},raw
    plan=target_plans[picked]
    confirm,confirmed=ask_laya_choice(agent,{'decision_facts':plan_facts(plan)},'wildlife_commit','Commit this exact target/force or defer. Retaliation chance and likely harm are distinct.',{'proceed':'Issue normal jobs for selected actors; outcome unverified.','defer':'Preserve actors and animal.'},detailed=False)
    return {'key':picked,'defer':confirm!='proceed'}, {'steps':[raw_target,raw,confirmed]}


def valid_status(data):
    return (isinstance(data,dict) and data.get('available') is True
        and isinstance(data.get('live_orders'),list) and isinstance(data.get('wild_status'),list)
        and all(isinstance(r,dict) and 'pawn_id' in r and 'drafted' in r and 'current_job' in r and isinstance(r.get('queued_attack_ids'),list) for r in data['live_orders'])
        and all(isinstance(r,dict) and 'id' in r and 'health' in r and 'dead' in r and 'downed' in r for r in data['wild_status']))


def unresolved(snapshot,map_state,reason):
    ids=(map_state.get('wildlife_hunt_group') or {}).get('pawn_ids',[])
    snapshot.setdefault('development',{})['wildlife_active_group_ids']=ids
    return {'applied':False,'available':False,'reason':reason,'unresolved_actor_ids':ids,'lease_retained':True}


def cleanup(client,snapshot,map_state,reason='lifecycle'):
    lease=map_state.get('wildlife_hunt_group') or {}
    if not lease:return {'applied':False,'reason':'no_hunt_group'}
    tick=int(snapshot.get('game',{}).get('tick') or 0)
    retrying=recent(lease.get('cleanup_retry') or {},tick,250)
    response=None;error=None
    if not retrying:
        try:
            response=client.post('/api/v1/wildlife/hunt-order',body={'map_id':lease['map_id'],'target_id':lease['target_id'],'mode':'cleanup','pawn_ids':lease['pawn_ids'],'owned_draft_ids':lease.get('owned_draft_ids',[])})
        except Exception as exc:error=str(exc)
    try:
        fresh=client.get('/api/v1/wildlife/hunt-status',map_id=lease['map_id'])
        if not valid_status(fresh):raise ValueError('cleanup_readback_incomplete')
        snapshot.setdefault('development',{})['wildlife']={**_context(snapshot),**fresh}
        remaining=active_group_actor_ids(snapshot,map_state)
        remaining |= {r['pawn_id'] for r in fresh['live_orders'] if r['pawn_id'] in lease.get('owned_draft_ids',[]) and r.get('drafted')}
        if not remaining:
            # Complete GET evidence reconciles a lost ACK, even during retry.
            map_state.pop('wildlife_hunt_group',None)
            snapshot['development']['wildlife_active_group_ids']=[]
            return {'applied':True,'reason':'cleanup_state_observed','response':response,'remaining_actor_ids':[]}
        if not retrying:lease['cleanup_retry']=failure_record(tick,15)
        snapshot['development']['wildlife_active_group_ids']=sorted(remaining)
        return {'applied':False,'reason':'cleanup_retry_waiting' if retrying else reason,'response':response,
                'remaining_actor_ids':sorted(remaining),'unresolved_actor_ids':sorted(remaining),'lease_retained':True}
    except Exception as exc:
        if not retrying:lease['cleanup_retry']=failure_record(tick,15)
        return unresolved(snapshot,map_state,'cleanup_unverified: '+str(error or exc))


def refresh_group(client,snapshot,map_state):
    if not map_state.get('wildlife_hunt_group'):return {'active_ids':[]}
    try:
        fresh=client.get('/api/v1/wildlife/hunt-status',map_id=snapshot['map']['id'])
        if not valid_status(fresh):raise ValueError('status unavailable or incomplete')
        snapshot.setdefault('development',{})['wildlife']={**_context(snapshot),**fresh}
        lease=map_state.get('wildlife_hunt_group') or {}
        if lease.get('pending'):
            recovered=[]
            for row in fresh.get('live_orders') or []:
                if row.get('pawn_id') in lease.get('pawn_ids',[]) and row.get('drafted') and (
                    row.get('current_job')=='AttackStatic' and row.get('target_id')==lease.get('target_id') or
                    row.get('current_job')=='Goto' and lease.get('target_id') in (row.get('queued_attack_ids') or [])):
                    recovered.append(row['pawn_id'])
                    if row.get('current_job')=='Goto':lease.setdefault('cells',{})[str(row['pawn_id'])]=row.get('current_cell')
            lease.update(pending=False,pawn_ids=recovered or lease.get('pawn_ids',[]))
        mode=_lifecycle(snapshot,map_state)
        if mode=='cleanup':return cleanup(client,snapshot,map_state,'target_gone_or_stalled')
        if mode=='handoff':return execute(client,snapshot,map_state,'wildlife_hunt_lifecycle',{'mode':'handoff'})
        ids=sorted(active_group_actor_ids(snapshot,map_state));snapshot['development']['wildlife_active_group_ids']=ids
        return {'active_ids':ids}
    except Exception as exc:return unresolved(snapshot,map_state,'group_status_unverified: '+str(exc))


def execute(client,snapshot,map_state,action,selected):
    context=_context(snapshot);tick=int(snapshot.get('game',{}).get('tick') or 0)
    if action=='wildlife_hunt_lifecycle':
        if selected.get('mode')!='handoff':return cleanup(client,snapshot,map_state)
        lease=map_state.get('wildlife_hunt_group') or {}
        response=client.post('/api/v1/wildlife/hunt-order',body={'map_id':snapshot['map']['id'],'target_id':lease.get('target_id'),'mode':'handoff','pawn_ids':lease.get('pawn_ids',[]),'owned_draft_ids':lease.get('owned_draft_ids',[])})
        cleanup_result=cleanup(client,snapshot,map_state,'handoff_group_released')
        return {**response,'cleanup':cleanup_result,'completion':'unverified'}
    if selected.get('defer'):
        map_state['wildlife_hunt_retry']={**failure_record(tick,120),'signature':retry_signature(context.get('plans') or {})}
        return {'applied':False,'reason':'laya_deferred_wildlife_hunt'}
    key=selected.get('key');old=(context.get('plans') or {}).get(key)
    fresh=client.get('/api/v1/wildlife/hunt-context',map_id=snapshot['map']['id'])
    plan=hunt_plans(fresh).get(key)
    if not plan or not old:return {'applied':False,'reason':'selected_hunt_plan_no_longer_feasible'}
    ids=[a['pawn_id'] for a in plan['actors']]
    if plan['mode']=='group':
        map_state['wildlife_hunt_group']={'map_id':snapshot['map']['id'],'target_id':plan['target']['id'],'pawn_ids':ids,'tick':tick,'progress_tick':tick,'pending':True,
            'owned_draft_ids':[a['pawn_id'] for a in plan['actors'] if not a.get('drafted')], 'cells':{str(a['pawn_id']):a.get('firing_position') for a in plan['actors']}}
    try:
        response=client.post('/api/v1/wildlife/hunt-order',body={'map_id':snapshot['map']['id'],'target_id':plan['target']['id'],'mode':plan['mode'],'pawn_ids':ids})
    except Exception as exc:
        refreshed=refresh_group(client,snapshot,map_state) if plan['mode']=='group' else {}
        return {'applied':False,'outcome_unknown':True,'reason':'hunt_ack_unknown','error':str(exc),'recovery':refreshed,'completion':'unverified'}
    accepted=response.get('accepted_ids') or []
    if plan['mode']=='group' and accepted:
        orders=response.get('orders') or []
        map_state['wildlife_hunt_group']={'map_id':snapshot['map']['id'],'target_id':plan['target']['id'],'pawn_ids':accepted,'tick':tick,'progress_tick':tick,
             'pending':False,'owned_draft_ids':[row['pawn_id'] for row in orders if not row.get('was_drafted') and row['pawn_id'] in accepted],'cells':{str(row['pawn_id']):row.get('goto_cell') for row in orders if row['pawn_id'] in accepted}}
    elif plan['mode']=='group':map_state.pop('wildlife_hunt_group',None)
    if response.get('applied') is not True:
        map_state.setdefault('wildlife_hunt_failed_plans',{})[key]={**failure_record(tick,15),'signature':retry_signature({key:plan})}
    if plan['mode']=='group' and accepted and (response.get('applied') is not True or set(accepted)!=set(ids)):
        stopped=cleanup(client,snapshot,map_state,'partial_group_not_viable')
        return {**response,'applied':False,'reason':'partial_group_stopped','cleanup':stopped,'completion':'unverified'}
    return {**response,'risk':plan['risk'],'completion':'unverified'}


def assess(action,snapshot):
    return {'benefit':'Actual prey meat/leather if killed and processed; training can enable learned species abilities.',
            'cost':'Selected hunters/handlers leave other work; group drafting needs cleanup; training uses food/time/upkeep.',
            'risk':'Native retaliation per hit differs from heuristic injury risk; nearby packmates may join.',
            'inaction':'Animal remains wild; food need or unlearned training remains.',
            'uncertainty':'Movement, armor/hit rolls and handler job availability; accepted orders are not kills or learned skills.'}
