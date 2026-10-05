import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).parents[1]))
import colony_director as d
import colony_medical_recovery as m


def state():
    pawns=[]
    for i in (361,355,358):
        pawns.append({'id':i,'name':str(i),'health':.9,'rest':.8,'hunger':.8,
          'capacities':{'moving':.41,'manipulation':.22},'skills':{'Construction':{'level':3},'Medicine':{'level':2}},
          'work_priorities':{'Construction':{'priority':2,'disabled':False},'Doctor':{'priority':1,'disabled':False}},
          'health_conditions':[{'def_name':'Hypothermia','severity':.5,'cur_stage_index':3},
                               {'def_name':'Frostbite','severity':2,'tendable_now':True}]})
    pawns[1]['downed']=True;pawns[2]['downed']=True
    return {'game':{'tick':190000,'is_paused':False},'map':{'id':1,'enemies':0,'resources':{}},
      'colonists':pawns,'combat':{'hostiles':[],'colonists':[
       {'id':361,'name':'Moon','current_job':'TendPatient','current_job_target_id':355,'care_target_id':355,
        'moving':.41,'manipulation':.22,'health':.9,'bleeding_rate':0},
       {'id':355,'name':'Red','is_downed':True,'tendable_now':True,'bleeding_rate':0},
       {'id':358,'name':'Furr','is_downed':True,'tendable_now':False,'bleeding_rate':0}]},
      'development':{'cold_start_focus':'finish_heat','weather':{'temperature':-8},'rooms':[],
       'buildings':[],'construction_projects':[{'thing_id':34172,'def_name':'Campfire','kind':'blueprint',
       'position':{'x':128,'z':150},'minimum_construction_skill':0,
       'materials_needed':[{'def_name':'WoodLog','required_count':20,'available_count':206}]}]}}


