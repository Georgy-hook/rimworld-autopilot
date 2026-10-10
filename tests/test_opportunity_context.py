import copy
import json
import unittest
from unittest.mock import patch

import colony_mining as mining
import colony_sustenance as sustenance
import laya_decisions as decisions
import test_parameter_context as parameters
from test_postmortem_fault_sequences import mine_snapshot


class OpportunityContextTests(unittest.TestCase):
    def test_mining_numbers_survive_every_comparison_and_order(self):
        for reverse in (False, True):
            agent = parameters.ParameterContextTests().agent()
            snapshot = mine_snapshot()
            snapshot['map']['resources']['nutrition'] = 32
            snapshot['colonists'][0].update(hunger=.9, health_conditions=[])
            first = snapshot['development']['mining']['options'][0]
            other = copy.deepcopy(first)
            other.update(key='1:101', thing_ids=[101], product_def='Steel', nominal_market_value=76)
            snapshot['development']['mining']['options'] = [other,first] if reverse else [first,other]
            mining.prepare(snapshot,{})
            mining.choose(agent,{},'mining_extract',snapshot)
            for visible in agent.seen:
                facts=visible['facts']['comparison']
                self.assertEqual(facts['shared']['food_nutrition'],32)
                for key,row in facts['options'].items():
                    if key=='defer': continue
                    self.assertEqual((row['hp'],row['speed'],row['worker_food']), (3000,1.2,.9))
                    self.assertIn(row['nominal_value'],(400,76))
                self.assertLessEqual(len(agent.tok(json.dumps(visible,ensure_ascii=False))['input_ids']),312)

    def test_welfare_measured_clinic_and_reserve_reach_all_stages(self):
        agent=parameters.ParameterContextTests().agent()
        context={'options':[{'key':'warmspot:4:1:1','kind':'warmspot','target_id':4,'value':'1,1',
            'label':'Free warm spot', 'cost':'free', 'facts':{'source_c':-22,'destination_c':21,
            'hypothermia':.88,'downed':True,'materials':0,'rescue_pending':True}}],
            'animals':[{'id':4,'food':.4,'downed':True}],
            'human_food':[{'def_name':'RawRice','fresh_eligible_nutrition':6.2}]}
        snapshot={'map':{'id':0},'game':{'tick':1},'development':{'sustenance':context}}
        sustenance.choose(agent,{},'sustenance_animal_welfare',snapshot)
        self.assertEqual(len(agent.seen),1)
        for visible in agent.seen:
            facts=visible['facts']['comparison']
            self.assertEqual(facts['shared']['human_nutrition'],6.2)
            row=facts['options']['o0']
            self.assertEqual((row['hypothermia'],row['source_c'],row['destination_c']),(.88,-22,21))
            self.assertTrue(row['rescue_pending'])

    def test_oversized_required_facts_fail_explicitly_without_truncation(self):
        agent=parameters.ParameterContextTests().agent()
        with self.assertRaisesRegex(ValueError,'Consequence envelope'):
            decisions.ask_laya_choice(agent,{'comparison_facts':{'shared':{'required':'critical '*1000}},
                'option_effects':{'a':{'benefit':'act'},'defer':{'benefit':'wait'}}},
                'test','Choose',{'a':'Act','defer':'Wait'})
        self.assertEqual(agent.seen,[])

    def test_measured_pen_feed_contains_finite_reserve_and_starvation(self):
        context={'options':[{'key':'penfeed:1:2','kind':'penfeed','facts':{
            'malnutrition':.8,'nutrition':.8,'human_remaining':5.4,'human_minimum':1.8,'delivery_pending':True}}]}
        facts=sustenance._subject_facts(context,'penfeed:1:2')
        self.assertEqual((facts['malnutrition'],facts['human_remaining']),(.8,5.4))
        self.assertTrue(facts['delivery_pending'])


if __name__=='__main__': unittest.main()
