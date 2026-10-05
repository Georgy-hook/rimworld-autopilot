import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import colony_inspirations as inspirations
import colony_production as production
import colony_professions as professions
import colony_director as director


def pair(target=90,worker=2,inspiration="Inspired_Taming",identity="actual-session"):
    return {"key":f"{target}:{worker}","target_id":target,"worker_id":worker,"label":f"Megasloth by Handler{worker}",
            "expected_inspiration":inspiration,"expected_identity":identity,"expected_start_tick":100,
            "animals_skill":8,"minimum_skill":8,"value":1000,"wildness":.8,"revenge_on_failure":.1,
            "remaining_ticks":40000,"guaranteed_attempt":inspiration=="Inspired_Taming","food_count":8,"food_id":45,
            "products":"trainable Haul; meat 180; leather 80"}


def snapshot():
    return {"map":{"id":1,"resources":{"food":60}},"game":{"tick":1000},"colonists":[{"id":2,"name":"Handler","inspiration":"Inspired_Taming"}],
            "development":{"inspirations":{"available":True,"pawns":[],"taming":{"available":True,"options":[pair()]},
                        "recruitment":{"available":True,"options":[]}}}}


class NativeClient:
    def __init__(self,rows=None,response=None,lost_ack=False):
        self.rows=copy.deepcopy(rows if rows is not None else [pair()]);self.response=response or {"applied":True,"job_assigned":True}
        self.calls=[];self.jobs={};self.lost_ack=lost_ack
    def get(self,path,**kwargs):
        if path.endswith("context"):
            return {"available":True,"pawns":[{"pawn_id":w,"def_name":"Inspired_Taming","identity":"actual-session",**job} for w,job in self.jobs.items()],"definitions":[]}
        return {"available":True,"options":copy.deepcopy(self.rows)}
    def post(self,path,**kwargs):
        self.calls.append((path,copy.deepcopy(kwargs["body"])))
        if self.response.get("applied") is True:
            body=kwargs["body"];self.jobs[body["worker_id"]]={"current_job":"Tame" if path.endswith("tame") else "PrisonerAttemptRecruit","current_job_target_id":body["target_id"]}
            self.rows=[p for p in self.rows if p["worker_id"]!=body["worker_id"] and p["target_id"]!=body["target_id"]]
        if self.lost_ack:raise TimeoutError("lost acknowledgement")
        return copy.deepcopy(self.response)


