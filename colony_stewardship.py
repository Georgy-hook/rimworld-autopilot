"""Finite food, shelter and preservation plans backed by observed native state."""
from __future__ import annotations
import copy
import math
import colony_architect as architect
import colony_capabilities as crops
import colony_retry as retry
import colony_storage as storage
import colony_husbandry as husbandry
from laya_decisions import ask_laya_choice

DESCRIPTIONS = {
    'stewardship_crop_budget': 'Pause or resume future sowing in one existing field. Preserve every standing healthy plant; compare native human/animal demand, usable stock deadlines, concurrent harvests, season, growers, hauling and cooking. Excess capacity needs a finite winter/trade purpose. Never count standing yield as delivered food.',
    'stewardship_preservation_goal': 'Select a finite freezer material/research goal, before all components are available. Compare vulnerable food, accessible covered storage, power and construction labor. Mining/trade must obtain actual shortages. A goal produces no building or cold room.',
    'stewardship_shell_repair': 'Replace one actually missing wall or door of the recorded starter shelter using loaded costs and normal construction. Preserve existing structures and work; native placement must validate the cell. Blueprint is not an enclosed warm room.',
}
ACTIONS = set(DESCRIPTIONS)
LABELS = {a:a.removeprefix('stewardship_') for a in ACTIONS}
DOMAINS = {a:'work_orders' for a in ACTIONS}


def collect(client, snapshot):
    # Reuses separately validated live plant, production, building and project reads.
    return {'available':True, 'source':'current_native_module_observations'}


def sow_plans(snapshot):
    dev=snapshot.get('development') or {}; facts=crops.food_planning_facts(snapshot)
    definitions=crops.plant_definitions(snapshot); plans={}
    feed=husbandry.planning_context(snapshot)
    # Conservative shared-food allowance; species/diet and separate fodder remain in the native feed planner.
    demand=facts['human_demand_per_day']+float(feed.get('adult_allowance_nutrition_day') or feed.get('demand_now_nutrition_day') or 0)
    yield_day=facts['potential_crop_nutrition_per_day']
    stored=facts['stored_food_days']; ready=facts['ready_food_plants']
    fallout=any(c.get('def_name')=='ToxicFallout' for c in ((dev.get('resilience') or {}).get('environment') or {}).get('conditions') or [])
    excessive=bool(demand and yield_day>demand*1.6 and stored is not None and stored>=5
        and (feed.get('available') or not snapshot.get('animals')))
    gap=bool(facts['crop_capacity_gap'] or facts['first_harvest_gap'])
    for field in (dev.get('plant_catalog') or {}).get('growers') or []:
        if field.get('zone_id') is None or field.get('kind')=='new_ground' or type(field.get('allow_sow')) is not bool: continue
        definition=definitions.get(field.get('plant_def')) or {}
        if definition.get('human_edible_product') is not True: continue
        option=next((r for r in field.get('options') or [] if r.get('def_name')==field.get('plant_def')), {})
        want=False if fallout and not field.get('roofed') or excessive else True if gap and not fallout and option.get('safe_sowing_now') is True else None
        if want is None or want==field['allow_sow']: continue
        plans[str(field['zone_id'])]={'zone_id':field['zone_id'],'plant_def':field['plant_def'],
            'expected_allow_sow':field['allow_sow'],'allow_sow':want,'standing_plants':field.get('plant_count'),
            'reason':'unsafe_outdoor_sowing_during_fallout' if fallout else 'excess_repeat_capacity' if not want else 'fresh_supply_gap',
            'plant_preservation':True, 'forecast_days':option.get('calendar_days_to_harvest_estimate')}
    return plans


