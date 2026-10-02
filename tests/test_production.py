import copy
import unittest
from unittest.mock import patch
import colony_production as p

class Client:
    def __init__(self, context, response=None):
        self.context=context; self.calls=[]; self.response=response or {}
    def get(self, *args, **kwargs): return copy.deepcopy(self.context)
    def post(self, *args, **kwargs): self.calls.append((args, kwargs)); return self.response

class ProductionTests(unittest.TestCase):
    def snapshot(self):
        return {"map":{"id":1}, "game":{"tick":20000}, "colonists":[{"id":4,"work_priorities":{"Cooking":{"disabled":False,"priority":1}}}], "development":{"production":{
            "animals":[{"species":"Muffalo","can_eat_kibble":True,"food_level":.2,"can_graze":True}],
            "buildings":[{"id":2,"def_name":"Cooler","switch_on":True,"flick_pending":False}],
            "stocks":[{"def_name":"Meat_Chicken","nutrition":1,"eligible_nutrition":1},{"def_name":"Hay","nutrition":1,"eligible_nutrition":1}],
            "feed_tables":[{"id":3,"usable":True,"existing_bill":False,"eligible_worker_ids":[4],"ingredients":[{"count":1,"allowed_defs":["Meat_Chicken"]},{"count":1,"allowed_defs":["Hay"]}]}]}}}
    def test_nutrition_groups_and_cook_gate(self):
        s=self.snapshot(); self.assertIn("production_feed_batch",p.prepare(s,{}))
        s['development']['production']['stocks'][1]['eligible_nutrition']=.99
        self.assertNotIn("production_feed_batch",p.prepare(s,{}))
    def test_no_animals_incompatible_diet_or_protected_cook(self):
        for change in ('none','diet','care','priority','skill'):
            s=self.snapshot()
            if change=='none':s['development']['production']['animals']=[]
            if change=='diet':s['development']['production']['animals'][0]['can_eat_kibble']=False
            if change=='care':s['colonists'][0]['current_job']='TendPatient'
            if change=='priority':s['colonists'][0]['work_priorities']['Cooking']['priority']=0
            if change=='skill':s['development']['production']['feed_tables'][0]['eligible_worker_ids']=[]
            self.assertNotIn('production_feed_batch',p.prepare(s,{}),change)
    def test_unsafe_or_missing_eligible_stock_never_proves_supply(self):
        s=self.snapshot();s['development']['production']['stocks'][0].pop('eligible_nutrition')
        self.assertNotIn('production_feed_batch',p.prepare(s,{}))
    def test_completed_bill_context_allows_next_finite_batch(self):
        s=self.snapshot();s['development']['production']['feed_tables'][0]['existing_bill']=False
        self.assertIn('production_feed_batch',p.prepare(s,{}))
    def test_feed_revalidation_supply_loss_blocks_post(self):
        s=self.snapshot();p.prepare(s,{})
        live=copy.deepcopy(s['development']['production']);live['stocks'][0]['eligible_nutrition']=0
        c=Client(live);r=p.execute(c,s,{},'production_feed_batch',{'production_policy':'3'})
        self.assertFalse(r['applied']);self.assertEqual([],c.calls)
    def test_unavailable_collection_is_error(self):
        with self.assertRaises(ValueError):p.collect(Client({'available':False}),self.snapshot())
        s=self.snapshot(); s['colonists'][0]['work_priorities']['Cooking']['disabled']=True
        self.assertNotIn("production_feed_batch",p.prepare(s,{}))
    def test_pending_flick_and_existing_bill_excluded(self):
        s=self.snapshot(); s['development']['production']['buildings'][0]['flick_pending']=True
        s['development']['production']['feed_tables'][0]['existing_bill']=True
        self.assertEqual([],p.prepare(s,{}))
    def test_revalidation_blocks_changed_policy(self):
        s=self.snapshot(); p.prepare(s,{})
        live=copy.deepcopy(s['development']['production']); live['buildings'][0]['switch_on']=False
        c=Client(live); r=p.execute(c,s,{},'production_utilities',{'production_policy':'2:switch_off'})
        self.assertFalse(r['applied']); self.assertEqual([],c.calls)
    def test_missing_applied_is_not_success(self):
        s=self.snapshot(); p.prepare(s,{})
        c=Client(s['development']['production']); r=p.execute(c,s,{},'production_utilities',{'production_policy':'2:switch_off'})
        self.assertFalse(r['applied']); self.assertEqual(1,len(c.calls))
    def test_defer_records_cooldown_without_api_mutation(self):
        s=self.snapshot(); c=Client({}); m={}
        r=p.execute(c,s,m,'production_feed_batch',{'production_policy':'defer'})
        self.assertFalse(r['applied']); self.assertEqual([],c.calls)
        self.assertEqual(20000,m['issued']['production:production_feed_batch'])
    def test_risk_and_defer_reach_native_choice(self):
        s=self.snapshot();p.prepare(s,{})
        with patch.object(p,'ask_laya_choice',return_value=('defer',{})) as ask:
            selected,_=p.choose(None,{},'production_utilities',s)
        args=ask.call_args.args
        self.assertIn('choice_context',args[1]);self.assertIn('risk',args[4]['2:switch_off']); self.assertIn('defer',args[4])
        self.assertEqual('defer',selected['production_policy'])

if __name__=='__main__':unittest.main()