class InspirationContractTests(unittest.TestCase):
    def test_exact_taming_director_execution_persists_job_across_eight_cycles(self):
        s=snapshot();memory={"anchor":{"x":10,"z":10},"issued":{}};client=NativeClient()
        for cycle in range(8):
            s["game"]["tick"]+=4500
            s["development"]["inspirations"]=inspirations.collect(client,s)
            plans=inspirations.ready_pairs(inspirations.tame_options(s),memory,s)
            if plans:
                p=plans["90:2"]
                result=director.execute_action(client,s,memory,"start_taming",{"tame_pair":p["key"],"tame_options":[p]})
                self.assertTrue(result["applied"])
            else:self.assertIn(2,client.jobs)
            memory=json.loads(json.dumps(memory))
        self.assertEqual(len(client.calls),1)
        self.assertEqual(client.calls[0][1]["worker_id"],2)
        self.assertEqual(client.calls[0][1]["expected_identity"],"actual-session")
        self.assertNotIn("expected_start_tick",client.calls[0][1])
        self.assertNotIn("map/animal/tame",client.calls[0][0])

    @patch("colony_retry.time.time")
    def test_failed_pair_60second_floor_new_pair_bypass_and_rollback(self,clock):
        s=snapshot();memory={};client=NativeClient(response={"applied":False,"reason":"reservation unavailable"})
        clock.return_value=100
        for cycle in range(8):
            clock.return_value=100+cycle*5;s["game"]["tick"]+=4500
            rows=inspirations.ready_pairs({p["key"]:p for p in client.rows},memory,s)
            if rows:inspirations.exact_order(client,s,next(iter(rows.values())),"tame",memory)
            memory=json.loads(json.dumps(memory))
        self.assertEqual(len(client.calls),1)
        new=pair(target=91)
        self.assertIn(new["key"],inspirations.ready_pairs({new["key"]:new},memory,s))
        clock.return_value=161
        self.assertIn("90:2",inspirations.ready_pairs({"90:2":pair()},memory,s))
        inspirations.exact_order(client,s,pair(),"tame",memory)
        s["game"]["tick"]=10
        self.assertIn("90:2",inspirations.ready_pairs({"90:2":pair()},memory,s))

    def test_unknown_post_observes_exact_job_without_reissuing(self):
        s=snapshot();client=NativeClient(lost_ack=True);memory={}
        result=inspirations.exact_order(client,s,pair(),"tame",memory)
        self.assertTrue(result["applied"])
        self.assertEqual(result["reason"],"exact_job_observed_after_lost_ack")
        for _ in range(8):
            self.assertFalse(inspirations.ready_pairs({"90:2":pair()},memory,s))
        self.assertEqual(len(client.calls),1)

    def test_inspiration_expiry_or_new_same_def_session_reconsiders_without_failure_latch(self):
        for changed in (pair(inspiration="",identity=""),pair(identity="new-session")):
            s=snapshot();memory={};client=NativeClient([changed])
            result=inspirations.exact_order(client,s,pair(),"tame",memory)
            self.assertTrue(result["reconsider"]);self.assertFalse(client.calls)
            self.assertIn(changed["key"],inspirations.ready_pairs({changed["key"]:changed},memory,s))

    def test_start_tick_and_remaining_age_drift_do_not_replace_native_identity(self):
        p=pair();changed={**p,"expected_start_tick":101,"remaining_ticks":39999}
        c=NativeClient([changed]);self.assertTrue(inspirations.exact_order(c,snapshot(),p,"tame",{})["applied"])

    def test_independent_endpoint_failure_keeps_taming_and_clears_expired_pawn_context(self):
        s=snapshot();s["colonists"][0]["inspiration_context"]={"identity":"stale"}
        class Client(NativeClient):
            def get(self,path,**kwargs):
                if path.endswith("recruitment"):raise TimeoutError("read failed")
                return super().get(path,**kwargs)
        data=inspirations.collect(Client(),s)
        self.assertFalse(data["endpoint_status"]["recruitment"]["available"])
        self.assertEqual(len(data["taming"]["options"]),1)
        self.assertEqual(s["colonists"][0]["inspiration"],"")
        self.assertNotIn("inspiration_context",s["colonists"][0])

    def test_unavailable_minimum_skill_food_or_pen_never_synthesizes_taming(self):
        # Native context is the eligibility authority; no best-skill fallback fabricates readiness.
        s=snapshot();s["development"]["inspirations"]["taming"]["options"]=[]
        s["wild_animals"]=[{"id":90,"def":"Thrumbo","can_tame":True,"minimum_handling_skill":10}]
        s["colonists"][0]["skills"]={"Animals":{"level":20}}
        self.assertFalse(inspirations.tame_options(s))

    def test_all_eight_and_unknown_loaded_effects_reach_profession_context(self):
        names=["Frenzy_Work","Frenzy_Go","Frenzy_Shoot","Inspired_Trade","Inspired_Recruitment","Inspired_Taming","Inspired_Surgery","Inspired_Creativity","Mod_Unexpected"]
        pawns=[{"id":i,"name":name,"inspiration":name,"inspiration_context":{"effect":"native effect or unknown","remaining_ticks":40000},"skills":{}} for i,name in enumerate(names)]
        context=professions.profession_context(pawns,[])
        self.assertEqual({p["def"] for p in context["inspirations"]},set(names))
        descriptions=professions.direction_choice_descriptions(context)
        self.assertIn("Inspired_Taming",descriptions["animal_husbandry"])
        self.assertIn("Inspired_Creativity",descriptions["art_culture"])
        self.assertIn("Inspired_Surgery",descriptions["medicine_biotech"])
        self.assertIn("Inspired_Trade",descriptions["trade_diplomacy"])

    def test_exact_pair_choice_keeps_inspired_lower_skill_and_ordinary_higher_skill_alternatives(self):
        from laya_decisions import ask_laya_choice
        s=snapshot();inspired=pair();ordinary={**pair(worker=3,inspiration="",identity=""),"animals_skill":16}
        s["development"]["tame_options"]=[inspired,ordinary]
        question=director.subchoice_questions_for_action("start_taming",s)["tame_pair"]
        self.assertEqual(set(question["criteria"]),{"90:2","90:3","defer"})
        self.assertIn("guaranteed next attempt",question["criteria"]["90:2"])
        self.assertIn("ordinary chance",question["criteria"]["90:3"])
        agent=CachedAgent()
        chosen,raw=ask_laya_choice(agent,{},"tame_pair",question["instructions"],question["criteria"],detailed=True)
        self.assertIn(chosen,question["criteria"])
        for state in agent.calls:self.assertLessEqual(len(agent.tok(json.dumps(state,ensure_ascii=False))["input_ids"]),312)

    def test_recruitment_eight_actual_prepare_choose_execute_cycles_do_not_reissue(self):
        plan={**pair(inspiration="Inspired_Recruitment",identity="recruit-session"),"inspiration":"next qualifying recruit succeeds"}
        s=snapshot();client=NativeClient([plan]);memory={}
        for cycle in range(8):
            s["game"]["tick"]+=4500
            s["development"]["inspirations"]["recruitment"]={"available":True,"options":copy.deepcopy(client.rows)}
            actions=inspirations.prepare(s,memory)
            if actions:
                chosen,_=inspirations.choose(CachedAgent(),{"decision_facts":{"food":60}},actions[0],s)
                self.assertTrue(inspirations.execute(client,s,memory,actions[0],chosen)["applied"])
            memory=json.loads(json.dumps(memory))
        self.assertEqual(len(client.calls),1)
        self.assertEqual(client.calls[0][0],"/api/v1/inspirations/recruit")



