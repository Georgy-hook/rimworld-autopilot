"""Behavioral regressions for choices backed by active RimWorld capabilities."""
import copy
import json
import unittest

import colony_architect as architect
import colony_capabilities as caps
import colony_director as director
import rimworld_laya as bridge
from laya_decisions import ask_laya_choice


class Agent:
    def __init__(self, choices=None):
        self.choices = choices or {}
        self.calls = []

    def predict(self, state, questions):
        self.calls.append((copy.deepcopy(state), copy.deepcopy(questions)))
        question_id, question = next(iter(questions.items()))
        options = question["criteria"]
        root = question_id.split("_round_")[0]
        preferred = self.choices.get(root)
        choice = preferred if preferred in options else next((k for k in options if k != "defer"), next(iter(options)))
        return {"answers": {question_id: {"choice": choice, "confidence": 0.9, "probabilities": {choice: 1.0}}}}


class Client:
    def __init__(self, applied=True):
        self.calls = []
        self.applied = applied

    def post(self, endpoint, **kwargs):
        self.calls.append((endpoint, kwargs))
        return {"applied": self.applied, "reason": "queued" if self.applied else "current_requirements_changed"}


def snapshot():
    pawn = {"id": 1, "name": "Farmer", "position": {"x": 50, "z": 50}, "health": 1,
            "skills": {"Plants": {"level": 12}, "Animals": {"level": 8}, "Medicine": {"level": 10}},
            "work_priorities": {k: {"priority": 2, "disabled": False} for k in ("Growing", "PlantCutting", "Handling", "Doctor")}}
    fighter = {"id": 1, "name": "Farmer", "health": 1, "can_fight": True, "position": pawn["position"],
               "moving": 1, "manipulation": 1, "sight": 1, "shooting_skill": 12, "melee_skill": 3,
               "distance_to_nearest_opponent": 20, "weapon_range": 30, "has_ranged_weapon": True,
               "weapon_def": "Gun_AssaultRifle", "current_job": "Wait_Combat", "is_drafted": True}
    return {"game": {"tick": 60000, "is_paused": False}, "map": {"id": 0, "enemies": 0, "resources": {"food": 100, "meals": 100}},
            "colonists": [pawn], "animals": [], "combat": {"available": True, "colonists": [fighter], "hostiles": [], "available_weapons": []},
            "development": {"plants": [], "plant_catalog": {"plants": [], "growers": []}, "augmentation_context": {}, "building_catalog": []}}


def crop(name="Plant_Rice", *, safe=True, skill=0):
    return {"def_name": name, "label": name, "category": "food", "sowable": True, "minimum_skill": skill,
            "human_edible_product": True, "product_nutrition": .05,
            "safe_sowing_now": safe, "legal_cells": 9, "calendar_days_to_harvest_estimate": 6,
            "outdoor_warm_days_estimate": 12, "harvested_thing": "Rice", "harvest_yield": 6}


def growing_site(kind="ground", plant="Plant_Corn", **kwargs):
    return {"id": "zone:4" if kind == "ground" else "new_indoor_ground", "zone_id": 4 if kind == "ground" else None,
            "kind": kind, "plant_def": plant, "allow_sow": True, "roofed": False, "powered": True,
            "point_a": {"x": 52, "y": 0, "z": 52}, "point_b": {"x": 54, "y": 0, "z": 54}, **kwargs}


def augmentation(*, ready=True, count=1, efficiency=0.8):
    return {"patient_pawn_id": 1, "patient": "Farmer", "patient_role": "Growing=1; Plants=12; Shooting=0",
            "patient_beliefs": ["BodyPurist: Body purist", "BodyModification_Disapproved: disapproved"],
            "recipe_def": "InstallFieldHand", "label": "Install field hand", "body_part_index": 5, "body_part": "left shoulder",
            "current_efficiency": 1, "new_efficiency": efficiency, "implant_stock": {"FieldHand": count},
            "implant_defs": ["FieldHand"], "ready": ready, "reason": "available" if ready else "no_qualified_surgeon",
            "doctor_ids": [2], "bed_ids": [10], "doctor_details": {2: "Doctor: Medicine 10; surgery stat .8; manipulation 1"},
            "bed_details": {10: "hospital bed: surgery factor 1.2; clean, light, 21 C"}}


