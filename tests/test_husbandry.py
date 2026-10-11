"""Husbandry sequences: shared rations, season changes, safe plans and fresh decisions."""
import copy
import json
from collections import deque
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import colony_husbandry as husbandry
import colony_architect as architect
import colony_sustenance as sustenance
import colony_capabilities as caps
import colony_director as director
from tests.test_capabilities import snapshot as farm_snapshot, crop, growing_site


def husbandry_context(count=2, stock=100):
    animals=[dict(id=i+1,species="Pig", recovery_nutrition_per_day=.8,
        adult_baseline_nutrition_per_day=.8,newborn_baseline_nutrition_per_day=.2,
        pregnant=False,comfortable_min=-6,comfortable_max=34,needs_pen=True) for i in range(count)]
    return dict(available=True,observed_tick=60000,animals=animals,human_nutrition=30,
        human_reserve_nutrition=1.8,human_demand_nutrition_day=1.6,hay_unit_nutrition=.05,
        feed_pools=[dict(thing_id=20,def_name="Hay",nutrition=stock,human_edible=False,
            compatible_ids=[a["id"] for a in animals],accessible_ids=[a["id"] for a in animals])],
        seasonal_means=[dict(offset_days=0,duration_days=5,mean_c=15)])


def livestock_snapshot(context):
    return {"development":{"sustenance":{"husbandry":context}}}


def barn_catalog():
    rows=[]
    for name,stuff,cost in (("Wall",5,None),("Door",25,None),("Fence",1,None),
            ("FenceGate",25,None),("PenMarker",30,None),("AnimalFlap",25,None),
            ("AnimalSleepingSpot",0,None),("Campfire",0,("WoodLog",20)),
            ("Heater",0,("Steel",50)),("PassiveCooler",0,("WoodLog",50)),
            ("Cooler",0,("Steel",90)),("StrawMatting",0,("Hay",2))):
        rows.append(dict(def_name=name,available_now=True,size_x=1,size_z=1,cost_stuff_count=stuff,
            allowed_stuff_defs=["Cloth","Leather_Plain"] if name=="AnimalFlap" else ["WoodLog","BlocksGranite"] if stuff else [],
            cost_list=[dict(thing_def=cost[0],count=cost[1])] if cost else []))
    return rows


def barn_context(hay=100):
    native=husbandry_context(3,hay)
    return dict(material="WoodLog",climate="cold",building_catalog=barn_catalog(),
        item_counts={"WoodLog":3000,"BlocksGranite":3000,"Steel":1000,"Cloth":500,"Hay":int(hay/.05)},
        animals=native["animals"],sustenance={"husbandry":native})