def recipe(value=300,material="WoodLog",worker=2,identity="creative-session"):
    w={"worker_id":worker,"label":"Artist","skill":14,"work_speed":1,"expected_inspiration":"Inspired_Creativity","expected_identity":identity,
       "inspiration":{"effect":"next actual quality +2","remaining_ticks":40000}}
    return {"key":f"8:Make_SculptureLarge:{material}","building_id":8,"recipe":"Make_SculptureLarge","material":material,"category":"art",
            "label":f"Large sculpture {material}","products":"SculptureLarge x1","worker_ids":[worker],"workers":[w],"quality_bearing":True,
            "normal_product_value":value,"work_amount":24000,"relevant_skill":"Artistic",
            "ingredient_budget":[{"alternatives":[{"required":100,"def_name":material,"reservable_count":110,"unit_value":1.2}]}]}


class RecipeClient:
    def __init__(self,plans):self.plans=copy.deepcopy(plans);self.calls=[];self.stock=110;self.completed=[]
    def get(self,*args,**kwargs):return {"available":True,"options":copy.deepcopy(self.plans)}
    def post(self,path,**kwargs):
        body=kwargs["body"];self.calls.append((path,copy.deepcopy(body)))
        # Fake queued native outcome is applied to subsequent observations, never called completed here.
        self.plans=[p for p in self.plans if p["key"]!=body["key"]]
        return {"applied":True,"pawn_restricted":True,"worker_id":body["worker_id"],"job_assigned":True,"reason":"bill_accepted_not_produced"}


class CachedAgent:
    cfg={"max_len":512,"head_max_len":192}
    def __init__(self):
        from tokenizers import Tokenizer
        paths=list((Path.home()/".cache/huggingface/hub/models--convaiinnovations--laya/snapshots").glob("*/tokenizer/tokenizer.json"))
        if not paths:raise unittest.SkipTest("cached Laya tokenizer unavailable")
        self.tokenizer=Tokenizer.from_file(str(sorted(paths)[0]));self.calls=[]
    def tok(self,text,**kwargs):return {"input_ids":self.tokenizer.encode(text,add_special_tokens=False).ids}
    def predict(self,state,questions):
        self.calls.append(copy.deepcopy(state));key,q=next(iter(questions.items()))
        return {"answers":{key:{"choice":next(k for k in q["criteria"] if k!="defer")}}}