def animal(id=7, *, learned=True, hp=1, master=1):
    return {"id": id, "name": "Husky", "def": "Husky", "is_colony_animal": True, "health": hp, "hunger": 1,
            "master_pawn_id": master, "follow_drafted": True, "combat_power": 80, "minimum_handling_skill": 4,
            "position": {"x": 50, "z": 51}, "trainables": [
                {"def_name": "Obedience", "can_train": True, "learned": learned, "wanted": learned},
                {"def_name": "Release", "can_train": True, "learned": learned, "wanted": learned}]}


def greenhouse_catalog():
    return [{"def_name": name, "available_now": True, "size_x": 1, "size_z": 4 if name == "HydroponicsBasin" else 1,
             "cost_stuff_count": 5 if name in {"Wall", "Door"} else 0, "allowed_stuff_defs": ["WoodLog", "BlocksGranite"] if name in {"Wall", "Door"} else [],
             "nominal_power_consumption": {"SunLamp": 2900, "Heater": 175, "Cooler": 200, "HydroponicsBasin": 70}.get(name, 0),
             "cost_list": [{"thing_def": "Steel", "count": 100}] if name in {"SunLamp", "Heater", "HydroponicsBasin"} else [],
             "research_prerequisites": ["Hydroponics" if name == "HydroponicsBasin" else "Electricity"] if name not in {"Wall", "Door"} else []}
            for name in ("Wall", "Door", "SunLamp", "PowerConduit", "Heater", "Cooler", "HydroponicsBasin")]