class RationAndSeasonSequences(unittest.TestCase):
    def test_shared_stack_and_incompatible_species_are_not_counted_twice(self):
        c=husbandry_context(2,10)
        c["feed_pools"].append(copy.deepcopy(c["feed_pools"][0]))
        self.assertAlmostEqual(husbandry.feed_cover_days(c),6.25,places=2)
        self.assertEqual(husbandry.planning_context(livestock_snapshot(c))["stored_compatible_nutrition"],10)
        c["feed_pools"][0]["compatible_ids"]=[1]
        c["feed_pools"][0]["accessible_ids"]=[1]
        self.assertEqual(husbandry.feed_cover_days(c),0)

    def test_stack_behind_a_gate_is_stock_not_current_feed(self):
        c=husbandry_context(1,8); c["feed_pools"][0]["accessible_ids"]=[]
        p=husbandry.planning_context(livestock_snapshot(c))
        self.assertEqual(p["accessible_cover_days"],0)
        self.assertAlmostEqual(p["stock_cover_days_if_delivered"],10,places=2)

    def test_reserve_deficit_uses_compatibility_and_each_stack_once(self):
        c=husbandry_context(2,20)
        c['feed_pools'][0].update(compatible_ids=[1],accessible_ids=[1])
        c['feed_pools'].append(copy.deepcopy(c['feed_pools'][0]))
        p=husbandry.planning_context(livestock_snapshot(c))
        self.assertEqual(p['reserve_target_nutrition'],30)
        self.assertEqual(p['reserve_deficit_nutrition'],15)

    def test_reserve_grows_before_winter_arrives(self):
        c=husbandry_context(1,20)
        self.assertFalse(husbandry.planning_context(livestock_snapshot(c))["fodder_gap"])
        c["seasonal_means"]=[dict(offset_days=0,duration_days=5,mean_c=8),
            dict(offset_days=5,duration_days=15,mean_c=-5),
            dict(offset_days=20,duration_days=15,mean_c=-15),dict(offset_days=35,duration_days=5,mean_c=8)]
        p=husbandry.planning_context(livestock_snapshot(c))
        self.assertEqual(p["reserve_horizon_days"],35)
        self.assertEqual(p["reserve_target_nutrition"],35)
        self.assertTrue(p["fodder_gap"])

    def test_pregnancy_reopens_a_previously_sufficient_ration(self):
        c=husbandry_context(1,30)
        before=husbandry.planning_context(livestock_snapshot(c))
        c["animals"][0].update(pregnant=True,birth_days_nominal=2,litter_max_estimate=4)
        after=husbandry.planning_context(livestock_snapshot(c))
        self.assertFalse(before["fodder_gap"]); self.assertTrue(after["fodder_gap"])
        self.assertGreater(after["reserve_target_nutrition"],before["reserve_target_nutrition"])
        self.assertEqual(after["animals"],1) # Estimated births are not new residents.

    def test_post_winter_growth_delay_is_not_free_food_on_the_first_warm_day(self):
        c=husbandry_context(1,20)
        c.update(post_climate_feed_growth_days_normal=12.92,seasonal_means=[
            dict(offset_days=0,duration_days=5,mean_c=8),dict(offset_days=5,duration_days=30,mean_c=-10),
            dict(offset_days=35,duration_days=5,mean_c=8)])
        plan=husbandry.planning_context(livestock_snapshot(c))
        self.assertAlmostEqual(plan['reserve_horizon_days'],47.92)
        self.assertTrue(plan['fodder_gap'])

    def test_young_starving_animals_keep_an_adult_allowance(self):
        c=husbandry_context(1,1); c["animals"][0]["recovery_nutrition_per_day"]=.1
        c["animals"][0]["current_nutrition_per_day"]=.01
        p=husbandry.planning_context(livestock_snapshot(c))
        self.assertEqual(p["adult_allowance_nutrition_day"],.8)
        self.assertEqual(p["reserve_target_nutrition"],15)

    def test_human_meals_cannot_supply_a_winter_herd_at_humans_expense(self):
        c=husbandry_context(1,46.8); c.update(human_nutrition=46.8,human_reserve_nutrition=5.4,human_demand_nutrition_day=4.8)
        c["feed_pools"][0].update(def_name="MealSimple",human_edible=True)
        p=husbandry.planning_context(livestock_snapshot(c))
        self.assertEqual(p["human_horizon_reserve_nutrition"],72)
        self.assertTrue(p["fodder_gap"])
        self.assertLess(p["stock_cover_days_if_delivered"],9)

    def test_spoilage_and_grazing_do_not_become_winter_stock(self):
        c=husbandry_context(1,100)
        c["feed_pools"][0]["ticks_until_rot"]=60000
        c["pasture_nutrition_per_day"]=100
        p=husbandry.planning_context(livestock_snapshot(c))
        self.assertLessEqual(p["stock_cover_days_if_delivered"],1)
        self.assertTrue(p["fodder_gap"])

    def test_missing_native_read_or_growth_demand_is_unknown(self):
        self.assertFalse(husbandry.planning_context({})["available"])
        c=husbandry_context(); c["animals"][0].pop("adult_baseline_nutrition_per_day")
        self.assertFalse(husbandry.planning_context(livestock_snapshot(c))["available"])