class CreativeProductionTests(unittest.TestCase):
    def test_actual_recipe_comparison_sees_creativity_before_worker_and_fits_312(self):
        p=recipe();small={**recipe(value=40),"key":"8:Make_SculptureSmall:WoodLog","recipe":"Make_SculptureSmall","label":"Small sculpture","products":"SculptureSmall x1","work_amount":8000}
        agent=CachedAgent();chosen,raw=production.recipe_choose(agent,{"recipe_context":{"options":[p,small]}},
             {"decision_facts":{"care_risks":{"bleed_rate_max":.9,"downed":1}}})
        self.assertEqual(chosen["production_worker"]["worker_id"],2)
        for stage in raw["stages"]:
            self.assertLessEqual(len(agent.tok(json.dumps(stage["visible_state"],ensure_ascii=False))["input_ids"]),312)
        for stage in raw["stages"][:3]:
            visible=json.dumps(stage["visible_state"])
            self.assertIn("Inspired_Creativity",visible)
        compared=str(agent.calls)
        self.assertIn("100 WoodLog",compared)
        self.assertIn("300",compared)
        self.assertIn("40",compared)

    def test_eight_cycles_observe_accepted_bill_and_only_later_completion(self):
        plan=recipe();c=RecipeClient([plan]);memory={};s={"map":{"id":1},"game":{"tick":1000},"colonists":[],"development":{}}
        for cycle in range(8):
            s["game"]["tick"]+=4500
            s["development"]["production"]={"recipe_context":c.get(),"buildings":[]}
            actions=production.prepare(s,memory)
            if "production_recipe_batch" in actions:
                choice,_=production.recipe_choose(CachedAgent(),s["development"]["production"])
                self.assertTrue(production.execute(c,s,memory,"production_recipe_batch",choice)["applied"])
                self.assertEqual(c.stock,110);self.assertFalse(c.completed)
            if cycle==3:
                # Explicit simulated game observation: recipe consumed 100 and produced one item now.
                c.stock-=100;c.completed.append("SculptureLarge")
            memory=json.loads(json.dumps(memory))
        self.assertEqual(len(c.calls),1)
        self.assertEqual(c.calls[0][1]["worker_id"],2)
        self.assertEqual(c.calls[0][1]["expected_identity"],"creative-session")
        self.assertEqual(c.stock,10);self.assertEqual(c.completed,["SculptureLarge"])

    def test_expired_creativity_reconsiders_ordinary_worker_without_sticky_failure(self):
        old=recipe();live=recipe(identity="");live["workers"][0]["expected_inspiration"]=""
        c=RecipeClient([live]);s={"map":{"id":1},"game":{"tick":1000},"development":{"production":{"recipe_context":{"options":[old]}}}}
        state={};result=production.execute(c,s,state,"production_recipe_batch",{"production_policy":old["key"],"production_worker":old["workers"][0]})
        self.assertTrue(result["reconsider"]);self.assertFalse(c.calls)
        self.assertNotIn("production_option_backoff",state)
        s["development"]["production"]["recipe_context"]["options"]=[live]
        chosen,_=production.recipe_choose(CachedAgent(),s["development"]["production"])
        self.assertTrue(production.execute(c,s,state,"production_recipe_batch",chosen)["applied"])

    def test_fresh_stock_or_worker_failure_does_not_queue_bill(self):
        old=recipe();s={"map":{"id":1},"game":{"tick":1000},"development":{"production":{"recipe_context":{"options":[old]}}}}
        for plans in ([],[{**old,"worker_ids":[3]}]):
            c=RecipeClient(plans)
            self.assertFalse(production.execute(c,s,{},"production_recipe_batch",{"production_policy":old["key"],"production_worker":old["workers"][0]})["applied"])
            self.assertEqual(c.stock,110);self.assertFalse(c.calls)


class SurgeryInspirationTests(unittest.TestCase):
    def test_applicable_nonmech_and_inapplicable_mech_are_explicit_in_actual_chooser(self):
        import colony_capabilities as caps
        from tests.test_capabilities import snapshot as surgery_snapshot,augmentation,Agent
        for applicable in (True,False):
            s=surgery_snapshot();operation=augmentation()
            inspiration={"expected_inspiration":"Inspired_Surgery","expected_identity":"surgery-session","remaining_ticks":40000,
                         "applicable":applicable,"multiplier":2 if applicable else 1,"patient_is_mech":not applicable}
            operation["doctor_inspirations"]={"2":inspiration}
            s["development"]["augmentation_context"]={"options":[operation]}
            caps.prepare(s,{})
            agent=Agent();chosen,_=caps.choose(agent,{},"plan_colonist_augmentation",s)
            self.assertEqual(chosen["augmentation_inspiration"],inspiration)
            self.assertIn(f"applicable {applicable}",str(agent.calls))
            class FreshNativeReject:
                calls=[]
                def post(self,path,**kwargs):
                    self.calls.append((path,kwargs["body"]))
                    return {"applied":False,"reason":"inspiration_changed_reconsider"}
            client=FreshNativeReject();memory={}
            result=caps.execute(client,s,memory,"plan_colonist_augmentation",chosen)
            self.assertTrue(result["reconsider"])
            self.assertEqual(len(client.calls),1)
            self.assertEqual(client.calls[0][1]["expected_identity"],"surgery-session")
            self.assertFalse(any("failed" in str(k) for k in memory.get("capability_dwell",{})))


if __name__=="__main__":unittest.main()
