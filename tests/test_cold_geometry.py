import unittest
import copy
import colony_director as d

class ColdGeometryTests(unittest.TestCase):
    def snapshot(self, corners=True):
        layout=d.starter_base_blueprint(3,cold=True,include_corners=corners)
        def row(i,b):return {'id':i,'def':b['def_name'],'position':{'x':126+b['rel_x'],'z':146+b['rel_z']}}
        built=[row(i,b) for i,b in enumerate(layout['buildings'],1) if b['def_name']=='SleepingSpot']
        return {'map':{'id':1,'resources':{'nutrition':12}},'colonists':[{'id':1,'name':'Builder','rest':.9,'hunger':.8,
            'work_priorities':{'Construction':{'priority':1,'disabled':False}}}],
            'development':{'cold_threat':{'outside_c':-8,'patients':[{'name':'Builder'}]},'rooms':[], 'buildings':built,
                'construction_projects':[], 'cold_starter_plan':{'cold':True,'origin':{'x':126,'z':146},'layout':layout}}}
    def project(self,x,z,def_name='Wall',id=100):return {'thing_id':id,'def_name':def_name,'position':{'x':x,'z':z}}
    def enclose(self,s):
        plan=s['development']['cold_starter_plan']
        for i,b in enumerate(d.starter_base_blueprint(3,cold=True)['buildings'],100):
            if b['def_name'] in {'Wall','Door'}:s['development']['buildings'].append({'id':i,'def':b['def_name'],
                'position':{'x':126+b['rel_x'],'z':146+b['rel_z']}})
    def focus(self,s,actions):
        details={'construction_project_options':s['development']['construction_projects']}
        return d.focus_cold_start_choices(s,actions,details),details
    def test_small_layout_cardinal_boundary_is_closed_without_corners(self):
        layout=d.starter_base_blueprint(3,cold=True)
        blockers={(b['rel_x'],b['rel_z']) for b in layout['buildings'] if b['def_name'] in {'Wall','Door'}}
        self.assertTrue(all((x+dx,z+dz) in blockers or 1<=x+dx<=3 and 1<=z+dz<=4
            for x in range(1,4) for z in range(1,5) for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]))
        self.assertEqual(13,sum(b['def_name']=='Wall' for b in layout['buildings']))
        self.assertFalse(blockers.intersection({(0,0),(4,0),(0,5),(4,5)}))
    def test_existing_plan_closure_gaps_before_corner_or_fire(self):
        s=self.snapshot();s['development']['construction_projects']=[self.project(126,146,id=1),self.project(127,146,id=2),self.project(128,150,'Campfire',3)]
        actions,details=self.focus(s,['prioritize_construction_project','hold_survival'])
        self.assertIn('prioritize_construction_project',actions)
        self.assertEqual([2],[p['thing_id'] for p in details['construction_project_options']])
    def test_closed_shell_roof_pending_does_not_claim_heat_or_progress(self):
        s=self.snapshot();self.enclose(s)
        s['development']['construction_projects']=[self.project(126,146,id=1),self.project(128,150,'Campfire',3)]
        actions,_=self.focus(s,['prioritize_construction_project','hold_survival','set_work_priority'])
        self.assertEqual(['set_work_priority'],actions)
        s['development']['cold_starter_plan']['layout']=d.starter_base_blueprint(3,cold=True)
        actions,_=self.focus(s,['hold_survival'])
        self.assertEqual([],actions);self.assertIn('blocked_reason',s['development']['cold_roof_pending'])
    def test_active_native_buildroof_preserved(self):
        s=self.snapshot();self.enclose(s);s['colonists'][0]['current_job']='BuildRoof'
        actions,_=self.focus(s,['prioritize_construction_project','hold_survival'])
        self.assertEqual(['hold_survival'],actions)
        self.assertEqual([],d.cold_shelter_available_workers(s))
    def test_actual_roofed_room_releases_fire_before_legacy_corner(self):
        s=self.snapshot();self.enclose(s)
        beds=[b['id'] for b in s['development']['buildings'] if b['def']=='SleepingSpot']
        s['development']['rooms']=[{'id':7,'touches_map_edge':False,'open_roof_count':0,'contained_beds_ids':beds,'temperature':-5}]
        s['development']['construction_projects']=[self.project(126,146,id=1),self.project(128,150,'Campfire',3)]
        actions,details=self.focus(s,['prioritize_construction_project','hold_survival'])
        self.assertIn('prioritize_construction_project',actions)
        self.assertEqual([3],[p['thing_id'] for p in details['construction_project_options']])
    def test_dynamic_material_price_uses_actual_layout_and_loaded_cost(self):
        dev={'item_counts':{'WoodLog':110},'building_catalog':[]}
        self.assertEqual({'WoodLog':110},d.cold_starter_material_options(dev,3)['WoodLog'])
        dev['building_catalog']=[{'def_name':'Wall','cost_stuff_count':7},{'def_name':'Door','cost_stuff_count':25},
            {'def_name':'Campfire','cost_list':[{'thing_def':'WoodLog','count':20}]}]
        self.assertNotIn('WoodLog',d.cold_starter_material_options(dev,3))
    def test_legacy_pending_layout_survives_reload(self):
        memory={'pending_starter_base':{'map_id':1,'origin':{'x':126,'z':146},'cold':True,
            'layout':d.starter_base_blueprint(3,cold=True,include_corners=True)}}
        self.assertIsNotNone(d.pending_starter_plan(memory,1))
    def test_unrecorded_arbitrary_walls_keep_ordinary_selection(self):
        s=self.snapshot();s['development'].pop('cold_starter_plan')
        s['development']['construction_projects']=[self.project(126,146,id=1)]
        _,details=self.focus(s,['prioritize_construction_project'])
        self.assertEqual([1],[p['thing_id'] for p in details['construction_project_options']])
    def candidate_fixture(self):
        s=self.snapshot();s['game']={'tick':100000}
        s['colonists'][0].update(health=1,position={'x':128,'z':148},health_conditions=[{'def_name':'Hypothermia','severity':.5}])
        s.update(animals=[],wild_animals=[],combat={})
        s['development'].update(item_counts={'WoodLog':100},weather={'temperature':-8},building_counts={'SleepingSpot':3},
            construction_projects=[{**self.project(127,146,id=10),'materials_needed':[{'def_name':'WoodLog','required_count':5,'available_count':100}]},self.project(127,151,id=11)])
        m={'anchor':{'x':126,'z':146},'issued':{'starter_base':50000},'known_starter_base':s['development']['cold_starter_plan'],
            'failed_construction_projects':{'10':{'tick':99000,'wood':100,'materials':{'WoodLog':100}}}}
        return s,m
    def test_failed_closure_backoff_preserved_until_material_change_or_timeout(self):
        original,memory=self.candidate_fixture()
        for tick,stock,expected in [(100000,100,{11}),(110000,100,{11}),(110000,101,{10,11}),(129001,100,{10,11})]:
            with self.subTest(tick=tick,stock=stock):
                s=copy.deepcopy(original);s['game']['tick']=tick;s['development']['item_counts']['WoodLog']=stock
                s['development']['construction_projects'][0]['materials_needed'][0]['available_count']=stock
                _,details=d.candidate_actions(None,s,copy.deepcopy(memory))
                self.assertEqual(expected,{p['thing_id'] for p in details['eligible_construction_projects']})
                self.assertEqual(expected,{p['thing_id'] for p in details['construction_project_options']})
    def test_explicit_empty_eligible_list_never_falls_back_to_raw_projects(self):
        s=self.snapshot();s['development']['construction_projects']=[self.project(127,146,id=10)]
        details={'construction_project_options':[],'eligible_construction_projects':[]}
        d.focus_cold_start_choices(s,['hold_survival'],details)
        self.assertEqual([],details['construction_project_options'])
    def test_candidate_cycle_retains_roof_block_evidence_without_exception(self):
        s,m=self.candidate_fixture();self.enclose(s)
        d.candidate_actions(None,s,m)
        self.assertIn('blocked_reason',s['development']['cold_roof_pending'])

if __name__=='__main__':unittest.main()
