"""Designation lifecycle regressions: accepted work is not delivered nutrition."""
import copy
import json
import unittest
from unittest.mock import patch
import colony_capabilities as caps
from tests.test_capabilities import snapshot, Client


class AtRiskHarvestLifecycleTests(unittest.TestCase):
    def fixture(self):
        s=snapshot()
        plant={'thing_id':5,'def_name':'Plant_Agave','harvestable_now':True,'dying':True,
               'is_designated_for_harvest':False,'harvested_thing_def':'RawAgave','harvest_yield':8,
               'growth':.99,'hit_points':80,'max_hit_points':100}
        s['development']['plants']=[plant]
        return s,plant

    @patch('colony_retry.time.time')
    def test_eight_cycles_no_repeat_after_accepted_ack_without_designation_readback(self,clock):
        s,plant=self.fixture();state={};clock.return_value=100;client=Client()
        caps.prepare(s,state)
        result=caps.execute(client,s,state,'harvest_at_risk_crops',{'harvest_worker':'1'})
        self.assertEqual(result['reason'],'harvest_designation_accepted_not_delivered')
        self.assertIsNone(result['delivered_nutrition']);self.assertEqual(result['subject_ids'],[5])
        initial=s['game']['tick'];posts=len(client.calls)
        for i in range(8):
            clock.return_value=110+i*10;s['game']['tick']=initial+20000+i*1000
            plant['growth']=.991+i*.001;s['colonists'][0]['food']=.4-i*.01
            state=json.loads(json.dumps(state))
            self.assertNotIn('harvest_at_risk_crops',caps.prepare(s,state))
        self.assertEqual(len(client.calls),posts)
        clock.return_value=221
        self.assertIn('harvest_at_risk_crops',caps.prepare(s,state))

    @patch('colony_retry.time.time',return_value=100)
    def test_new_subject_and_changed_material_risk_bypass_only_affected_subject(self,clock):
        s,plant=self.fixture();state={};caps.prepare(s,state)
        caps.execute(Client(),s,state,'harvest_at_risk_crops',{'harvest_worker':'1'})
        s['development']['plants'].append({**plant,'thing_id':6})
        caps.prepare(s,state)
        self.assertEqual([p['thing_id'] for p in s['development']['capability_plans']['harvest_at_risk_crops']['plants']],[6])
        plant['dying_from_pollution']=True
        caps.prepare(s,state)
        self.assertEqual({p['thing_id'] for p in s['development']['capability_plans']['harvest_at_risk_crops']['plants']},{5,6})

    @patch('colony_retry.time.time',return_value=100)
    def test_active_harvest_preserved_and_other_actor_can_save_new_plant(self,clock):
        s,plant=self.fixture();state={};caps.prepare(s,state)
        s['colonists'][0].update(current_job='HarvestDesignated',current_job_target_id=5)
        client=Client()
        result=caps.execute(client,s,state,'harvest_at_risk_crops',{'harvest_worker':'1'})
        self.assertEqual(result['reason'],'harvest_worker_already_active');self.assertEqual(client.calls,[])
        second=copy.deepcopy(s['colonists'][0]);second.update(id=2,current_job='Wait_Wander',current_job_target_id=None)
        s['colonists'].append(second);s['development']['plants'].append({**plant,'thing_id':6})
        caps.prepare(s,state);plan=s['development']['capability_plans']['harvest_at_risk_crops']
        self.assertEqual([p['id'] for p in plan['workers']],[2]);self.assertEqual([p['thing_id'] for p in plan['plants']],[6])
        self.assertEqual(s['colonists'][0]['current_job'],'HarvestDesignated')

    @patch('colony_retry.time.time',return_value=100)
    def test_new_clinical_starvation_band_can_retry_missing_designation(self,clock):
        s,plant=self.fixture();state={};caps.prepare(s,state)
        caps.execute(Client(),s,state,'harvest_at_risk_crops',{'harvest_worker':'1'})
        self.assertNotIn('harvest_at_risk_crops',caps.prepare(s,state))
        s['colonists'][0]['health_conditions']=[{'def_name':'Malnutrition','severity':.6}]
        self.assertIn('harvest_at_risk_crops',caps.prepare(s,state))
        plant['is_designated_for_harvest']=True
        self.assertNotIn('harvest_at_risk_crops',caps.prepare(s,state))

    @patch('colony_retry.time.time',return_value=100)
    def test_disappearance_is_not_delivered_food_and_same_id_regrowth_can_be_considered(self,clock):
        s,plant=self.fixture();state={};caps.prepare(s,state)
        result=caps.execute(Client(),s,state,'harvest_at_risk_crops',{'harvest_worker':'1'})
        plant['harvestable_now']=False;caps.prepare(s,state)
        self.assertNotIn('harvest_at_risk_crops:5',state['capability_history'])
        self.assertIsNone(result['delivered_nutrition'])
        plant['harvestable_now']=True
        self.assertIn('harvest_at_risk_crops',caps.prepare(s,state))