class CapabilityTests(unittest.TestCase):
    def test_short_season_keeps_fast_crop_and_excludes_slow_or_illegal_crop(self):
        s = snapshot()
        rice, corn, mod = crop(), crop("Plant_Corn", safe=False), crop("ModPlant", safe=True, skill=18)
        s["development"]["plant_catalog"] = {"plants": [rice, corn, mod], "growers": [growing_site(options=[rice, corn, mod])]}
        plans = caps.crop_sites(s, False)
        self.assertEqual(set(plans["zone:4"]["crop_options"]), {"Plant_Rice"})

    def test_dynamic_mod_crop_is_not_restricted_by_a_python_allowlist(self):
        s = snapshot(); p = crop("ModBarley")
        s["development"]["plant_catalog"] = {"plants": [p], "growers": [growing_site(options=[p])]}
        self.assertIn("ModBarley", caps.crop_sites(s, False)["zone:4"]["crop_options"])

    def test_existing_healthy_crop_is_not_a_same_crop_exchange(self):
        s = snapshot(); p = crop()
        s["development"]["plant_catalog"] = {"plants": [p], "growers": [growing_site(plant=p["def_name"], options=[p])]}
        self.assertEqual(caps.crop_sites(s, False), {})

    def test_field_capacity_uses_edible_yield_and_current_viability(self):
        s = snapshot()
        rice = {**crop(), "human_edible_product": True, "product_nutrition": 0.05}
        hay = {**crop("Plant_Haygrass"), "human_edible_product": False, "product_nutrition": 0.05}
        s["development"]["plant_catalog"] = {"plants": [rice, hay], "growers": [
            growing_site(plant=rice["def_name"], options=[rice], blighted_count=3),
            growing_site(plant=hay["def_name"], options=[hay]),
            growing_site(kind="new_ground", plant=rice["def_name"], options=[rice]),
            growing_site(plant=rice["def_name"], options=[{**rice, "safe_sowing_now": False}])
        ]}
        self.assertAlmostEqual(caps.crop_nutrition_estimate(s), 0.3)

    def test_winter_only_pauses_outdoor_field_keeps_heated_greenhouse(self):
        s = snapshot(); outside = growing_site(options=[crop("Plant_Corn", safe=False)])
        inside = growing_site(plant="Plant_Rice", id="zone:5", zone_id=5, roofed=True, allow_sow=False, options=[crop()])
        s["development"]["plant_catalog"]["growers"] = [outside, inside]
        self.assertEqual(caps.seasonal_zones(s), ([4], [5]))

    def test_no_light_and_unpowered_basin_cannot_be_native_sow_options(self):
        s = snapshot(); p = crop(safe=False)
        s["development"]["plant_catalog"] = {"plants": [p], "growers": [growing_site(kind="hydroponics", powered=False, options=[p])]}
        self.assertEqual(caps.crop_sites(s, False), {})

    def test_create_uses_model_selected_real_crop_and_rectangle(self):
        s = snapshot(); p = crop("ModBarley")
        site = growing_site(kind="new_ground", plant=None, options=[p], roofed=True)
        s["development"]["plant_catalog"] = {"plants": [p], "growers": [site]}
        caps.prepare(s, {})
        choices, _ = caps.choose(Agent(), {}, "create_growing_zone", s)
        client = Client(); result = caps.execute(client, s, {}, "create_growing_zone", choices)
        self.assertTrue(result["applied"])
        body = client.calls[0][1]["body"]
        self.assertEqual(body["plant_def"], "ModBarley")
        self.assertEqual(body["point_a"], site["point_a"])

    def test_native_zone_dto_enables_priority_zero_grower_after_acceptance(self):
        s=snapshot(); s['colonists'][0]['work_priorities']['Growing']['priority']=0
        p=crop(); site=growing_site(kind='new_ground',plant=None,options=[p])
        s['development']['plant_catalog']={'plants':[p],'growers':[site]}
        caps.prepare(s,{})
        selected={'crop_site':site['id'],'crop_type':p['def_name'],'crop_worker':'1'}
        client=Client()
        def post(endpoint, **kwargs):
            client.calls.append((endpoint,kwargs))
            return {'zone':{'id':8,'cells_count':9},'plant_def_name':p['def_name']} if endpoint.endswith('/growing') else {'success':True}
        client.post=post
        self.assertTrue(caps.execute(client,s,{},'create_growing_zone',selected)['applied'])
        self.assertEqual(client.calls[-1][1]['body'],{'id':1,'work':'Growing','priority':1})

    def test_empty_or_string_applied_never_claims_accepted_crop_or_changes_work(self):
        s=snapshot(); p=crop(); site=growing_site(kind='new_ground',plant=None,options=[p])
        s['development']['plant_catalog']={'plants':[p],'growers':[site]};caps.prepare(s,{})
        for response in ({}, {'applied':'false'}):
            client=Client()
            def post(endpoint, **kwargs):
                client.calls.append((endpoint,kwargs));return response
            client.post=post
            result=caps.execute(client,s,{},'create_growing_zone',{'crop_site':site['id'],'crop_type':p['def_name'],'crop_worker':'1'})
            self.assertFalse(result['applied']);self.assertEqual(len(client.calls),1)

    def test_rejected_harvest_does_not_enable_worker(self):
        s=snapshot(); s['development']['plants']=[{'thing_id':5,'harvestable_now':True,'dying':True}]
        caps.prepare(s,{});client=Client(applied=False)
        self.assertFalse(caps.execute(client,s,{},'harvest_at_risk_crops',{'harvest_worker':'1'})['applied'])
        self.assertEqual(len(client.calls),1)

    def test_blight_selects_infected_only_and_does_not_interrupt_doctor(self):
        s = snapshot(); s["development"]["plants"] = [{"thing_id": 5, "blighted": True}, {"thing_id": 6, "blighted": False}]
        actions = caps.prepare(s, {})
        self.assertIn("clear_plant_blight", actions)
        choices, _ = caps.choose(Agent(), {}, "clear_plant_blight", s)
        client = Client(); caps.execute(client, s, {}, "clear_plant_blight", choices)
        self.assertEqual(client.calls[0][1]["body"]["plant_ids"], [5])
        s["colonists"][0]["current_job"] = "TendPatient"
        self.assertNotIn("clear_plant_blight", caps.prepare(s, {}))

    def test_api_skip_does_not_raise_work_priority_or_claim_blight_done(self):
        s = snapshot(); s["development"]["plants"] = [{"thing_id": 5, "blighted": True}]
        caps.prepare(s, {}); client = Client(applied=False)
        result = caps.execute(client, s, {}, "clear_plant_blight", {"blight_worker": "1"})
        self.assertFalse(result["applied"])
        self.assertEqual(len(client.calls), 1)

    def test_dying_yield_can_be_saved_but_blight_is_not_harvested(self):
        s = snapshot(); s["development"]["plants"] = [
            {"thing_id": 5, "harvestable_now": True, "dying": True},
            {"thing_id": 6, "harvestable_now": True, "dying": True, "blighted": True}]
        self.assertIn("harvest_at_risk_crops", caps.prepare(s, {}))
        client = Client(); caps.execute(client, s, {}, "harvest_at_risk_crops", {"harvest_worker": "1"})
        self.assertEqual(client.calls[0][1]["body"]["plant_ids"], [5])

    def test_empty_stock_never_offers_installation(self):
        s = snapshot(); s["development"]["augmentation_context"] = {"options": [augmentation(count=0)]}
        self.assertNotIn("plan_colonist_augmentation", caps.prepare(s, {}))

    def test_field_hand_with_lower_efficiency_stays_a_native_role_choice(self):
        s = snapshot(); s["development"]["augmentation_context"] = {"options": [augmentation()], "catalog": [
            {"recipe_def": "InstallFieldHand", "benefits": ["PlantWorkSpeed offset 1.60", "Moving offset -0.08"]}]}
        self.assertIn("plan_colonist_augmentation", caps.prepare(s, {}))
        agent = Agent(); choices, _ = caps.choose(agent, {}, "plan_colonist_augmentation", s)
        self.assertEqual(choices["augmentation_operation"], "1|InstallFieldHand|5")
        visible = str(agent.calls)
        self.assertIn("BodyPurist", visible); self.assertIn("Growing=1", visible); self.assertIn("PlantWorkSpeed", visible)
        client = Client(); caps.execute(client, s, {}, "plan_colonist_augmentation", choices)
        self.assertEqual(client.calls[0][0], "/api/v1/medical/augmentation")
        self.assertEqual(client.calls[0][1]["body"]["body_part_index"], 5)
        self.assertFalse(any("amput" in str(c).lower() for c in client.calls))

    def test_native_patient_defer_does_not_touch_game(self):
        s = snapshot(); s["development"]["augmentation_context"] = {"options": [augmentation()]}
        caps.prepare(s, {}); choices, _ = caps.choose(Agent({"augmentation_patient": "defer"}), {}, "plan_colonist_augmentation", s)
        client = Client(); result = caps.execute(client, s, {}, "plan_colonist_augmentation", choices)
        self.assertFalse(result["applied"]); self.assertEqual(client.calls, [])

    def test_native_can_defer_for_surgeon_risk(self):
        s = snapshot(); s["development"]["augmentation_context"] = {"options": [augmentation()]}
        caps.prepare(s, {}); choices, _ = caps.choose(Agent({"augmentation_doctor": "defer"}), {}, "plan_colonist_augmentation", s)
        self.assertTrue(choices["augmentation_defer"])

    def test_stock_without_safe_surgeon_is_considered_but_not_installed(self):
        s = snapshot(); s["development"]["augmentation_context"] = {"options": [augmentation(ready=False)]}
        self.assertIn("plan_colonist_augmentation", caps.prepare(s, {}))
        choices, _ = caps.choose(Agent(), {}, "plan_colonist_augmentation", s)
        client = Client(); caps.execute(client, s, {}, "plan_colonist_augmentation", choices)
        self.assertEqual(client.calls, [])

    def test_queued_surgery_is_not_repeated(self):
        s = snapshot(); op = augmentation(); op["already_queued"] = True
        s["development"]["augmentation_context"] = {"options": [op]}
        self.assertNotIn("plan_colonist_augmentation", caps.prepare(s, {}))

    def test_weapon_compatibility_checks_biocoding_shields_and_game_restrictions(self):
        p = {"id": 1, "can_fight": True}
        for w in ({"biocoded_pawn_id": 2}, {"compatible_pawn_ids": []}, {"equippable": False}):
            self.assertFalse(caps.weapon_compatible(p, w))
        self.assertFalse(caps.weapon_compatible({**p, "has_shield_belt": True}, {"is_ranged": True}))

    def test_weapon_comparison_uses_quality_stats_not_price(self):
        p = {"id": 1, "shooting_skill": 15}
        good = {"is_ranged": True, "damage": 20, "range": 30, "accuracy_medium": .8, "warmup": 1, "cooldown": 1, "market_value": 10}
        expensive = {**good, "damage": 5, "accuracy_medium": .3, "market_value": 10000}
        self.assertGreater(caps.weapon_score(p, good), caps.weapon_score(p, expensive))
        self.assertEqual(caps.weapon_score(p, {**good, "emp": True}), 0)

    def test_live_purchase_menu_exposes_parts_weapons_and_actual_wood_stock(self):
        trader = {"stock": [
            {"def_name": "FieldHand", "is_implant": True, "count": 1, "description": "PlantWorkSpeed 1.6; Moving -0.08"},
            {"def_name": "ModCarbine", "is_weapon": True, "count": 1, "description": "range 30; AP .3; quality 5"},
            {"def_name": "WoodLog", "count": 100},
        ]}
        menu = director.live_purchase_options(trader, 2)
        self.assertEqual(set(menu), {"none", "implant:FieldHand", "weapon:ModCarbine", "wood"})
        self.assertIn("Moving -0.08", menu["implant:FieldHand"])
        self.assertIn("quality 5", menu["weapon:ModCarbine"])

    def test_specialist_weapon_is_a_native_option_and_can_be_deferred(self):
        s = snapshot()
        s["combat"]["available_weapons"] = [{"id": 9, "def_name": "ModPulseLauncher", "is_ranged": True,
            "emp": True, "range": 20, "position": {"x": 50, "z": 50}}]
        self.assertIn("improve_weapon_loadout", caps.prepare(s, {}))
        chosen, _ = caps.choose(Agent({"weapon_item": "defer"}), {}, "improve_weapon_loadout", s)
        client = Client()
        self.assertFalse(caps.execute(client, s, {}, "improve_weapon_loadout", chosen)["applied"])
        self.assertEqual(client.calls, [])
        self.assertFalse(director.execute_action(client, s, {"anchor": {"x": 50, "z": 50}, "issued": {}}, "equip_colonists", chosen)["applied"])
        self.assertEqual(client.calls, [])

    def test_new_training_is_a_plan_not_learned_and_pen_animals_are_excluded(self):
        s = snapshot(); dog = animal(learned=False); dog["master_pawn_id"] = None
        cow = {**animal(id=8, learned=False), "trainables": [{"def_name": "Release", "can_train": False}]}
        s["animals"] = [dog, cow]
        self.assertIn("assign_animal_training", caps.prepare(s, {}))
        self.assertEqual(set(s["development"]["capability_plans"]["assign_animal_training"]), {"7"})
        self.assertNotIn("assign_animal_master", s["development"]["capability_plans"])
        self.assertEqual(caps.combat_animals(s), [])

    def test_bond_without_master_does_not_make_combat_animal(self):
        s = snapshot(); dog = animal(master=None); dog["bonded_pawn_id"] = 1
        s["animals"] = [dog]
        self.assertEqual(caps.combat_animals(s), [])

    def test_release_group_with_one_wounded_animal_is_not_offered(self):
        s = snapshot(); s["animals"] = [animal(), animal(id=8, hp=.3)]
        self.assertEqual(caps.combat_animals(s), [])

    def test_downing_master_blocks_attack_but_still_allows_recall(self):
        s = snapshot(); a = animal(); a["animals_released"] = True
        s["animals"] = [a]; s["combat"]["colonists"][0]["is_downed"] = True
        self.assertEqual(caps.combat_animals(s), [])
        self.assertEqual([p["id"] for p in caps.combat_animals(s, released=True)], [7])

    def test_release_order_drafts_master_and_never_drafts_animal(self):
        s = snapshot(); s["animals"] = [animal()]; s["map"]["enemies"] = 1
        s["combat"]["hostiles"] = [{"id": 99, "health": 1, "current_job": "AttackMelee", "position": {"x": 60, "z": 50}}]
        action = bridge.plan_action(s, {"choice": "release_trained_animals", "animal_master_id": 1})
        draft = [c["body"]["pawn_id"] for c in action["commands"] if c["endpoint"].endswith("edit/status")]
        self.assertEqual(draft, [1])
        self.assertTrue(any(c["endpoint"].endswith("animals/release") and c["body"]["release"] for c in action["commands"]))

    def test_stand_down_recalls_released_animals(self):
        s = snapshot(); dog = animal(); dog["animals_released"] = True; s["animals"] = [dog]
        action = bridge.plan_action(s, {"choice": "stand_down"})
        self.assertEqual(action["commands"][0]["endpoint"], "/api/v1/combat/animals/release")
        self.assertFalse(action["commands"][0]["body"]["release"])

    def test_tundra_research_uses_prerequisite_frontier_not_locked_target(self):
        s = snapshot(); s["development"].update(greenhouse_context={"short_season": True, "settled": True, "missing_research": ["Hydroponics"]},
            research_tree=[{"name": "Hydroponics", "prerequisites": ["Electricity"], "can_start_now": False},
                           {"name": "Electricity", "can_start_now": True, "player_has_any_appropriate_research_bench": True}])
        self.assertIn("research_greenhouse", caps.prepare(s, {}))
        self.assertEqual(set(s["development"]["capability_plans"]["research_greenhouse"]), {"Electricity"})
        choices, _ = caps.choose(Agent({"greenhouse_research": "defer"}), {}, "research_greenhouse", s)
        client = Client(); caps.execute(client, s, {}, "research_greenhouse", choices)
        self.assertEqual(client.calls, [])

    def test_greenhouse_research_does_not_restart_existing_useful_project(self):
        s = snapshot(); s["development"].update(greenhouse_context={"short_season": True, "settled": True, "missing_research": ["Electricity"]},
            research_tree=[{"name": "Electricity", "can_start_now": True}], current_research={"name": "Electricity"})
        self.assertNotIn("research_greenhouse", caps.prepare(s, {}))

    def test_all_detailed_comparison_options_reach_native_model(self):
        options = {str(i): f"Role effect {i}, complete patient ideology and physician risk details" for i in range(17)}
        agent = Agent(); ask_laya_choice(agent, {"urgent_food": 10}, "part", "Choose part", options, detailed=True)
        seen = {k for state, _ in agent.calls for k in state["alternatives"]}
        self.assertEqual(seen, set(options))
        self.assertTrue(all(len(state["alternatives"]) <= 2 for state, _ in agent.calls))

    def test_long_comparison_keeps_both_alternatives_inside_encoder_budget(self):
        class Tokenizer:
            def __call__(self, text, **kwargs):
                count = (len(text) + 3) // 4
                return {"input_ids": list(range(min(count, kwargs.get("max_length", count))))}

        agent = Agent(); agent.tok = Tokenizer(); agent.cfg = {"max_len": 512, "head_max_len": 192}
        options = {"FieldHand": "PlantWorkSpeed bonus; Moving penalty; " + "detail " * 300,
                   "ArchotechArm": "Manipulation bonus; combat benefit; " + "detail " * 300}
        ask_laya_choice(agent, {"choice_context": {"patient": "BodyPurist farmer; surgery failure risk"},
                               "large_colony": "history " * 1000}, "part", "Choose part", options, detailed=True)
        visible = agent.calls[-1][0]
        self.assertLessEqual(len(agent.tok(json.dumps(visible, ensure_ascii=False))["input_ids"]), 312)
        self.assertEqual(set(visible["alternatives"]), set(options))
        self.assertIn("BodyPurist", visible["decision_facts"]["patient"])
        self.assertIn("PlantWorkSpeed", visible["alternatives"]["FieldHand"])
        self.assertIn("Manipulation", visible["alternatives"]["ArchotechArm"])


