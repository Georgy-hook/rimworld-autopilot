"""Cached Laya husbandry decisions over offline transport, with no game orders."""
import argparse
import copy
import json
import os
from pathlib import Path
import sys

os.environ.update(HF_HUB_OFFLINE='1',TOKENIZERS_PARALLELISM='false',LAYA_CPU_THREADS='4',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4')
REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO),str(REPO/'tests')]
import rimworld_laya as bridge
import colony_sustenance as sustenance
import colony_capabilities as caps
import colony_architect as architect
from tests.test_husbandry import husbandry_context,barn_context,FeedPlantingSequences


class OfflineTransport:
    def __init__(self,context):self.context=context;self.orders=[]
    def get(self,path,**kwargs):
        if path!='/api/v1/sustenance/context':raise AssertionError('Unexpected offline read')
        return copy.deepcopy(self.context)
    def post(self,path,**kwargs):
        if path!='/api/v1/sustenance/policy':raise AssertionError('Unexpected offline order')
        self.orders.append(dict(path=path,body=copy.deepcopy(kwargs['body'])))
        return dict(applied=True,reason='offline_ack_only',completion='native_execution_not_tested')


def scenarios(reverse=False):
    warming=dict(key='warmspot:4:21:21',kind='warmspot',target_id=4,value='21,21',
        label='Prepare free roofed animal spot at 21C for exposed patient',
        facts=dict(source_c=-22,destination_c=21,hypothermia=.88,heatstroke=None,downed=True,
            preventive=False,work=0,materials=0,rescue_pending=True,carrier_count=1))
    feed=dict(key='penfeed:9:1:33:30:25',kind='penfeed',target_id=9,value='1,33,30,25,16',
        label='Haul finite compatible feed into hungry connected pen',
        facts=dict(hungry_animals=2,min_food=0,malnutrition=.8,nutrition=.8,human_remaining=29.2,
            human_minimum=1.8,delivery_pending=True))
    preventive={**warming,'key':'warmspot:4:22:21','value':'22,21','label':'Prepare roofed animal sleeping place before downing',
        'facts':{**warming['facts'],'hypothermia':None,'downed':False,'preventive':True,'rescue_pending':False}}
    for name,plans in [('exposed_downed_animal',[warming]),('finite_feed_only',[feed]),
            ('feed_or_thermal_place',[feed,warming]),('preventive_animal_place',[preventive])]:
        native=husbandry_context(2,0)
        context=dict(available=True,husbandry=native,human_food=[dict(fresh_eligible_nutrition=30)],
            animals=[dict(id=4,food=.4,downed=True,temperature=-22,
                health=[dict(def_name='Hypothermia',stage_index=3,severity=.88,life_threatening=True)])],
            pens=[dict(id=9,enclosed=True,consumption_per_day=1.6,pasture_nutrition_per_day=0,stockpiled_nutrition=0)],
            options=copy.deepcopy(list(reversed(plans)) if reverse else plans))
        yield name,dict(game=dict(tick=60000),map=dict(id=0,resources=dict(nutrition=30,meals=20,food=20)),
            colonists=[dict(id=1,health=1,hunger=.9)],development=dict(sustenance=context))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    args=parser.parse_args()
    agent=bridge.load_agent(bridge.DEFAULT_MODEL,args.device)
    records=[]
    for reverse in (False,True):
        for name,s in scenarios(reverse):
            memory={}; context=s['development']['sustenance']; sustenance.prepare(s,memory)
            selected,decision=sustenance.choose(agent,{},'sustenance_animal_welfare',s)
            assert selected['sustenance_policy'] in {'defer',*[p['key'] for p in context['options']]}
            transport=OfflineTransport(context)
            result=sustenance.execute(transport,s,memory,'sustenance_animal_welfare',selected)
            records.append(dict(scenario=name,reverse=reverse,selected=selected,decision=decision,
                result=result,simulated_orders=transport.orders))
            print(json.dumps(dict(scenario=name,reverse=reverse,selected=selected)),flush=True)
        s,hay=FeedPlantingSequences().farm()
        other={**hay,'def_name':'ModFodder','label':'Other legal feed crop','harvest_yield':10,'calendar_days_to_harvest_estimate':9}
        s['development']['plant_catalog']['plants'].append(other)
        s['development']['plant_catalog']['growers'][1]['options'].append(other)
        if reverse:s['development']['plant_catalog']['growers'][1]['options'].reverse()
        caps.prepare(s,{})
        selected,decision=caps.choose(agent,{},'create_growing_zone',s)
        records.append(dict(scenario='human_food_or_separate_fodder_field',reverse=reverse,selected=selected,decision=decision,game_orders=0))
        print(json.dumps(dict(scenario='human_food_or_separate_fodder_field',reverse=reverse,selected=selected)),flush=True)
    output=dict(offline=True,game_mutations=0,model=bridge.DEFAULT_MODEL,device=args.device,records=records,
        native_execution_not_proven=True,survival_not_proven=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