class FeedPlantingSequences(unittest.TestCase):
    def farm(self):
        s=farm_snapshot(); s["map"]["resources"]["nutrition"]=30
        s["development"]["sustenance"]={"husbandry":husbandry_context(2,0)}
        hay={**crop("Plant_Haygrass"),"human_edible_product":False,"harvest_yield":18,
            "harvested_thing":"Hay","compatible_product_animal_ids":[1,2],"grazing_animal_ids":[1,2],
            "live_plant_nutrition":.2,"calendar_days_to_harvest_estimate":12.92,"outdoor_warm_days_estimate":20,"category":"feed"}
        rice={**crop(),"compatible_product_animal_ids":[1,2],"grazing_animal_ids":[1,2],"live_plant_nutrition":.2}
        s["development"]["plant_catalog"]={"plants":[hay,rice],"growers":[
            growing_site(plant="Plant_Rice",options=[rice,hay],pen_ids=[]),
            growing_site(kind="new_ground",options=[rice,hay],pen_ids=[])]}
        return s,hay

    def test_new_fodder_field_keeps_the_existing_human_food_field(self):
        s,hay=self.farm()
        self.assertEqual(caps.crop_sites(s,False),{})
        option=next(iter(caps.crop_sites(s,True).values()))["crop_options"][hay["def_name"]]
        self.assertEqual(option["category"],"stored_animal_feed")
        self.assertAlmostEqual(option["feed_planning"]["potential_nutrition"],8.1)
        self.assertEqual(option["feed_planning"]["delivered_nutrition"],0)

    def test_fodder_acreage_is_a_lower_bound_until_sown_harvested_and_delivered(self):
        s,hay=self.farm()
        plan=next(iter(caps.crop_sites(s,True).values()))['crop_options'][hay['def_name']]['feed_planning']
        self.assertEqual(plan['reserve_deficit_nutrition'],30)
        self.assertEqual(plan['harvest_cells_lower_bound'],34) # .9 nutrition per mature cell.
        self.assertEqual(plan['delivered_nutrition'],0)
        hay['compatible_product_animal_ids']=[1]
        s['development']['plant_catalog']['plants'][0]=hay
        s['development']['plant_catalog']['growers'][1]['options'][1]=hay
        limited=next(iter(caps.crop_sites(s,True).values()))['crop_options'][hay['def_name']]['feed_planning']
        self.assertIsNone(limited['harvest_cells_lower_bound']) # Cannot cover the other diet.

    def test_human_starvation_does_not_create_an_unfunded_fodder_detour(self):
        s,hay=self.farm(); s["colonists"][0]["hunger"]=0
        crops=next(iter(caps.crop_sites(s,True).values()))["crop_options"]
        self.assertNotIn(hay["def_name"],crops)

    def test_inside_pen_planting_is_grazing_not_a_promised_hay_harvest(self):
        s,hay=self.farm(); s["development"]["plant_catalog"]["growers"][1]["pen_ids"]=[5]
        option=next(iter(caps.crop_sites(s,True).values()))["crop_options"][hay["def_name"]]
        self.assertEqual(option["category"],"animal_pasture")
        self.assertIsNone(option["feed_planning"]["potential_nutrition"])
        self.assertIsNone(option["feed_planning"]["harvest_days"])
        self.assertTrue(option["feed_planning"]["grazing_prevents_assured_harvest"])

    def test_no_feasible_sowing_or_recovered_reserve_does_not_add_hay(self):
        s,hay=self.farm()
        s["development"]["plant_catalog"]["growers"][1]["options"][1]["safe_sowing_now"]=False
        crops=next(iter(caps.crop_sites(s,True).values()))["crop_options"]
        self.assertNotIn(hay["def_name"],crops)