def preservation_goal(snapshot):
    dev=snapshot.get('development') or {}; production=dev.get('production') or {}
    if production.get('available') is False or any(b.get('def_name')=='Cooler' for b in production.get('buildings') or []): return None
    index=architect.catalog_index(dev.get('building_catalog') or [])
    if not all(name in index for name in ('Wall','Door','Cooler','PowerConduit')): return None
    facts=crops.food_planning_facts(snapshot); condition=facts['food_condition']
    if not condition.get('available') or not condition.get('observed_food_nutrition'): return None
    # Cold grain is optional; real short-lived meat/meals or exposed vulnerable food establish the need.
    rows=condition.get('stacks') or []
    if not any(r.get('exposed') or r.get('rot_days') is not None and r['rot_days']<8 for r in rows): return None
    from colony_director import freezer_blueprint
    layout=freezer_blueprint(wall_stuff='WoodLog')
    requirements=architect.estimated_stuff_cost(layout,dev['building_catalog'])
    if not requirements or any(k.startswith('unknown_') for k in requirements): return None
    power_requirements={}
    generator_defs={k for k,v in index.items() if v.get('is_power_generator')}
    has_generator=any(b.get('def_name') in generator_defs or isinstance(b.get('power_output'),(int,float)) and b['power_output']>0
        for b in production.get('buildings') or [])
    if not has_generator and 'WoodFiredGenerator' in index:
        power_requirements=architect.effective_building_cost(index['WoodFiredGenerator'])
        for name,count in power_requirements.items():requirements[name]=requirements.get(name,0)+count
    return {'kind':'freezer','requirements':requirements,'layout':layout,
        'power_requirements':power_requirements,
        'research':['Electricity'], 'need_actual_power':True, 'completion':'unverified',
        'reason':'Observed food deadline/exposure; freezer competes with immediate care and covered hauling',
        'food_condition':{k:condition.get(k) for k in ('at_risk_nutrition','critical_stack_ids')}}


def shell_plans(snapshot,map_state):
    dev=snapshot.get('development') or {}; record=map_state.get('known_starter_base') or {}
    if record.get('map_id')!=snapshot['map']['id'] or not isinstance(record.get('origin'),dict) or not isinstance(record.get('layout'),dict): return {}
    origin=record['origin']; rows=record['layout'].get('buildings') or []
    if type(origin.get('x')) is not int or type(origin.get('z')) is not int: return {}
    builders=[p for p in snapshot.get('colonists') or [] if not any(p.get(k) for k in ('dead','downed','in_mental_state','is_drafted'))
        and not ((p.get('skills') or {}).get('Construction') or {}).get('disabled')
        and not (p.get('work_priorities',{}).get('Construction') or {}).get('disabled')
        and p.get('current_job') not in {'TendPatient','Rescue','FeedPatient','Ingest'}
        and (p.get('current_job')!='DoBill' or p.get('current_job_is_care') is False)]
    if not builders or not isinstance(dev.get('buildings'),list) or not isinstance(dev.get('construction_projects'),list): return {}
    occupied={(r.get('def_name') or r.get('def'),(r.get('position') or {}).get('x'),(r.get('position') or {}).get('z'))
        for r in dev['buildings']+dev['construction_projects']}
    counts=dev.get('item_counts') or {}; index=architect.catalog_index(dev.get('building_catalog') or []); plans={}
    for row in rows:
        name=row.get('def_name'); x=origin['x']+int(row.get('rel_x') or 0);z=origin['z']+int(row.get('rel_z') or 0)
        if name not in {'Wall','Door'} or (name,x,z) in occupied or name not in index: continue
        costs=architect.effective_building_cost(index[name],row.get('stuff_def_name') or '')
        if not costs or any(int(counts.get(k) or 0)<v for k,v in costs.items()):continue
        plans[f'{name}:{x}:{z}']={'def_name':name,'position':{'x':x,'z':z},'costs':costs,
            'layout':architect.blueprint([{**row,'rel_x':0,'rel_z':0}],1,1), 'completion':'unverified'}
    return plans


def prepare(snapshot,map_state):
    dev=snapshot.setdefault('development',{}); tick=int(snapshot.get('game',{}).get('tick') or 0)
    history=map_state.setdefault('stewardship_history',{})
    history={k:v for k,v in history.items() if isinstance(v,dict) and v.get('map_id')==snapshot['map']['id'] and retry.recent(v,tick,30000)}
    map_state['stewardship_history']=history
    selected=map_state.get('preservation_goal') or {}
    if selected.get('map_id')==snapshot['map']['id']:
        requirements=copy.deepcopy(selected.get('requirements') or {})
        if selected.get('placed'):requirements=copy.deepcopy(selected.get('power_requirements') or {})
        catalog=architect.catalog_index(dev.get('building_catalog') or [])
        power_defs={k for k,v in catalog.items() if v.get('is_power_generator')}
        if any((b.get('def_name') or b.get('def')) in power_defs for b in ((dev.get('production') or {}).get('buildings') or [])+(dev.get('construction_projects') or [])):
            for name,count in (selected.get('power_requirements') or {}).items():requirements[name]=max(0,requirements.get(name,0)-count)
        dev['preservation_requirements']=requirements
        dev['preservation_goal']=selected
    else:dev['preservation_requirements']={}
    plans={'stewardship_crop_budget':sow_plans(snapshot), 'stewardship_shell_repair':shell_plans(snapshot,map_state)}
    goal=preservation_goal(snapshot)
    if goal and not selected:plans['stewardship_preservation_goal']={'freezer':goal}
    for action,rows in plans.items():
        plans[action]={k:v for k,v in rows.items() if action+':'+k not in history}
    dev['stewardship']={'available':True,'plans':plans,'food_condition':crops.food_planning_facts(snapshot)['food_condition']}
    return [a for a,p in plans.items() if p]


