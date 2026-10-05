import copy
import unittest
import colony_director as d

class ColdWorkerTests(unittest.TestCase):
    def snapshot(self):
        def pawn(id,name,rest,job,**extra):
            return {'id':id,'name':name,'rest':rest,'hunger':.8,'current_job':job,
                'bleeding_rate':0,'work_priorities':{'Construction':{'priority':1,'disabled':False}},
                'skills':{'Construction':{'level':2}},'health_conditions':[{'def_name':'Hypothermia','severity':.5}],**extra}
        return {'map':{'resources':{'nutrition':12}},'colonists':[
            pawn(1,'Red',.94,'LayDown'),pawn(2,'Furr',.775,'FinishFrame',bleeding_rate=.96),
            pawn(3,'Moon',.887,'TendPatient')],
            'combat':{'colonists':[{'id':2,'current_job':'FinishFrame','current_job_target_id':10}]},
            'development':{'cold_threat':{'outside_c':-8,'patients':[{'name':'Red'}]},'rooms':[]}}
    def focus(self,s):
        details={'construction_project_options':[{'thing_id':10,'def_name':'Wall'}, {'thing_id':11,'def_name':'Wall'}]}
        actions=d.focus_cold_start_choices(s,['prioritize_construction_project','hold_survival','tend_colonist'],details)
        return actions,details
    def test_well_rested_resting_worker_can_help_without_interrupting_builder_or_care(self):
        s=self.snapshot();actions,details=self.focus(s)
        self.assertIn('prioritize_construction_project',actions)
        self.assertIn('hold_survival',actions)
        self.assertEqual([11],[p['thing_id'] for p in details['construction_project_options']])
        workers=d.worker_criteria(s,'Construction');self.assertEqual({'1'},set(workers))
        for fact in ['rest 0.94','hunger 0.8','LayDown','cold -8','hypothermia 0.50','bleeding']:
            self.assertIn(fact,workers['1'])
    def test_exhausted_bleeding_or_infected_extra_worker_not_offered(self):
        for extra in [{'rest':.2},{'bleeding_rate':.1},{'health_conditions':[{'def_name':'WoundInfection','severity':.4,'immunity':.2,'lethal_severity':1,'tendable_now':True}]}]:
            s=self.snapshot();s['colonists'][0].update(extra)
            self.assertEqual({},d.worker_criteria(s,'Construction'))
            self.assertNotIn('prioritize_construction_project',self.focus(s)[0])
    def test_live_combat_job_protects_builder_even_if_detailed_job_is_stale(self):
        s=self.snapshot();s['colonists'][1]['current_job']='LayDown';s['colonists'][1]['bleeding_rate']=0
        self.assertEqual({'1'},set(d.worker_criteria(s,'Construction')))
    def test_reserved_only_project_keeps_current_builder_working(self):
        s=self.snapshot();details={'construction_project_options':[{'thing_id':10,'def_name':'Wall'}]}
        actions=d.focus_cold_start_choices(s,['prioritize_construction_project','hold_survival'],details)
        self.assertNotIn('prioritize_construction_project',actions)

if __name__=='__main__':unittest.main()