class ShelterSequences(unittest.TestCase):
    def test_cloth_flap_and_indoor_pen_are_real_alternatives(self):
        c=barn_context(); plans=architect.animal_shelter_variants(c)
        self.assertTrue(any(p["layout"]["mode"]=="indoor_pen" for p in plans.values()))
        self.assertTrue(any(p["layout"]["mode"]=="barn_run" for p in plans.values()))
        for p in plans.values():
            flaps=[r for r in p["layout"]["buildings"] if r["def_name"]=="AnimalFlap"]
            self.assertTrue(all(r["stuff_def_name"]=="Cloth" for r in flaps))
            self.assertEqual(p["layout"]["animal_places"],3)
        c["item_counts"]["Cloth"]=0
        self.assertTrue(all(p["layout"]["mode"]=="indoor_pen" for p in architect.animal_shelter_variants(c).values()))

    def test_disjoint_temperature_limits_require_separate_cohorts(self):
        c=barn_context(); c['animals']=[dict(id=1,needs_pen=True,comfortable_min=-50,comfortable_max=15),
            dict(id=2,needs_pen=True,comfortable_min=20,comfortable_max=45)]
        plans=architect.animal_shelter_variants(c)
        self.assertTrue(plans)
        self.assertEqual({tuple(p['housing_cohort']) for p in plans.values()},{(1,),(2,)})

    def test_roamer_can_pass_internal_flap_but_not_escape_compound(self):
        layout=architect.animal_shelter_layout("WoodLog",18,mode="barn_run",flap_stuff="Cloth")
        blocking={(r["rel_x"],r["rel_z"]) for r in layout["buildings"] if r["def_name"] in {"Wall","Door","Fence","FenceGate"}}
        spots=[r for r in layout["buildings"] if r["def_name"]=="AnimalSleepingSpot"]
        seen={(spots[0]["rel_x"],spots[0]["rel_z"])}; queue=deque(seen)
        while queue:
            x,z=queue.popleft()
            self.assertTrue(0<x<layout["width"]-1 and 0<z<layout["height"]-1)
            for cell in ((x-1,z),(x+1,z),(x,z-1),(x,z+1)):
                if cell not in blocking and cell not in seen: seen.add(cell);queue.append(cell)
        marker=next(r for r in layout["buildings"] if r["def_name"]=="PenMarker")
        self.assertIn((marker["rel_x"],marker["rel_z"]),seen)
        self.assertEqual(len(spots),18)
        self.assertEqual(architect.layout_anchor_conflicts(layout),[])

    def test_straw_does_not_spend_a_short_feed_reserve(self):
        rich=architect.animal_shelter_variants(barn_context(100))
        self.assertTrue(any(p["layout"]["floors"] for p in rich.values()))
        scarce=architect.animal_shelter_variants(barn_context(10))
        self.assertTrue(scarce)
        self.assertTrue(all(not p["layout"]["floors"] for p in scarce.values()))

    def test_pet_housing_and_hot_climate_use_suitable_structures(self):
        c=barn_context(); c["animals"]=[dict(id=1,requires_pen=False,comfortable_min=-25,comfortable_max=40)]
        c["climate"]="hot"
        plans=architect.animal_shelter_variants(c)
        self.assertTrue(any("Cooler" in [r["def_name"] for r in p["layout"]["buildings"]] for p in plans.values()))
        for p in plans.values():
            self.assertNotIn("PenMarker",[r["def_name"] for r in p["layout"]["buildings"]])
            self.assertEqual(architect.layout_anchor_conflicts(p["layout"]),[])

    def test_legacy_outdoor_spot_does_not_place_anything(self):
        client=Mock()
        result=director.execute_action(client,{"game":{"tick":60000},"map":{"id":0},"development":{}},
            {"anchor":{"x":50,"z":50},"issued":{}},"build_animal_spots",{})
        self.assertFalse(result["applied"]); client.post.assert_not_called()

    def test_partial_barn_keeps_exact_intent_for_observed_repair(self):
        plans=architect.animal_shelter_variants(barn_context())
        plan=next(p for p in plans.values() if not p['layout']['floors'])
        plan={**plan,'material':'WoodLog'}
        snapshot={'game':{'tick':60000},'map':{'id':0},'development':{}}
        memory={'anchor':{'x':50,'z':50},'issued':{}}
        details={'animal_barn_options':{'plans':{'chosen':plan}},'animal_barn_plan':'chosen'}
        def partial(client,map_id,origin,layout):
            self.assertEqual(memory['architecture_projects'][0]['layout'],plan['layout'])
            return {'applied':False,'reason':'Only part of the paid project was observed'}
        with patch.object(director,'find_clear_layout_site',return_value={'x':40,'z':40}), \
             patch.object(director,'post_observed_blueprint',side_effect=partial):
            result=director.execute_action(Mock(),snapshot,memory,'build_animal_barn',details)
        self.assertFalse(result['applied'])
        self.assertNotIn('animal_barn',memory['issued'])
        self.assertIn('unverified',result['completion'])
        first=plan['layout']['buildings'][0]
        observed={'id':80,'def':first['def_name'],'stuff_def_name':first.get('stuff_def_name'),
            'rotation':first.get('rotation',0),'position':{'x':40+first['rel_x'],'z':40+first['rel_z']}}
        repairs=architect.reconcile_projects({'buildings':[observed]},memory,0,62500,lambda *_:{})
        self.assertEqual(len(repairs),1)
        pending=next(iter(repairs.values()))
        self.assertEqual(pending['project']['origin'],{'x':40,'z':40})
        self.assertEqual(len(pending['layout']['buildings']),len(plan['layout']['buildings'])-1)
        self.assertFalse(pending['project']['complete_plan_placed'])

    def test_new_feed_shortage_blocks_straw_before_any_placement(self):
        c=barn_context(100)
        plan=next(p for p in architect.animal_shelter_variants(c).values() if p['layout']['floors'])
        plan={**plan,'material':'WoodLog'}
        snapshot={'game':{'tick':60000},'map':{'id':0},'development':{'building_catalog':barn_catalog()}}
        memory={'anchor':{'x':50,'z':50},'issued':{}}
        client=Mock(); client.get.return_value={'husbandry':husbandry_context(3,0)}
        with patch.object(director,'find_clear_layout_site') as placement:
            result=director.execute_action(client,snapshot,memory,'build_animal_barn',
                {'animal_barn_options':{'plans':{'chosen':plan}},'animal_barn_plan':'chosen'})
        self.assertFalse(result['applied'])
        self.assertEqual(result['reason'],'straw_would_consume_required_feed_or_context_unavailable')
        placement.assert_not_called(); client.post.assert_not_called()
        self.assertNotIn('architecture_projects',memory)

    def test_comfort_intersection_uses_the_most_vulnerable_species(self):
        self.assertEqual(husbandry.comfort_intersection([dict(comfortable_min=-50,comfortable_max=45),
            dict(comfortable_min=0,comfortable_max=30)]),[0,30])

    def test_patient_in_a_cold_bed_can_move_to_a_measured_warm_bed(self):
        animal=dict(id=1,name='Patient',downed=True,hunger=.4,health=1,in_bed=True,current_bed_id=10,
            position=dict(x=50,z=50))
        native=husbandry_context(1); native['animals'][0].update(temperature=-22)
        native['animal_beds']=[dict(id=10,temperature=-22,roofed=False,suitable_ids=[1],occupied_ids=[1]),
            dict(id=11,temperature=21,roofed=True,suitable_ids=[1],occupied_ids=[],thermal_benefit_ids=[1])]
        s=dict(animals=[animal],colonists=[dict(id=3,name='Rescuer',position=dict(x=50,z=51))],
            development=dict(buildings=[dict(id=10,def_name='AnimalSleepingSpot',**{'def':'AnimalSleepingSpot'},position=dict(x=50,z=50)),
                dict(id=11,**{'def':'AnimalSleepingSpot'},position=dict(x=51,z=50))],sustenance=dict(husbandry=native)))
        self.assertEqual(director.animal_rescue_options(s)[0]['bed_id'],11)
        native['animal_beds'][1]['occupied_ids']=[8]
        self.assertEqual(director.animal_rescue_options(s),[])
        native['animal_beds'][1]['occupied_ids']=[]
        native['animal_beds'][1]['temperature']=-30
        self.assertEqual(director.animal_rescue_options(s),[])

    def test_missing_housing_read_cannot_authorize_an_outdoor_rescue(self):
        s={'animals':[dict(id=1,downed=True,health=1,hunger=0,position=dict(x=50,z=50))],
            'colonists':[dict(id=3,position=dict(x=50,z=51))], 'development':{'buildings':[
                dict(id=10,**{'def':'AnimalSleepingSpot'},position=dict(x=51,z=50))]}}
        self.assertEqual(director.animal_rescue_options(s),[])
        s['development']['sustenance']={'husbandry':{'available':False,'reason':'read failed'}}
        self.assertEqual(director.animal_rescue_options(s),[])


