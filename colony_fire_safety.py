"""A burning person is an immediate exact native job, not a work-priority ACK."""
import rimworld_laya as bridge
from laya_decisions import ask_laya_choice


def run_cycle(client, agent, snapshot, fire_state, log_path):
    if bridge.combat_planner.live_hostiles(snapshot):
        return None
    if fire_state.get('burning_pawns_available') is not True:
        return None  # Older native capability is unknown, never a no-fire assertion.
    patients = fire_state.get('burning_pawns')
    if not isinstance(patients, list):
        return {'timestamp':bridge.utc_now(),'mode':'burning-pawn-emergency','decision':{'choice':'unavailable'},
                'result':{'applied':False,'error':'invalid_native_burning_pawns'}}
    if not patients:
        return None
    context = client.get('/api/v1/resilience/context', map_id=int(snapshot['map']['id']))
    if not isinstance(context,dict) or context.get('available') is not True or any(context.get(k) for k in ('error','errors','read_errors')):
        result={'applied':False,'error':'native_burning_pawn_options_unavailable'}
        record={'timestamp':bridge.utc_now(),'mode':'burning-pawn-emergency','decision':{'choice':'unavailable'},'result':result}
        bridge.append_log(log_path,record);return record
    rows=[r for r in context.get('options') or []
          if r.get('kind')=='extinguish' and all(r.get(k) is not None for k in ('worker_id','target_id','giver'))]
    plans={f'extinguish_{index+1}':r for index,r in enumerate(rows)}
    if not plans:
        return None  # Current exact fire job may already own the available actor.
    choices={k:f"Send {r.get('worker') or r['worker_id']} to extinguish the attached fire on {r.get('target') or r['target_id']}. "
                  f"Native firefighter and route verified; distance {r.get('travel_distance','unknown')}. "
                  "This can replace ordinary unforced ground firefighting or optional work, never current/queued care or a later forced order."
             for k,r in plans.items()}
    choices['defer']='Leave these people burning for now; continued flame damage can kill them even with bleeding stopped. Ordinary tending does not extinguish fire.'
    effects={k:{'benefit':'Stop continuing fire damage to a living person.',
        'risk':'Native actor, work restrictions, reservations and route are rechecked.',
        'cost':f"Worker {r.get('worker') or r['worker_id']}; travel {r.get('travel_distance','unknown')} cells; optional current work yields.",
        'inaction':'The person continues burning and can die.',
        'uncertainty':'Accepted job is not completed extinguishing.'} for k,r in plans.items()}
    effects['defer']={'benefit':'Continue current optional work.','risk':'Continued fire can kill the downed person.',
        'cost':'No rescue now.','inaction':'Fire remains on the person.','uncertainty':'No recovery is established.'}
    answer,raw=ask_laya_choice(agent,{'decision_facts':{'burning_people':patients,'battle_clear':True},'option_effects':effects},'burning_pawn_response',
        'After the observed battle, a colonist or pet is still on fire. Prefer a feasible exact extinguishing job before optional cleaning, building, corpse work or routine ground fire. '
        'The game rechecks the exact fire, actor, work restrictions, reservations and safe route. Existing care remains protected. An accepted job is not proof the fire is out.',choices)
    choice=answer
    if choice=='defer':result={'applied':False,'deferred':True,'reason':'laya_deferred_pawn_fire'}
    else:
        row=plans[choice]
        result=client.post('/api/v1/resilience/order',body={'map_id':int(snapshot['map']['id']),
            **{k:row[k] for k in ('kind','worker_id','target_id','giver')}})
        if not isinstance(result,dict) or not isinstance(result.get('applied'),bool):
            result={'applied':False,'error':'invalid_native_extinguish_result','outcome_unknown':True}
    record={'timestamp':bridge.utc_now(),'mode':'burning-pawn-emergency','decision':{'choice':choice},'native_option':plans.get(choice),'result':result,'raw':raw}
    bridge.append_log(log_path,record);return record
