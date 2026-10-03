"""Regression cases reconstructed from the failed October 3 colony."""
import copy
import unittest
import colony_director as director
import colony_medical_recovery as care
import colony_resilience as resilience
import rimworld_laya as bridge

class RecoveryFaults(unittest.TestCase):
    def snapshot(self):
        return {"combat": {"colonists": [
            {"id": 1, "name": "Yunxin", "tendable_now": True, "is_downed": True, "bleeding_rate": 4.315},
            {"id": 2, "name": "Barbara", "tendable_now": True, "is_downed": True, "bleeding_rate": 0},
            {"id": 3, "name": "Virgil", "current_job": "TendPatient", "current_job_target_id": 2,
             "moving": 1, "manipulation": 1, "medicine_skill": 0},
        ]}, "colonists": [
            {"id": 1, "health_conditions": [{"def_name": "BloodLoss", "severity": .795}]},
            {"id": 2, "health_conditions": [{"def_name": "BloodLoss", "severity": .643, "life_threatening": True}]},
            {"id": 3, "skills": {"Medicine": {"disabled": False}}},
        ]}

    def test_stopped_bleeding_releases_doctor_for_imminent_other_death(self):
        s=self.snapshot(); plans=director.post_combat_care_options(s)
        self.assertEqual(plans['tend_1_3']['reassign_from_patient_id'],2)
        self.assertTrue(director.urgent_care_actionable(s))
        self.assertIn('stable patient 2',plans['tend_1_3']['summary'])

    def test_continuing_bleed_or_active_illness_or_surgery_keeps_doctor(self):
        for mutation in ('bleed','disease','surgery','ample_time'):
            s=self.snapshot()
            if mutation=='bleed': s['combat']['colonists'][1]['bleeding_rate']=.2
            if mutation=='disease': s['colonists'][1]['health_conditions'].append({'def_name':'Plague','tendable_now':True,'immunity':.5})
            if mutation=='surgery': s['combat']['colonists'][2]['current_job']='DoBill'
            if mutation=='ample_time': s['colonists'][0]['health_conditions'][0]['severity']=.2
            self.assertNotIn('tend_1_3',director.post_combat_care_options(s),mutation)

    def test_nonimmune_lungrot_enters_disease_gate_with_quality_and_body_part(self):
        s=self.snapshot();s['combat']['colonists'][0].update(is_downed=False,bleeding_rate=0)
        s['combat']['colonists'][2]['current_job']='Wait'
        s['colonists'][0]['health_conditions']=[{'def_name':'LungRot','part':'left lung','severity':.579,
            'lethal_severity':1,'can_ever_kill':True,'immunity':None,'tendable_now':True,'tend_quality':.088,'tend_ticks_left':-1}]
        self.assertEqual(bridge.active_immune_diseases(s['colonists'][0]),[])
        self.assertTrue(bridge.active_recovery_diseases(s['colonists'][0]))
        self.assertTrue(director.urgent_care_actionable(s))
        summary=director.disease_care_summary(s['colonists'][0])
        self.assertIn('left lung',summary);self.assertIn('no immunity race',summary);self.assertIn('9%',summary)

    def test_recovered_immunity_and_permanent_conditions_not_disease_recovery(self):
        p={'health_conditions':[{'def_name':'Plague','can_ever_kill':True,'immunity':1,'lethal_severity':1},
             {'def_name':'Scar','permanent':True,'lethal_severity':1}, {'def_name':'BloodLoss','lethal_severity':1}]}
        self.assertEqual(bridge.active_recovery_diseases(p),[])

    def test_resilience_existing_tend_cannot_be_reissued_by_another_doctor(self):
        s={'game':{'tick':1},'development':{'resilience':{'active_orders':[{'kind':'tend','target_id':1,'worker_id':3}],
             'options':[{'kind':'tend','target_id':1,'worker_id':4,'giver':'DoctorTendEmergency'}]}}}
        self.assertEqual(resilience.prepare(s,{}),[])

    def test_disposal_attention_and_active_haul_suppression(self):
        s={'game':{'tick':1},'development':{'resilience':{'options':[
            {'kind':'dispose_corpse','worker_id':3,'target_id':5,'giver':'HaulCorpses'}]}}}
        self.assertEqual(resilience.prepare(s,{}),['resilience_dispose_corpse'])
        self.assertTrue(s['development']['sanitation_urgent'])
        s['development']['resilience']['active_orders']=[{'kind':'haul','target_id':5}]
        self.assertEqual(resilience.prepare(s,{}),[])
        self.assertFalse(s['development']['sanitation_urgent'])

    def frontier_rows(self):
        return {'good':{'id':3,'current_job':'Wait_Wander','position':{'x':5,'z':0},'medical_tend_quality':.9,'medical_tend_speed':1.2,'medicine_skill':14},
                'bad':{'id':4,'current_job':'Wait_Wander','position':{'x':5,'z':0},'medical_tend_quality':.1,'medical_tend_speed':1,'medicine_skill':0}}

    def test_frontier_elimination_is_order_invariant_and_explained(self):
        rows=self.frontier_rows();patient={'position':{'x':0,'z':0}}
        for options in (rows,dict(reversed(list(rows.items())))):
            kept,removed=care.helper_frontier({},patient,options)
            self.assertEqual(set(kept),{'good'});self.assertEqual(removed['bad']['dominated_by'],['good'])

    def test_frontier_preserves_unknown_stats_near_bad_and_unknown_opportunity(self):
        for change in ('unknown_quality','near_bad','busy_good','unknown_job','surgery'):
            rows=self.frontier_rows()
            if change=='unknown_quality': rows['bad'].pop('medical_tend_quality')
            if change=='near_bad': rows['bad']['position']['x']=1
            if change=='busy_good': rows['good']['current_job']='TendPatient'
            if change=='unknown_job': rows['good'].pop('current_job')
            if change=='surgery': rows['good']['current_job']='DoBill'
            self.assertEqual(set(care.helper_frontier({}, {'position':{'x':0,'z':0}},rows)[0]),{'good','bad'},change)

    def test_postcare_and_regular_care_use_same_frontier(self):
        rows=self.frontier_rows();s=self.snapshot()
        s['combat']['colonists']=[dict(s['combat']['colonists'][0],position={'x':0,'z':0}),*rows.values()]
        s['colonists'].append({'id':4,'skills':{'Medicine':{'disabled':False}}})
        plans=director.post_combat_care_options(s)
        self.assertIn('tend_1_3',plans);self.assertNotIn('tend_1_4',plans)
        regular={'patient':{'id':1,'position':{'x':0,'z':0}},'helpers':rows}
        context,criteria=care.helper_comparison(s,regular,'tend_colonist')
        self.assertEqual(set(criteria),{'good'});self.assertIn('Known dominated idle helpers excluded',context)

if __name__=='__main__': unittest.main()