class BoundedHusbandryDecisions(unittest.TestCase):
    def agent(self):
        from tokenizers import Tokenizer
        paths=list((Path.home()/'.cache/huggingface/hub/models--convaiinnovations--laya/snapshots').glob('*/tokenizer/tokenizer.json'))
        if not paths:self.skipTest('cached tokenizer unavailable')
        tokenizer=Tokenizer.from_file(str(paths[0]))
        class Agent:
            cfg={'max_len':512,'head_max_len':192}
            def __init__(self):self.seen=[]
            def tok(self,text,**kwargs):return {'input_ids':tokenizer.encode(text,add_special_tokens=False).ids}
            def predict(self,state,questions):
                self.seen.append(copy.deepcopy(state))
                key,q=next(iter(questions.items()))
                preferred='stored_animal_feed' if key.startswith('crop_purpose') else None
                return {'answers':{key:{'choice':preferred if preferred in q['criteria'] else next(k for k in q['criteria'] if k!='defer')}}}
        return Agent()

    def test_measured_warm_spot_keeps_thermal_facts_and_rations(self):
        context={'available':True,'husbandry':husbandry_context(),
            'human_food':[dict(fresh_eligible_nutrition=30)],'options':[
                dict(key='warmspot:4:21:21',kind='warmspot',target_id=4,value='21,21',label='Roofed animal spot',
                    facts=dict(source_c=-22,destination_c=21,hypothermia=.88,heatstroke=None,downed=True,
                        preventive=False,work=0,materials=0,rescue_pending=True))]}
        s={'map':{'id':0},'game':{'tick':60000},'development':{'sustenance':context}}
        agent=self.agent(); sustenance.prepare(s,{})
        chosen,_=sustenance.choose(agent,{},'sustenance_animal_welfare',s)
        self.assertEqual(chosen['sustenance_policy'],'warmspot:4:21:21')
        comparisons=[v['facts']['comparison'] for v in agent.seen if 'comparison' in v.get('facts',{})]
        self.assertTrue(comparisons)
        for v in agent.seen:self.assertLessEqual(len(agent.tok(json.dumps(v,ensure_ascii=False))['input_ids']),312)
        self.assertEqual(comparisons[-1]['options']['o0']['source_c'],-22)
        self.assertEqual(comparisons[-1]['shared']['human_nutrition'],30)

    def test_fodder_crop_packet_keeps_delay_yield_and_pen_grazing(self):
        s,hay=FeedPlantingSequences().farm()
        other={**hay,'def_name':'ModFodder','label':'Other legal feed crop','harvest_yield':10}
        s['development']['plant_catalog']['plants'].append(other)
        s['development']['plant_catalog']['growers'][1]['options'].append(other)
        caps.prepare(s,{})
        agent=self.agent(); selected,_=caps.choose(agent,{},'create_growing_zone',s)
        self.assertEqual(selected['crop_type'],hay['def_name'])
        comparisons=[v['facts']['comparison'] for v in agent.seen if 'comparison' in v.get('facts',{})]
        self.assertTrue(comparisons)
        self.assertAlmostEqual(comparisons[-1]['options'][hay['def_name']]['feed_nutrition'],8.1)
        self.assertEqual(comparisons[-1]['options'][hay['def_name']]['feed_cells_needed'],34)
        for v in agent.seen:self.assertLessEqual(len(agent.tok(json.dumps(v,ensure_ascii=False))['input_ids']),312)

    def test_feed_and_thermal_purposes_fit_together_with_known_forecast(self):
        context={'available':True,'husbandry':husbandry_context(),
            'human_food':[dict(fresh_eligible_nutrition=30)],'options':[
                dict(key='warmspot:4:21:21',kind='warmspot',target_id=4,value='21,21',label='Roofed warm spot',
                    facts=dict(source_c=-22,destination_c=21,hypothermia=.88,heatstroke=None,downed=True,
                        preventive=False,work=0,materials=0,rescue_pending=True)),
                dict(key='penfeed:9:1:33:30:25',kind='penfeed',target_id=9,value='1,33,30,25,16',label='Finite feed delivery',
                    facts=dict(hungry_animals=2,min_food=0,malnutrition=.8,nutrition=.8,human_remaining=29.2,
                        human_minimum=1.8,delivery_pending=True))]}
        s={'map':{'id':0},'game':{'tick':60000},'development':{'sustenance':context}}
        agent=self.agent(); sustenance.prepare(s,{})
        selected,_=sustenance.choose(agent,{},'sustenance_animal_welfare',s)
        self.assertIn(selected['sustenance_policy'],[p['key'] for p in context['options']])
        for v in agent.seen:self.assertLessEqual(len(agent.tok(json.dumps(v,ensure_ascii=False))['input_ids']),312)


if __name__=='__main__':unittest.main()