class RoutineCareThermalReplay(unittest.TestCase):
    def test_eight_cycles_native_job_and_project_progress_persist(self):
        s=state();posts=[];memory={"anchor":{"x":128,"z":150}}
        def get(endpoint,**kw):
            if endpoint.endswith('/weather'):return copy.deepcopy(s['development']['weather'])
            if endpoint.endswith('/rooms'):return {'rooms':copy.deepcopy(s['development']['rooms'])}
            if endpoint.endswith('/projects'):return {'projects':copy.deepcopy(s['development']['construction_projects'])}
            if endpoint.endswith('/buildings'):return []
            if endpoint.endswith('/detailed'):return copy.deepcopy(s['colonists'])
            raise AssertionError(endpoint)
        def post(endpoint,**kw):
            posts.append((endpoint,kw))
            if endpoint.endswith('/work-priority'):
                body=kw['body'];s['colonists'][0]['work_priorities'][body['work']]['priority']=body['priority']
            if endpoint.endswith('/builder/prioritize'):
                s['combat']['colonists'][0].update(current_job='FinishFrame',current_job_target_id=34172,care_target_id=None)
                s['development']['construction_projects'][0].update(kind='frame',percent_complete=.1)
            return {'applied':True,'success':True}
        client=Mock();client.get.side_effect=get;client.post.side_effect=post
        with patch.object(d.bridge,'collect_snapshot',side_effect=lambda _:copy.deepcopy(s)), \
             patch.object(d.bridge,'normalize_colonists',side_effect=lambda rows:rows), \
             patch.object(d,'publish_post_combat_care_overlay'), patch.object(d.bridge,'append_log'):
            for cycle in range(8):
                s['game']['tick']+=600
                if cycle==3:
                    s['development']['construction_projects']=[]
                    s['development']['rooms']=[{'temperature':20,'contained_beds_ids':[1],
                       'open_roof_count':0,'touches_map_edge':False,'cells_count':20}]
                    s['combat']['colonists'][0].update(current_job='Wander',current_job_target_id=None)
                if cycle<3:
                    self.assertIsNone(d.run_post_combat_care_cycle(client,Mock(),copy.deepcopy(s),Path('unused')))
                if cycle==0:
                    self.assertTrue(d.routine_care_can_yield_to_warmth(s,361))
                    result=d.execute_action(client,copy.deepcopy(s),memory,'prioritize_thermal_project',
                        {'thermal_project':34172,'worker_pawn':361})
                    self.assertTrue(result['applied'])
                elif cycle<3:
                    s['development']['construction_projects'][0]['percent_complete']=(cycle+1)/3
                else:
                    self.assertFalse(d.routine_care_can_yield_to_warmth(s,361))
        builder=[kw['body'] for ep,kw in posts if ep.endswith('/builder/prioritize')]
        self.assertEqual(builder,[{'map_id':1,'project_thing_id':34172,'pawn_id':361}])
        self.assertEqual(s['colonists'][0]['work_priorities']['Doctor']['priority'],2)
        self.assertEqual(s['development']['construction_projects'],[])

    def test_moderate_bleeding_reassigns_slow_doctor_from_routine_patient(self):
        s=state();s['combat']['colonists'][2].update(bleeding_rate=.96,tendable_now=True)
        s['colonists'][2]['health_conditions'].append({'def_name':'BloodLoss','severity':.351})
        options=d.post_combat_care_options(s)
        row=options['tend_358_361']
        self.assertEqual(row['reassign_from_patient_id'],355)
        self.assertAlmostEqual(row['estimated_bleedout_ticks'],40562.5)
        self.assertFalse(d.routine_care_can_yield_to_warmth(s,361))
        self.assertTrue(d.urgent_care_actionable(s))

    def test_urgent_old_care_cannot_yield_or_reassign(self):
        for condition in ('bleed','infection'):
            s=state();s['combat']['colonists'][2].update(bleeding_rate=.96,tendable_now=True)
            if condition=='bleed':s['combat']['colonists'][1]['bleeding_rate']=.2
            else:s['colonists'][1]['health_conditions'].append({'def_name':'WoundInfection','tendable_now':True,'immunity':.1})
            self.assertFalse(d.routine_care_can_yield_to_warmth(s,361))
            self.assertNotIn('tend_358_361',d.post_combat_care_options(s))

    def test_default_guards_never_release_routine_actor_or_patient(self):
        s=state()
        self.assertEqual(d.active_care_pawn_ids(s), {'361','355'})
        self.assertEqual(d.active_care_pawn_ids(s,allow_thermal_yield=True), {'355'})
        client=Mock()
        self.assertFalse(d.prioritize(client,s,'Hauling',361)['applied'])
        client.post.assert_not_called()

    def test_new_bleed_at_fresh_mutation_check_cancels_warmth_dispatch(self):
        s=state();fresh=copy.deepcopy(s)
        fresh['combat']['colonists'][1]['bleeding_rate']=.2
        fresh['colonists'][1]['bleeding_rate']=.2
        client=Mock()
        def get(ep,**kw):
            if ep.endswith('/weather'):return {'temperature':-8}
            if ep.endswith('/rooms'):return {'rooms':[]}
            if ep.endswith('/projects'):return {'projects':fresh['development']['construction_projects']}
            raise AssertionError(ep)
        client.get.side_effect=get
        with patch.object(d.bridge,'collect_snapshot',return_value=fresh):
            result=d.execute_action(client,s,{'anchor':{'x':128,'z':150}},'prioritize_thermal_project',
                {'thermal_project':34172,'worker_pawn':361})
        self.assertFalse(result['applied'])
        client.post.assert_not_called()

    def test_no_material_no_viable_warmth_and_active_patient_no_duplicate(self):
        s=state();s['development']['construction_projects'][0]['materials_needed'][0]['available_count']=0
        self.assertFalse(d.routine_care_can_yield_to_warmth(s,361))
        self.assertNotIn('tend_355_361',d.post_combat_care_options(s))

    def test_actual_cached_tokenizer_postcare_keeps_thermal_and_bleeding_facts(self):
        from tokenizers import Tokenizer
        paths=list((Path.home()/'.cache/huggingface/hub/models--convaiinnovations--laya/snapshots').glob('*/tokenizer/tokenizer.json'))
        if not paths:self.skipTest('cached tokenizer unavailable')
        tok=Tokenizer.from_file(str(sorted(paths)[0]))
        class Agent:
            cfg={'max_len':512,'head_max_len':192}
            def tok(self,text,**kw):return {'input_ids':tok.encode(text,add_special_tokens=False).ids[:kw.get('max_length',99999)]}
            def predict(self,state,questions):
                key,q=next(iter(questions.items()))
                return {'answers':{key:{'choice':next(iter(q['criteria']))}}}
        s=state();s['combat']['colonists'][2].update(bleeding_rate=.96,tendable_now=True)
        s['colonists'][2].update(bleeding_rate=.96)
        s['colonists'][2]['health_conditions'].append({'def_name':'BloodLoss','severity':.351})
        client=Mock()
        def get(ep,**kw):
            if ep.endswith('/weather'):return {'temperature':-8}
            if ep.endswith('/rooms'):return {'rooms':[]}
            if ep.endswith('/projects'):return {'projects':s['development']['construction_projects']}
            if ep.endswith('/buildings'):return []
            return {}
        client.get.side_effect=get;client.post.return_value={'applied':True}
        with patch.object(d,'publish_post_combat_care_overlay'),patch.object(d.bridge,'append_log'):
            record=d.run_post_combat_care_cycle(client,Agent(),s,Path('unused'))
        raw=record['decision']['raw']
        for stage in [*raw.get('narrowing',[]),raw]:
            risks=stage['visible_state']['facts']['care_risks']
            self.assertEqual(risks['thermal']['Hypothermia']['stage'],3)
            self.assertEqual(risks['outside_c'],-8)
            self.assertEqual(risks['bleed_rate_max'],.96)
            self.assertLessEqual(stage['prompt_budget']['state_tokens'],312)

    def test_medical_helper_low_health_low_capacity_remains_native_candidate(self):
        s=state();s['colonists'][0]['health']=.4
        s['combat']['colonists'][0]['current_job']='Wander'
        self.assertEqual([p['id'] for p in m.helpers(s,355,doctor=True)],[361])

if __name__=='__main__':unittest.main()