class GreenhouseTests(unittest.TestCase):
    def context(self):
        return {"building_catalog": greenhouse_catalog(), "item_counts": {"WoodLog": 1000, "Steel": 4000},
                "material": "WoodLog", "colonists": [{"id": 1}], "sheltered_beds": 1,
                "finished_research": ["Electricity", "Hydroponics"], "climate": "cold", "biome": "Tundra"}

    def test_no_greenhouse_before_research_or_human_shelter(self):
        context = self.context(); context["sheltered_beds"] = 0
        self.assertEqual(architect.generate_program_variants("greenhouse_soil", context), {})
        context = self.context(); next(r for r in context["building_catalog"] if r["def_name"] == "SunLamp")["available_now"] = False
        self.assertEqual(architect.generate_program_variants("greenhouse_soil", context), {})

    def test_soil_greenhouse_needs_no_hydroponic_research_and_has_no_floor(self):
        context = self.context(); next(r for r in context["building_catalog"] if r["def_name"] == "HydroponicsBasin")["available_now"] = False
        layouts = architect.generate_program_variants("greenhouse_soil", context)
        self.assertTrue(layouts)
        self.assertEqual(architect.generate_program_variants("greenhouse_hydroponics", context), {})
        layout = next(iter(layouts.values()))["layout"]
        self.assertEqual(layout["floors"], []); self.assertTrue(layout["roof"])
        self.assertEqual(architect.layout_anchor_conflicts(layout), [])

    def test_hydroponic_basin_footprints_paths_and_peak_power(self):
        variant = next(iter(architect.generate_program_variants("greenhouse_hydroponics", self.context()).values()))
        items = variant["layout"]["buildings"]
        basins = [i for i in items if i["def_name"] == "HydroponicsBasin"]
        occupied = set()
        for b in basins:
            self.assertEqual(b["rotation"], 1)
            cells = {(b["rel_x"] + dx, b["rel_z"]) for dx in (-1, 0, 1, 2)}
            self.assertFalse(cells & occupied); occupied |= cells
            self.assertTrue(all((x-6)**2 + (z-6)**2 < 6.5**2 for x, z in cells))
        self.assertEqual(len(occupied), 32)
        self.assertFalse(any(x == 6 for x, _ in occupied))
        self.assertEqual(variant["planned_power_w"], 3810)
        self.assertEqual(architect.greenhouse_context(self.context())["hydroponics_daytime_w"], 3810)
        warm = self.context(); warm.update(climate="temperate", biome="TemperateForest")
        self.assertEqual(architect.greenhouse_context(warm)["soil_daytime_w"], 2900)

    def test_hot_greenhouse_preserves_east_entry_and_external_exhaust(self):
        context = self.context(); context.update(climate="hot", entry_side="east", biome="Desert")
        variant = next(iter(architect.generate_program_variants("greenhouse_soil", context).values()))
        items = variant["layout"]["buildings"]
        # Door and cooler must be on different cells so access cannot be lost.
        doors = {(i["rel_x"], i["rel_z"]) for i in items if i["def_name"] == "Door"}
        coolers = {(i["rel_x"], i["rel_z"]) for i in items if i["def_name"] == "Cooler"}
        self.assertEqual(len(doors), 1)
        self.assertFalse(doors & coolers)

    def test_resource_budget_includes_basins_and_lamp(self):
        context = self.context(); context["item_counts"]["Steel"] = 300
        variants = architect.generate_program_variants("greenhouse_hydroponics", context)
        self.assertEqual(architect.affordable_variants(variants, context), {})


if __name__ == "__main__":
    unittest.main()
