import copy
import unittest
from unittest.mock import Mock, patch
import colony_director as d
import colony_architect as a

class WoodMaterialTests(unittest.TestCase):
    def snapshot(self):
        project={'thing_id':20213,'def_name':'Wall','position':{'x':145,'z':128},'rotation':0,
                 'stuff_def_name':'WoodLog','materials_needed':[{'def_name':'WoodLog','required_count':4}], 'percent_complete':0}
        return {'map':{'id':1,'resources':{}},'game':{'tick':143482},'colonists':[{'id':1}],
            'development':{'item_counts':{'WoodLog':0,'Steel':776},'construction_projects':[project],
                'weather':{'temperature':37}, 'ideology':{'precepts':['TreeConnection']},
                'building_catalog':[{'def_name':'Wall','available_now':True,'cost_stuff_count':5,
                                    'allowed_stuff_defs':['Steel','WoodLog']}],
                'tree_options':{'SmashedStump':{'ids':[1],'count':1,'label':'stump','expected_yield':4},
                                'Plant_TreeDrago':{'ids':[2],'count':1,'label':'living tree','expected_yield':24}}}}
    def test_nonstructural_construction_still_gets_wood_supply(self):
        s=self.snapshot();s['development']['construction_projects'][0].update(def_name='ButcherTable')
        s['development']['construction_projects'][0]['materials_needed'][0]['required_count']=25
        self.assertEqual(25,d.wood_supply_demand(s))
        s['development'].update(building_counts={},zones=[],forbidden=[],current_research={'name':'none'},
            plants=[{'thing_id':100,'def_name':'Plant_TreeOak','harvested_thing_def':'WoodLog','harvestable_now':True,
                     'harvest_yield':30,'position':{'x':10,'z':10}}])
        s['colonists'][0].update(name='Cutter',health=1,position={'x':10,'z':10},
            work_priorities={'PlantCutting':{'priority':1}})
        s['animals']=[];s['wild_animals']=[];s['combat']={}
        choices,details=d.candidate_actions(None,s,{'anchor':{'x':10,'z':10},'issued':{}})
        self.assertIn('harvest_nearby_trees',choices)
        self.assertEqual(25,details['tree_options']['Plant_TreeOak']['wood_demand'])

    def test_species_criterion_shows_actual_small_batch_not_entire_population(self):
        s=self.snapshot();s['development']['tree_options']['Plant_TreeDrago'].update(count=19,expected_yield=252,
            planned_batch_count=1,planned_batch_yield=14,wood_demand=4)
        q=d.subchoice_questions_for_action('harvest_nearby_trees',s)
        criterion=q['tree_type']['criteria']['Plant_TreeDrago']
        self.assertTrue(criterion.startswith('Mark 1 for ~14 wood; demand 4'))
        self.assertIn('19 total available',criterion)

    def test_leaf_defer_skips_worker(self):
        s=self.snapshot()
        def ask(agent,state,key,instructions,criteria,**kwargs):
            choice='defer' if key=='tree_type' else next(iter(criteria))
            return choice, {'answers':{key:{'choice':choice}}}
        with patch.object(d,'ask_laya_choice',side_effect=ask) as ask_mock, patch.object(d,'foraging_worker_criteria',return_value={'1':'worker'}):
            result=d.choose_action(type('Agent',(),{'cfg':{},'tok':None})(),s,['harvest_nearby_trees'])
        self.assertEqual('defer',result['tree_type'])
        self.assertNotIn('tree_worker',[call.args[2] for call in ask_mock.call_args_list])

    def test_wall_clock_floor_and_native_severe_stage(self):
        s=self.snapshot();m={'anchor':{'x':0,'z':0}}
        with patch('colony_retry.time.time',return_value=1000):
            d.execute_action(Mock(),s,m,'harvest_nearby_trees',{'tree_type':'defer'})
        s['game']['tick']+=30001
        with patch('colony_retry.time.time',return_value=1100):self.assertTrue(d.wood_defer_active(s,m))
        with patch('colony_retry.time.time',return_value=1121):self.assertFalse(d.wood_defer_active(s,m))
        s['colonists'][0]['health_conditions']=[{'def_name':'Hypothermia','severity':.2,'cur_stage_index':3}]
        with patch('colony_retry.time.time',return_value=1100):self.assertFalse(d.wood_defer_active(s,m))

    def test_exact_gap_stump_and_affordable_steel(self):
        s=self.snapshot();s['development']['structural_material_options']=a.structural_material_repair_options(s['development'])
        f=d.wood_choice_facts(s)
        self.assertEqual((0,4,4),(f['wood'],f['shell_wood_required'],f['shell_wood_gap']))
        self.assertEqual(['20213|Steel'],f['replacement_choices'])
        self.assertNotIn('TreeConnection',str(f['cut_precepts']))
        self.assertEqual([1],d.wood_batch_ids([1,2],{1:{'harvest_yield':4},2:{'harvest_yield':24}}, {'x':0,'z':0},4))
    def test_eight_unchanged_cycles_backoff_jobs_and_tick_drift(self):
        s=self.snapshot();m={'wood_choice_defer':{'tick':143482,'signature':d.wood_defer_signature(s)}}
        for i in range(8):
            s['game']['tick']=143482+i*1000;s['colonists'][0]['job']='Job'+str(i)
            s['development']['weather']['temperature']=37+i/10
            s['development']['tree_options']['Plant_TreeDrago']['expected_yield']=248+i
            s['development']['tree_options']['SmashedStump']['expected_yield']=4
            self.assertTrue(d.wood_defer_active(s,m))
            self.assertTrue(a.structural_material_repair_options(s['development']))
        s['game']['tick']=173482;self.assertFalse(d.wood_defer_active(s,m))
    def test_changed_gap_resources_ideology_and_new_emergency_retry(self):
        s=self.snapshot();m={'wood_choice_defer':{'tick':143482,'signature':d.wood_defer_signature(s)}}
        for change in ('gap','stock','ideology','emergency'):
            t=copy.deepcopy(s)
            if change=='gap':t['development']['construction_projects'][0]['materials_needed'][0]['required_count']=3
            if change=='stock':t['development']['item_counts']['WoodLog']=1
            if change=='ideology':t['development']['ideology']['precepts'].append('TreeCutting_Prohibited')
            if change=='emergency':t['colonists'][0]['health_conditions']=[{'def_name':'Hypothermia','severity':.5}]
            self.assertFalse(d.wood_defer_active(t,m),change)
        s['game']['tick']=100;self.assertFalse(d.wood_defer_active(s,m))
    def test_no_affordable_or_nonstructural_replacement(self):
        s=self.snapshot();s['development']['item_counts']['Steel']=4
        self.assertFalse(a.structural_material_repair_options(s['development']))
        s=self.snapshot();s['development']['construction_projects'][0]['def_name']='TorchLamp'
        self.assertFalse(a.structural_material_repair_options(s['development']))
    def test_defer_persists_and_calls_no_api(self):
        s=self.snapshot();m={'anchor':{'x':0,'z':0}};c=Mock()
        r=d.execute_action(c,s,m,'harvest_nearby_trees',{'tree_type':'defer'})
        self.assertFalse(r['applied']);self.assertTrue(d.wood_defer_active(s,m));c.get.assert_not_called();c.post.assert_not_called()
    def test_replacement_defer_eight_cycles_keeps_wood_alternative(self):
        s=self.snapshot();m={'anchor':{'x':0,'z':0}};c=Mock()
        d.execute_action(c,s,m,'replace_blocked_shell_material',{'structural_material':'defer'})
        c.get.assert_not_called();c.post.assert_not_called()
        for cycle in range(8):
            s['game']['tick']+=1000
            plans=a.structural_material_repair_options(s['development'])
            self.assertFalse(d.structural_retry_options(s,m,plans))
            self.assertFalse(d.wood_defer_active(s,m))
        s['development']['item_counts']['Steel']=777
        self.assertTrue(d.structural_retry_options(s,m,a.structural_material_repair_options(s['development'])))

    def test_failed_replacement_backs_off_only_that_material(self):
        s=self.snapshot();m={'anchor':{'x':0,'z':0}}
        s['development']['building_catalog'][0]['allowed_stuff_defs'].append('Silver')
        s['development']['item_counts']['Silver']=100
        plans=a.structural_material_repair_options(s['development'])
        with patch.object(a,'execute_structural_material_repair',return_value={'applied':False,'reason':'native_refused'}):
            d.execute_action(Mock(),s,m,'replace_blocked_shell_material',{'structural_material':'20213|Steel'})
        remaining=d.structural_retry_options(s,m,plans)
        self.assertNotIn('20213|Steel',remaining);self.assertIn('20213|Silver',remaining)
        s['development']['construction_projects'][0]['thing_id']=20214
        self.assertTrue(d.structural_retry_options(s,m,a.structural_material_repair_options(s['development'])))

    def test_two_failed_materials_remain_backed_off_without_pingpong(self):
        s=self.snapshot();m={'anchor':{'x':0,'z':0}}
        s['development']['building_catalog'][0]['allowed_stuff_defs'].append('Silver')
        s['development']['item_counts']['Silver']=100
        plans=a.structural_material_repair_options(s['development'])
        with patch.object(a,'execute_structural_material_repair',return_value={'applied':False,'reason':'native_refused'}):
            for key in ['20213|Steel','20213|Silver']:
                d.execute_action(Mock(),s,m,'replace_blocked_shell_material',{'structural_material':key})
        for i in range(8):
            s['game']['tick']+=1000
            self.assertFalse(d.structural_retry_options(s,m,plans))
            self.assertFalse(d.wood_defer_active(s,m))

    def test_unobserved_project_materials_are_unknown_not_zero(self):
        s=self.snapshot();s['development']['construction_projects']=[{'thing_id':1,'label':'wall'}]
        self.assertIsNone(d.wood_supply_demand(s))
        self.assertEqual('construction_unknown',d.wood_leaf_context(s)['why'])

    def test_native_refusal_keeps_original(self):
        s=self.snapshot();s['development']['structural_material_options']=a.structural_material_repair_options(s['development'])
        c=Mock();p=s['development']['construction_projects']
        c.get.side_effect=[{'projects':p},[{'def_name':'Steel','stack_count':776}],s['development']['building_catalog'],{'projects':p}]
        c.post.return_value={'applied':False,'reason':'placement_refused'}
        r=a.execute_structural_material_repair(c,s,'20213|Steel',None)
        self.assertFalse(r['applied']);self.assertEqual(20213,c.post.call_args.kwargs['body']['project_thing_id'])
    def test_changed_native_identity_never_cancelled(self):
        s=self.snapshot();s['development']['structural_material_options']=a.structural_material_repair_options(s['development'])
        c=Mock();p=copy.deepcopy(s['development']['construction_projects']);p[0]['rotation']=1
        c.get.side_effect=[{'projects':p},[{'def_name':'Steel','stack_count':776}],s['development']['building_catalog']]
        r=a.execute_structural_material_repair(c,s,'20213|Steel',None)
        self.assertFalse(r['applied']);c.post.assert_not_called()

if __name__=='__main__':unittest.main()