def choose(agent,state,action,snapshot):
    plans=snapshot['development'].get('stewardship',{}).get('plans',{}).get(action) or {}
    need=crops.food_planning_facts(snapshot)
    facts={k:need.get(k) for k in ('human_demand_per_day','stored_food_days','potential_crop_nutrition_per_day',
        'first_harvest_days_estimate','immediate_food_gap')}
    facts['at_risk_nutrition']=(need.get('food_condition') or {}).get('at_risk_nutrition')
    criteria={k: ('pause future sowing' if p.get('allow_sow') is False else 'resume future sowing')+f" {p['plant_def']}; {p['reason']}; keep {p.get('standing_plants')} plants"
        if action=='stewardship_crop_budget' else f"{p.get('kind') or p.get('def_name')}; costs {p.get('requirements') or p.get('costs')}; not completed" for k,p in plans.items()}
    criteria['defer']='Keep current work and policy; deterioration/exposure or missing service may continue'
    key,raw=ask_laya_choice(agent,{'decision_facts':{'food':facts,'goal_requirements':snapshot['development'].get('preservation_requirements')},
        'option_effects':{k:assess(action,snapshot) for k in criteria}},'stewardship_target',DESCRIPTIONS[action],criteria,detailed=True)
    return {'key':key,'shown':list(plans),'plan':copy.deepcopy(plans.get(key))},raw


def execute(client,snapshot,map_state,action,selected):
    key=selected.get('key'); tick=int(snapshot['game'].get('tick') or 0);map_id=snapshot['map']['id']
    plans=snapshot['development'].get('stewardship',{}).get('plans',{}).get(action) or {}
    plan=plans.get(key)
    def remember(keys,seconds=120):
        for k in keys:map_state.setdefault('stewardship_history',{})[action+':'+k]={**retry.failure_record(tick,seconds),'map_id':map_id}
    if key=='defer':remember(selected.get('shown') or []);return {'applied':False,'reason':'laya_deferred_stewardship'}
    if not plan or plan!=selected.get('plan'):return {'applied':False,'reason':'stewardship_selection_changed'}
    if action=='stewardship_crop_budget':
        result=client.post('/api/v1/map/zone/growing/sowing',body={'map_id':map_id,'zone_id':plan['zone_id'],
            'allow_sow':plan['allow_sow'],'expected_allow_sow':plan['expected_allow_sow'],'expected_plant_def':plan['plant_def']})
        applied=isinstance(result,dict) and (result.get('success') is True or result.get('applied') is True)
        remember([key],120 if applied else 30)
        return {'applied':applied,'response':result,'standing_plants_removed':False,'harvest_delivery':'unverified'}
    if action=='stewardship_preservation_goal':
        map_state['preservation_goal']={**copy.deepcopy(plan),'map_id':map_id,'selected_tick':tick}
        return {'applied':True,'goal_selected':True,'completion':'unverified','requirements':plan['requirements']}
    from colony_director import post_observed_blueprint
    result=post_observed_blueprint(client,map_id,plan['position'],plan['layout'])
    remember([key],120 if result.get('applied') else 30)
    return {**result,'construction_completion':'unverified','warm_enclosure':'unverified'}


def assess(action,snapshot):
    return {'benefit':DESCRIPTIONS[action], 'cost':'Finite materials and real worker time or a reversible sowing policy',
        'risk':'Climate, routes, processing/hauling backlog and power may prevent delivery',
        'inaction':'Existing crops/work/policies continue; missing protection persists',
        'uncertainty':'No goal/blueprint/policy proves completion, cold temperature, delivered food or income'}


def summary(snapshot):
    context=snapshot.get('development',{}).get('stewardship') or {}
    condition=context.get('food_condition') or {}
    return {'vulnerable_food':{'count':len(condition.get('critical_stack_ids') or []),
        'at_risk_nutrition':condition.get('at_risk_nutrition')},
        'missing_shelter_shell':{'count':len((context.get('plans') or {}).get('stewardship_shell_repair') or {})}}
