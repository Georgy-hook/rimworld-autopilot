"""Cached Laya on bounded recovery contracts. Offline: no RimWorld client or socket."""
import argparse,copy,json,os,sys
from pathlib import Path
os.environ.update(HF_HUB_OFFLINE='1',TOKENIZERS_PARALLELISM='false',LAYA_CPU_THREADS='4',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import colony_capabilities as crops
import colony_society as society
import colony_director as director
import colony_specialists as specialists
import rimworld_laya as bridge
from tests.test_onbum_survival_recovery import food_snapshot

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    agent=bridge.load_agent(bridge.DEFAULT_MODEL,'cuda'); records=[]
    for reverse in (False,True):
        s=food_snapshot()
        # Actual native catalog shape: initial planting, four stored days,
        # six-day rice versus twenty-day corn. Neither feeds today's patient.
        s['development']['plant_catalog']['growers']=s['development']['plant_catalog']['growers'][1:]
        s['development']['farm']['crop_types']=[]
        if reverse:s['development']['plant_catalog']['growers'][0]['options'].reverse()
        crops.prepare(s,{})
        selected,raw=crops.choose(agent,{},'create_growing_zone',s)
        records.append({'case':'first_harvest_before_slow_corn','reverse':reverse,'selected':selected,
            'expected':selected.get('crop_type')=='Plant_Rice','decision':raw})
        s=food_snapshot();s['map']['resources']['nutrition']=0;s['development']['sanitation_urgent']=True
        candidates=['harvest_local_plants','resilience_dispose_corpse','resilience_shelter','advance_doctrine_research','hold_survival']
        candidates=director.focus_contamination_choices(s,director.focus_imminent_food_choices(s,candidates))
        # Native opportunity/actor details are deliberately required for a live
        # order; this check only proves the two emergency families stay visible.
        records.append({'case':'food_and_rot_options','reverse':reverse,'options':candidates,
            'expected':{'harvest_local_plants','resilience_dispose_corpse'}<=set(candidates)})
        person={'pawn_id':1,'name':'Injured worker','thoughts':[],'conditions':[], 'needs':[{'def_name':'Mood','level':.4}],
            'drugs':{'capacities':{'consciousness':.53,'moving':.15,'manipulation':.48},'entries':[
                {'drug':'SmokeleafJoint','capacity_risk':True,'allowed_joy':True,'capacity_effects':[{'capacity':'Consciousness','offset':-.3}]}]}}
        row={'kind':'drug_entry','pawn_id':1,'value':'SmokeleafJoint|disabled','native':True,'person':person,
            'label':'Disable recreational smokeleaf for injured worker','effects':{'benefit':'Remove future recreational sedation and appetite increase',
                'risk':'Current high will wear off with time. No addiction/dependency detected.',
                'cost':'Lose optional drug mood benefit; keep food/care and other recreation',
                'inaction':'Consciousness .53/moving .15, continued recreational permission may cause further incapacity',
                'uncertainty':'Policy does not cure existing injuries or hunger'}}
        s={'map':{'id':0},'development':{'society':{'options':{'society_drug_entry':{'disable':row}}}}}
        selected,raw=society.choose(agent,{},'society_drug_entry',s)
        records.append({'case':'injured_sedation_policy','reverse':reverse,'selected':selected,
            'expected':selected.get('value')=='SmokeleafJoint|disabled','decision':raw})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'offline':True,'game_orders':0,'survival_not_proven':True,'records':records},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{k:r.get(k) for k in ('case','reverse','selected','expected')} for r in records]))
    return int(not all(r['expected'] for r in records))
if __name__=='__main__':raise SystemExit(main())
