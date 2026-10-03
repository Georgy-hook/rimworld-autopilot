"""Choices backed by live plant, implant, weapon and animal capabilities.

Catalogs describe all loaded definitions. Orders use present objects and normal
game work; knowing a definition does not imply owning or unlocking it.
"""
from __future__ import annotations

from typing import Any
import colony_retry as retry
import colony_combat as combat
from laya_decisions import ask_laya_choice

DESCRIPTIONS = {
    "create_growing_zone": "Choose a live sowable crop and a verified plot. Compare food urgency, soil, biome, seasonal harvest time and skill; crops can die before harvest.",
    "configure_crop": "Choose a crop for an existing ground field or hydroponics basin from actual legal options. Changing an occupied field can sacrifice its standing crop; keep it until harvest unless the change is needed.",
    "clear_plant_blight": "Cut actually blighted plants before infection spreads. Pause sowing in affected fields and favor cutting over new sowing for the selected worker. Preserve healthy plants and active medical care.",
    "plan_colonist_augmentation": "Choose a beneficial replacement or implant, patient, specific body part, qualified surgeon and recovery bed. Normal surgery consumes medicine and can fail; consider ideology, recovery and the lost defender.",
    "assign_animal_training": "Request a species-supported training such as obedience, release, rescue or hauling. Learning needs a capable handler, food and time; a designation is not completed training.",
    "assign_animal_master": "Assign an obedient animal to a capable master and enable following when drafted. A bond alone does not assign a master, and pen livestock cannot learn combat obedience.",
    "improve_weapon_loadout": "Choose a colonist and an actual compatible weapon using damage, accuracy, range, armor penetration, quality and shooting/melee skill. Avoid explosives near allies and EMP against ordinary flesh targets.",
    "research_greenhouse": "Compare researching actual prerequisites for roofed farming early in a short-season biome with continuing current research. Building comes later, after human shelter, power and supplies.",
    "harvest_at_risk_crops": "Harvest reachable dying crops that can already yield something before they die. This sacrifices later yield. Blighted crops must be cut instead.",
}
LABELS = {
    "configure_crop": "выбор культуры", "clear_plant_blight": "вырубка заражённых растений",
    "plan_colonist_augmentation": "улучшение колониста имплантом",
    "assign_animal_training": "обучение животного", "assign_animal_master": "назначение хозяина животного",
    "improve_weapon_loadout": "выбор оружия колонисту", "create_growing_zone": "посадка подходящей культуры",
    "research_greenhouse": "исследования для теплицы", "harvest_at_risk_crops": "спасение урожая",
}
ACTIONS = set(DESCRIPTIONS)
CARE_JOBS = {"TendPatient", "Rescue", "FeedPatient", "DoBill", "Deathrest", "Breastfeed",
             "BottleFeedBaby", "BreastfeedCarryToMom", "BringBabyToSafety", "BringBabyToSafetyUnforced",
             "CarryToMomAfterBirth", "BabySuckle", "BabyPlay", "PlayStatic", "PlayWalking", "PlayToys",
             "Lessongiving", "Lessonreceiving", "PrisonerInterrogateIdentity", "Ingest"}


def _prune(snapshot: dict[str, Any], memory: dict[str, Any]) -> None:
    tick, map_id = int(snapshot.get("game", {}).get("tick") or 0), int(snapshot["map"]["id"])
    for name in ("capability_history", "capability_auxiliary"):
        rows = memory.get(name)
        rows = rows if isinstance(rows, dict) else {}
        memory[name] = dict(list({k: v for k, v in rows.items() if isinstance(k, str) and isinstance(v, dict)
            and type(v.get("tick")) is int and type(v.get("duration")) is int
            and 0 < v["duration"] <= 15000 and type(v.get("map_id")) is int and v["map_id"] == map_id
            and retry.recent(v, tick, v["duration"])}.items())[-512:])


def _scope(action: str, key: str) -> str:
    # An implant operation shares patient dwell; choosing a different limb must
    # not immediately queue another operation on the same recovering patient.
    return action + ":" + (key.split("|")[0] if action == "plan_colonist_augmentation" else key)


def _selection_key(action: str, selected: dict[str, Any]) -> str:
    field = {"create_growing_zone": "crop_site", "configure_crop": "crop_site",
             "plan_colonist_augmentation": "augmentation_operation", "improve_weapon_loadout": "weapon_pawn",
             "assign_animal_training": "training_animal", "assign_animal_master": "training_animal",
             "research_greenhouse": "greenhouse_research"}.get(action)
    return str(selected.get(field, "")) if field else ""


def _remember(snapshot: dict[str, Any], memory: dict[str, Any], key: str, duration: int, failure: bool = False) -> None:
    memory.setdefault("capability_history", {})[key] = {"tick": int(snapshot["game"].get("tick") or 0),
        "map_id": int(snapshot["map"]["id"]), "duration": duration}
    if failure:
        memory["capability_history"][key].update(retry.failure_record(int(snapshot["game"].get("tick") or 0), 30))
    while len(memory["capability_history"]) > 512:
        del memory["capability_history"][next(iter(memory["capability_history"]))]


def workers(snapshot: dict[str, Any], work: str, minimum: int = 0) -> list[dict[str, Any]]:
    # These actions explicitly enable the selected worker after acceptance.
    # Priority zero is a reversible assignment, unlike an incapable work type.
    skill = {"Growing": "Plants", "PlantCutting": "Plants", "Handling": "Animals", "Doctor": "Medicine"}.get(work)
    return [p for p in snapshot.get("colonists") or []
            if not p.get("downed") and not p.get("dead") and not p.get("in_mental_state") and not p.get("is_drafted")
            and p.get("current_job") not in CARE_JOBS
            and work in (p.get("work_priorities") or {})
            and not (p["work_priorities"][work] or {}).get("disabled")
            and int(((p.get("skills") or {}).get(skill) or {}).get("level") or 0) >= minimum
            and not any(h.get("can_ever_kill") and isinstance(h.get("immunity"), (int, float))
                        and h["immunity"] < 1 for h in p.get("health_conditions") or [])]


def plant_definitions(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["def_name"]: p for p in (snapshot.get("development", {}).get("plant_catalog") or {}).get("plants") or []}


def crop_sites(snapshot: dict[str, Any], new: bool) -> dict[str, dict[str, Any]]:
    defs = plant_definitions(snapshot)
    result = {}
    for site in (snapshot.get("development", {}).get("plant_catalog") or {}).get("growers") or []:
        if (site.get("kind") == "new_ground") != new:
            continue
        if new and combat.errand_exposed(snapshot, site.get("point_a")):
            continue
        options = {}
        for option in site.get("options") or []:
            definition = defs.get(option.get("def_name")) or {}
            if (option.get("safe_sowing_now") and int(option.get("legal_cells") or 0) > 0
                    and workers(snapshot, "Growing", int(definition.get("minimum_skill") or 0))
                    and (new or option["def_name"] != site.get("plant_def"))):
                options[option["def_name"]] = {**definition, **option}
        if options:
            result[site["id"]] = {**site, "crop_options": options}
    return result


def crop_nutrition_estimate(snapshot: dict[str, Any]) -> float:
    """Potential daily field output, before disease, weather, lost labor or waste."""
    definitions = plant_definitions(snapshot)
    total = 0.0
    for site in (snapshot.get("development", {}).get("plant_catalog") or {}).get("growers") or []:
        if site.get("kind") == "new_ground":
            continue
        definition = definitions.get(site.get("plant_def")) or {}
        option = next((o for o in site.get("options") or [] if o.get("def_name") == site.get("plant_def")), {})
        days = float(option.get("calendar_days_to_harvest_estimate") or 0)
        if definition.get("human_edible_product") and days > 0 and option.get("safe_sowing_now"):
            cells = max(0, int(option.get("legal_cells") or 0) - int(site.get("blighted_count") or 0))
            total += cells * float(definition.get("harvest_yield") or 0) * float(definition.get("product_nutrition") or 0) / days
    return total


def seasonal_zones(snapshot: dict[str, Any]) -> tuple[list[int], list[int]]:
    pause, resume = [], []
    for site in (snapshot.get("development", {}).get("plant_catalog") or {}).get("growers") or []:
        if site.get("zone_id") is None:
            continue
        current = next((row for row in site.get("options") or [] if row.get("def_name") == site.get("plant_def")), None)
        if current is None:
            continue
        if not current.get("safe_sowing_now") and site.get("allow_sow"):
            pause.append(int(site["zone_id"]))
        elif current.get("safe_sowing_now") and site.get("allow_sow") is False:
            resume.append(int(site["zone_id"]))
    return pause, resume


def trainables(animal: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["def_name"]: row for row in animal.get("trainables") or []}


def combat_animals(snapshot: dict[str, Any], *, released: bool = False) -> list[dict[str, Any]]:
    raw = snapshot.get("combat", {}).get("colony_animals") or snapshot.get("animals") or []
    fighters = {int(p["id"]): p for p in snapshot.get("combat", {}).get("colonists") or []}
    result = []
    for animal in raw:
        master = fighters.get(int(animal.get("master_pawn_id") or -1))
        if not master or master.get("is_dead"):
            continue
        if released:
            if animal.get("animals_released"):
                result.append(animal)
        elif master.get("is_downed") or master.get("is_in_mental_state") or master.get("can_fight") is False:
            continue
        elif (animal.get("follow_drafted") and trainables(animal).get("Release", {}).get("learned")
              and master.get("current_job") not in CARE_JOBS
              and not animal.get("dead") and not animal.get("downed") and not animal.get("in_mental_state")
              and float(animal.get("health") or 0) >= 0.8 and float(animal.get("bleeding_rate") or 0) == 0
              and float(animal.get("hunger", 1)) > 0.2):
            result.append(animal)
    if not released:
        following = [a for a in raw if a.get("follow_drafted") and trainables(a).get("Release", {}).get("learned")]
        ready_ids = {a["id"] for a in result}
        unsafe_masters = {a.get("master_pawn_id") for a in following if a["id"] not in ready_ids}
        result = [a for a in result if a.get("master_pawn_id") not in unsafe_masters]
    return result


def weapon_compatible(pawn: dict[str, Any], weapon: dict[str, Any]) -> bool:
    if weapon.get("equippable") is False or pawn.get("can_fight") is False:
        return False
    if weapon.get("compatible_pawn_ids") is not None and int(pawn["id"]) not in weapon["compatible_pawn_ids"]:
        return False
    if weapon.get("biocoded_pawn_id") not in (None, 0, pawn["id"]):
        return False
    if weapon.get("is_ranged") and pawn.get("has_shield_belt"):
        return False
    return True


def weapon_note(weapon: dict[str, Any]) -> str:
    special = ",".join(k for k in ("emp", "explosive", "incendiary", "single_use") if weapon.get(k)) or "normal"
    return (f"{weapon.get('label') or weapon.get('def_name')} quality {weapon.get('quality')}; {special}; range {weapon.get('min_range', 0)}..{weapon.get('range', '?')}; "
            f"damage {weapon.get('damage', '?')} {weapon.get('damage_def')}; burst {weapon.get('burst_shots', 1)}; "
            f"armor penetration {weapon.get('armor_penetration', '?')}; accuracy near/short/mid/long "
            f"{weapon.get('accuracy_touch', '?')}/{weapon.get('accuracy_short', '?')}/"
            f"{weapon.get('accuracy_medium', '?')}/{weapon.get('accuracy_long', '?')}; "
            f"warmup/cooldown {weapon.get('warmup', '?')}/{weapon.get('cooldown', '?')}; melee DPS {weapon.get('melee_dps', '?')}; "
            f"condition {weapon.get('hit_points_percent')}")


def weapon_score(pawn: dict[str, Any], weapon: dict[str, Any], distance: float = 20, armored: bool = False) -> float:
    """Fallback for an equip order without an explicit model weapon selection."""
    if not weapon_compatible(pawn, weapon):
        return -1
    if not weapon.get("is_ranged"):
        return float(weapon.get("melee_dps") or 1) * (1 + int(pawn.get("melee_skill") or 0) / 20)
    if weapon.get("emp") or weapon.get("explosive") or weapon.get("incendiary") or weapon.get("single_use"):
        return 0  # Specialist weapons require an explicit choice, not a generic founder loadout.
    accuracy = float(weapon.get("accuracy_short" if distance < 15 else "accuracy_medium" if distance < 30 else "accuracy_long") or 0.5)
    chance = 0.9 + min(20, int(pawn.get("shooting_skill") or 0)) * 0.005
    accuracy *= chance ** max(1, distance)
    cycle = max(0.1, float(weapon.get("warmup") or 0) + float(weapon.get("cooldown") or 1))
    score = float(weapon.get("damage") or 1) * int(weapon.get("burst_shots") or 1) * accuracy / cycle
    if armored:
        score *= 1 + 3 * float(weapon.get("armor_penetration") or 0)
    if float(weapon.get("range") or 999) < distance or float(weapon.get("min_range") or 0) > distance:
        score *= 0.15
    return score


def safe_weapons(snapshot: dict[str, Any], pawn: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(w["id"]): w for w in snapshot.get("combat", {}).get("available_weapons") or []
            if w.get("id") is not None and w.get("id") != (pawn.get("weapon_info") or {}).get("id")
            and weapon_compatible(pawn, w) and not combat.errand_exposed(snapshot, w.get("position"), pawn.get("position"))}


def founder_weapon_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Project founder choices without duplicating eligibility or order logic."""
    dev = snapshot.get("development") or {}
    plans = {}
    for key, plan in (dev.get("capability_plans", {}).get("improve_weapon_loadout") or {}).items():
        pawn = plan.get("pawn") or {}
        if not pawn or pawn.get("has_ranged_weapon"):
            continue
        weapons = {k: w for k, w in plan["weapons"].items() if w.get("is_ranged")}
        if weapons:
            plans[key] = {**plan, "weapons": weapons}
    return {**snapshot, "development": {**dev, "capability_plans": {
        **(dev.get("capability_plans") or {}), "improve_weapon_loadout": plans}}}


def prepare(snapshot: dict[str, Any], map_state: dict[str, Any]) -> list[str]:
    _prune(snapshot, map_state)
    dev = snapshot["development"]
    actions = []
    plans = {}
    new_sites, old_sites = crop_sites(snapshot, True), crop_sites(snapshot, False)
    if new_sites:
        plans["create_growing_zone"] = new_sites
        actions.append("create_growing_zone")
    if old_sites:
        plans["configure_crop"] = old_sites
        actions.append("configure_crop")
    blight = [p for p in dev.get("plants") or [] if p.get("blighted") and not p.get("is_designated_for_cut")
              and not combat.errand_exposed(snapshot, p.get("position"))]
    if blight and workers(snapshot, "PlantCutting"):
        plans["clear_plant_blight"] = {"plants": blight, "workers": workers(snapshot, "PlantCutting")}
        actions.append("clear_plant_blight")
    at_risk = [p for p in dev.get("plants") or [] if p.get("harvestable_now") and not p.get("blighted")
               and not p.get("is_designated_for_harvest") and (p.get("dying") or p.get("dying_from_pollution") or p.get("dying_from_no_pollution"))
               and not combat.errand_exposed(snapshot, p.get("position"))]
    if at_risk and workers(snapshot, "PlantCutting"):
        plans["harvest_at_risk_crops"] = {"plants": at_risk, "workers": workers(snapshot, "PlantCutting")}
        actions.append("harvest_at_risk_crops")
    greenhouse = dev.get("greenhouse_context") or {}
    tree = {r["name"]: r for r in dev.get("research_tree") or []}
    missing = set(greenhouse.get("missing_research") or [])
    pending = list(missing)
    while pending:
        row = tree.get(pending.pop()) or {}
        for name in (row.get("prerequisites") or []) + (row.get("hidden_prerequisites") or []):
            if name not in missing and not tree.get(name, {}).get("is_finished"):
                missing.add(name)
                pending.append(name)
    current = str((dev.get("current_research") or {}).get("name") or "")
    frontier = {name: row for name, row in tree.items() if name in missing and not row.get("is_finished")
                and row.get("can_start_now") and row.get("player_has_any_appropriate_research_bench") is not False}
    if greenhouse.get("short_season") and greenhouse.get("settled") and frontier and current not in missing:
        plans["research_greenhouse"] = frontier
        actions.append("research_greenhouse")
    augment = dev.get("augmentation_context") or {}
    # Role bonuses can justify a lower limb efficiency (field hands/drill arms).
    # Keep those alternatives and defer; never propose an item that isn't owned.
    rows = [o for o in augment.get("options") or [] if not o.get("already_queued")
            and any(int(n or 0) > 0 for n in (o.get("implant_stock") or {}).values())]
    if rows:
        plans["plan_colonist_augmentation"] = {f"{o['patient_pawn_id']}|{o['recipe_def']}|{o['body_part_index']}": o for o in rows}
        actions.append("plan_colonist_augmentation")
    training, masters = {}, {}
    for animal in snapshot.get("animals") or []:
        if animal.get("dead") or animal.get("downed") or animal.get("in_mental_state") or float(animal.get("bleeding_rate") or 0) > 0:
            continue
        eligible = workers(snapshot, "Handling", int(animal.get("minimum_handling_skill") or 0))
        if not eligible:
            continue
        if combat.errand_exposed(snapshot, animal.get("position")):
            continue
        available = {name: t for name, t in trainables(animal).items()
                     if t.get("can_train") and not t.get("learned") and not t.get("wanted")}
        if available:
            training[str(animal["id"])] = {"animal": animal, "trainables": available, "workers": eligible}
        if trainables(animal).get("Obedience", {}).get("learned") and (not animal.get("master_pawn_id") or not animal.get("follow_drafted")):
            masters[str(animal["id"])] = {"animal": animal, "workers": eligible}
    for action, rows in (("assign_animal_training", training), ("assign_animal_master", masters)):
        if rows:
            plans[action] = rows
            actions.append(action)
    weapon_plans = {}
    protected = combat.protected_emergency_care_ids(snapshot)
    for pawn in snapshot.get("combat", {}).get("colonists") or []:
        if (pawn.get("is_dead") or pawn.get("is_downed") or pawn.get("is_in_mental_state")
                or pawn.get("current_job") in CARE_JOBS | {"Equip"} or pawn.get("id") in protected
                or float(pawn.get("manipulation", 1) or 0) < 0.65):
            continue
        weapons = safe_weapons(snapshot, pawn)
        current = pawn.get("weapon_info") or {}
        # Knowledge is complete; suppress repeated no-op exchanges for an equivalent gun.
        if weapons and (not pawn.get("weapon_def") or any(w.get("def_name") != pawn.get("weapon_def") or
                weapon_score(pawn, w) > weapon_score(pawn, current) * 1.15 or
                any(w.get(k) != current.get(k) for k in ("quality", "hit_points_percent", "damage", "armor_penetration", "melee_dps"))
                for w in weapons.values())):
            weapon_plans[str(pawn["id"])] = {"pawn": pawn, "weapons": weapons}
    if weapon_plans:
        plans["improve_weapon_loadout"] = weapon_plans
        actions.append("improve_weapon_loadout")
    dev["crop_purpose_context"] = map_state.get("pending_income_crop") or map_state.get("income_strategy") or "colony survival"
    history = map_state["capability_history"]
    for action in list(plans):
        if action in {"clear_plant_blight", "harvest_at_risk_crops"}:
            plans[action]["plants"] = [p for p in plans[action]["plants"]
                if _scope(action, str(p["thing_id"])) not in history]
            if not plans[action]["plants"]:
                del plans[action]
        else:
            plans[action] = {k: v for k, v in plans[action].items()
                if _scope(action, k) not in history and action + ":failed:" + k not in history}
            if not plans[action]:
                del plans[action]
    repairs = set()
    for key, pending in map_state["capability_auxiliary"].items():
        action = pending.get("action")
        if action in ACTIONS and action not in repairs and key + ":aux_failed" not in history and isinstance(pending.get("steps"), list):
            plans[action] = {"__auxiliary__": key}
            repairs.add(action)
    dev["capability_plans"] = plans
    return list(plans)


def choose(agent: Any, state: dict[str, Any], action: str, snapshot: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    plans = snapshot["development"].get("capability_plans", {}).get(action) or {}
    if "__auxiliary__" in plans:
        return {"auxiliary_retry": plans["__auxiliary__"]}, {"answers": {}, "steps": []}
    details, raw = {}, {"answers": {}, "steps": []}

    def pick(question: str, instruction: str, criteria: dict[str, str]) -> str:
        if not criteria:
            raise ValueError(f"No feasible {question} options")
        selected, result = ask_laya_choice(agent, state, question, instruction, criteria, detailed=True)
        if selected not in criteria:
            raise ValueError(f"Infeasible {question}: {selected}")
        details[question] = selected
        details.setdefault("shown_subjects", {})[question] = [k for k in criteria if k != "defer"]
        raw["answers"].update(result.get("answers", {}))
        raw["steps"].append(result)
        return selected

    def person_note(p: dict[str, Any]) -> str:
        return f"{p.get('name')}; skills {p.get('skills')}; health {p.get('health')}; job {p.get('current_job')}; priorities {p.get('work_priorities')}; traits {p.get('traits')}"

    if action in {"create_growing_zone", "configure_crop"}:
        key = pick("crop_site", "Choose a grower. Changing an occupied field may destroy crops before harvest.", {
            k: f"{p.get('kind')}; current {p.get('plant_def')}, {p.get('plant_count')} plants; roofed {p.get('roofed')}, powered {p.get('powered')}" for k, p in plans.items()})
        crops = plans[key]["crop_options"]
        state = {"choice_context": {"plot": {k: plans[key].get(k) for k in ("kind", "plant_def", "roofed", "powered", "plant_count")},
                                    "purpose": snapshot["development"].get("crop_purpose_context")}, "colony": state}
        groups = {str(p.get("category") or "other") for p in crops.values()}
        category = pick("crop_purpose", f"Choose food, feed, fuel, medicine, textiles, trade or decoration for this plot. Current economic/survival purpose: {snapshot['development'].get('crop_purpose_context')}. A purpose does not override season, food or legal options.", {
            g: ", ".join(name for name, p in crops.items() if str(p.get("category") or "other") == g) for g in sorted(groups)})
        name = pick("crop_type", "Choose an actual legal crop. Seasonal averages cannot predict cold snaps. Compare time to harvest with remaining outdoor warm days and current food need.", {
            name: f"{p.get('label')}; yields {p.get('harvest_yield')} {p.get('harvested_thing')}; harvest about {p.get('calendar_days_to_harvest_estimate'):.1f} calendar days, warm days {p.get('outdoor_warm_days_estimate')}; fertility {p.get('fertility')}, sensitivity {p.get('fertility_sensitivity')}; skill {p.get('minimum_skill')}; temp {p.get('min_growth_temperature')}..{p.get('max_growth_temperature')}; {p.get('description')}"
            for name, p in crops.items() if str(p.get("category") or "other") == category})
        pick("crop_worker", "Choose an eligible grower, comparing Plants skill and competing work.", {
            str(p["id"]): person_note(p) for p in workers(snapshot, "Growing", int(crops[name].get("minimum_skill") or 0))})
    elif action == "clear_plant_blight":
        pick("blight_worker", f"Cut {len(plans['plants'])} infected plants immediately; protect medical work.", {str(p["id"]): person_note(p) for p in plans["workers"]})
    elif action == "harvest_at_risk_crops":
        pick("harvest_worker", f"Save reachable yield from {len(plans['plants'])} dying crops before it is lost.", {str(p["id"]): person_note(p) for p in plans["workers"]})
    elif action == "research_greenhouse":
        greenhouse = snapshot["development"].get("greenhouse_context") or {}
        pick("greenhouse_research", "Choose a startable greenhouse prerequisite or keep current research. A short season favors early planning, but shelter, food and defense compete for time.", {
            "defer": "Continue current research; no project is changed.",
            **{name: f"{row.get('label')}; {row.get('research_points')} points; {row.get('description')}; later needs {greenhouse.get('required_buildings')}, roughly {greenhouse.get('soil_daytime_w')} W soil / {greenhouse.get('hydroponics_daytime_w')} W hydroponics plus a warm roofed room." for name, row in plans.items()}})
    elif action == "plan_colonist_augmentation":
        patients = {}
        for o in plans.values():
            relevant_beliefs = [b for b in o.get("patient_beliefs") or [] if any(
                term in b.lower() for term in ("body", "bionic", "organ", "pain", "scar", "transhuman", "modif", "purist"))]
            patients[str(o["patient_pawn_id"])] = (f"{o['patient']}; beliefs {relevant_beliefs}; {o.get('patient_role')}"
                if o.get("patient_role") else o.get("patient_context") or o["patient"])
        patients["defer"] = "Keep every current body part. Surgery, ideology penalties or loss of the doctor/worker may outweigh the benefits."
        patient = pick("augmentation_patient", "Choose a colonist or defer surgery. Compare assigned work, skill, specific role bonuses, body-purist/body-modder traits and this patient's own ideology/precepts. Anesthesia removes their labor and defense temporarily. Neither price nor limb efficiency alone determines suitability.", patients)
        if patient == "defer":
            details["augmentation_defer"] = True
            return details, raw
        catalog = {r["recipe_def"]: r for r in (snapshot["development"].get("augmentation_context") or {}).get("catalog") or []}
        state = {"choice_context": {"patient": patients[patient]}, "colony": state}
        options = {key: f"{o['label']}; benefits {catalog.get(o['recipe_def'], {}).get('benefits')}; efficiency {o.get('current_efficiency')} -> {o.get('new_efficiency')}; on {o['body_part']} replacing {o.get('current_implant')}; stock {o.get('implant_stock')}; ready {o.get('ready')}, blockers {o.get('reason')}, missing {o.get('missing_ingredients')}; {catalog.get(o['recipe_def'], {}).get('description') or ''}"
                   for key, o in plans.items() if str(o["patient_pawn_id"]) == patient}
        options["defer"] = "Preserve the current part and the stored implant; no operation now."
        key = pick("augmentation_operation", "Choose one exact part and implant or defer. Compare role bonuses and drawbacks with current limbs: a field hand can favor farming, a drill arm mining, while mobility/sight/manipulation can favor combat. These are alternatives, not mandatory role assignments. Installing replaces a limb in one operation; never amputate first.", options)
        if key == "defer" or not plans[key].get("ready"):
            details["augmentation_defer"] = True
            return details, raw
        operation = plans[key]
        state["choice_context"]["surgery"] = {"operation": operation["label"], "part": operation["body_part"],
            "medicines": operation.get("medicine_options"), "recipe_success_factor": catalog.get(operation["recipe_def"], {}).get("surgery_success_factor"),
            "risk": "anesthesia, failed installation, implant loss, injuries or death; success is not guaranteed"}
        doctors = {str(k): v for k, v in operation.get("doctor_details", {}).items()}
        doctors["defer"] = "Wait for a better surgeon or circumstances; failure can injure the patient and destroy the implant."
        if pick("augmentation_doctor", "Choose a surgeon or postpone. Compare Medicine, manipulation, raw surgery stat and competing patient care; low skill can waste an expensive implant. No success is guaranteed.", doctors) == "defer":
            details["augmentation_defer"] = True
            return details, raw
        pick("augmentation_bed", "Choose a roofed temperate bed. Prefer good surgical factor, cleanliness and light.", {str(k): v for k, v in operation.get("bed_details", {}).items()})
    elif action in {"assign_animal_training", "assign_animal_master"}:
        key = pick("training_animal", "Choose a healthy colony animal; supported training depends on species and age.", {k: f"{p['animal'].get('name')} {p['animal'].get('def')}; power {p['animal'].get('combat_power')}; learned {trainables(p['animal'])}" for k, p in plans.items()})
        plan = plans[key]
        if action == "assign_animal_training":
            pick("animal_trainable", "Choose a training. Prerequisites are requested recursively; actual learning takes food, handling and time.", {k: str(v) for k, v in plan["trainables"].items()})
        pick("animal_handler", "Choose a handler or master with sufficient Animals skill, health and spare time.", {str(p["id"]): person_note(p) for p in plan["workers"]})
    elif action == "improve_weapon_loadout":
        key = pick("weapon_pawn", "Choose a colonist by combat role, skill and health, or keep current loadouts.", {
            **{k: f"{p['pawn'].get('name')}; shooting {p['pawn'].get('shooting_skill')}, melee {p['pawn'].get('melee_skill')}; sight {p['pawn'].get('sight')}, manipulation {p['pawn'].get('manipulation')}; current {weapon_note(p['pawn'].get('weapon_info') or {})}" for k, p in plans.items()},
            "defer": "Keep existing loadouts; fetching another weapon may be unnecessary or risky."})
        if key == "defer":
            details["weapon_defer"] = True
            return details, raw
        state = {"choice_context": {
            "fighter": {k: plans[key]["pawn"].get(k) for k in ("shooting_skill", "melee_skill", "distance_to_nearest_opponent", "weapon_def")},
            "enemies": [{k: e.get(k) for k in ("kind_def", "armor_sharp", "is_mechanoid", "is_insect")}
                        for e in snapshot.get("combat", {}).get("hostiles") or [] if not e.get("is_dead")][:4]}, "colony": state}
        if pick("weapon_item", "Choose a compatible weapon or keep current one. Compare range, quality, damage, accuracy and AP with pawn skills and enemies. Explosives risk friendly fire; EMP does not replace normal damage.", {
                **{k: weapon_note(w) for k, w in plans[key]["weapons"].items()},
                "defer": "Keep current weapon: " + weapon_note(plans[key]["pawn"].get("weapon_info") or {})}) == "defer":
            details["weapon_defer"] = True
    return details, raw


def _execute_primary(client: Any, snapshot: dict[str, Any], map_state: dict[str, Any], action: str, selected: dict[str, Any]) -> dict[str, Any]:
    plans = snapshot["development"].get("capability_plans", {}).get(action) or {}
    map_id = int(snapshot["map"]["id"])
    response: Any = None

    def order(path: str, body: dict[str, Any]) -> Any:
        return client.post(path, body=body)

    def accepted(value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        if "applied" in value:
            return value["applied"] is True
        if action == "create_growing_zone":
            # This legacy endpoint returns GrowingZoneDto, not an applied flag.
            zone = value.get("zone") or {}
            return (value.get("plant_def_name") == selected.get("crop_type")
                    and isinstance(zone, dict) and int(zone.get("cells_count") or 0) > 0)
        if action == "research_greenhouse":
            return value.get("name") == selected.get("greenhouse_research")
        # Harvest/Equip use the non-generic ApiResult success envelope.
        return value.get("success") is True

    if action in {"create_growing_zone", "configure_crop"}:
        site = plans.get(str(selected.get("crop_site")))
        crop = str(selected.get("crop_type") or "")
        if not site or crop not in site["crop_options"]:
            return {"applied": False, "reason": "No verified crop and site selected"}
        eligible = {int(p["id"]) for p in workers(snapshot, "Growing", int(site["crop_options"][crop].get("minimum_skill") or 0))}
        worker = int(selected.get("crop_worker") or 0)
        if worker not in eligible:
            return {"applied": False, "reason": "No eligible grower selected"}
        if action == "create_growing_zone":
            response = order("/api/v1/map/zone/growing", {"map_id": map_id, "plant_def": crop, "point_a": site["point_a"], "point_b": site["point_b"]})
        else:
            response = order("/api/v1/map/zone/growing/crop", {"map_id": map_id, "plant_def": crop, "zone_id": site.get("zone_id"), "building_id": site.get("building_id")})
            if accepted(response) and site.get("zone_id") is not None and not site.get("allow_sow"):
                order("/api/v1/map/zone/growing/sowing", {"map_id": map_id, "zone_id": site["zone_id"], "allow_sow": True})
        if accepted(response):
            order("/api/v1/colonist/work-priority", {"id": worker, "work": "Growing", "priority": 1})
    elif action == "clear_plant_blight":
        worker = int(selected.get("blight_worker") or 0)
        if worker not in {int(p["id"]) for p in plans.get("workers") or []}:
            return {"applied": False, "reason": "No eligible cutter selected"}
        response = order("/api/v1/map/plants/cut-blight", {"map_id": map_id, "plant_ids": [p["thing_id"] for p in plans["plants"]], "worker_pawn_id": worker})
        if accepted(response):
            order("/api/v1/colonist/work-priority", {"id": worker, "work": "PlantCutting", "priority": 1})
            pawn = next(p for p in plans["workers"] if int(p["id"]) == worker)
            growing_priority = (pawn.get("work_priorities", {}).get("Growing") or {}).get("priority")
            if growing_priority is not None and 0 < int(growing_priority) < 3:
                order("/api/v1/colonist/work-priority", {"id": worker, "work": "Growing", "priority": 3})
    elif action == "harvest_at_risk_crops":
        worker = int(selected.get("harvest_worker") or 0)
        if worker not in {int(p["id"]) for p in plans.get("workers") or []}:
            return {"applied": False, "reason": "No eligible harvester selected"}
        response = order("/api/v1/map/plants/harvest", {"map_id": map_id, "plant_ids": [p["thing_id"] for p in plans["plants"]]})
        if accepted(response):
            order("/api/v1/colonist/work-priority", {"id": worker, "work": "PlantCutting", "priority": 1})
    elif action == "research_greenhouse":
        target = str(selected.get("greenhouse_research") or "")
        if target == "defer":
            return {"applied": False, "reason": "laya_kept_current_research"}
        if target not in plans:
            return {"applied": False, "reason": "No available greenhouse prerequisite selected"}
        response = client.post("/api/v1/research/target", query={"name": target, "force": False})
    elif action == "plan_colonist_augmentation":
        if selected.get("augmentation_defer"):
            return {"applied": False, "reason": "laya_deferred_elective_surgery", "selection": selected}
        operation = plans.get(str(selected.get("augmentation_operation")))
        doctor, bed = int(selected.get("augmentation_doctor") or 0), int(selected.get("augmentation_bed") or 0)
        if not operation or not operation.get("ready") or doctor not in operation.get("doctor_ids", []) or bed not in operation.get("bed_ids", []):
            return {"applied": False, "reason": "No verified patient, surgeon and bed selected"}
        response = order("/api/v1/medical/augmentation", {"map_id": map_id, "patient_pawn_id": operation["patient_pawn_id"], "doctor_pawn_id": doctor, "bed_id": bed, "recipe_def": operation["recipe_def"], "body_part_index": operation["body_part_index"]})
        if accepted(response):
            order("/api/v1/colonist/work-priority", {"id": doctor, "work": "Doctor", "priority": 1})
    elif action in {"assign_animal_training", "assign_animal_master"}:
        plan = plans.get(str(selected.get("training_animal")))
        worker = int(selected.get("animal_handler") or 0)
        if not plan or worker not in {int(p["id"]) for p in plan["workers"]}:
            return {"applied": False, "reason": "No verified animal and handler selected"}
        body = {"map_id": map_id, "animal_id": plan["animal"]["id"]}
        if action == "assign_animal_training":
            td = str(selected.get("animal_trainable") or "")
            if td not in plan["trainables"]:
                return {"applied": False, "reason": "Unsupported training selected"}
            body.update(trainable_def=td, wanted=True, handler_pawn_id=worker)
        else:
            body.update(master_pawn_id=worker, follow_drafted=True)
        response = order("/api/v1/map/animal/training", body)
        if accepted(response):
            order("/api/v1/colonist/work-priority", {"id": worker, "work": "Handling", "priority": 1})
    elif action == "improve_weapon_loadout":
        if selected.get("weapon_defer"):
            return {"applied": False, "reason": "laya_kept_current_loadouts", "selection": selected}
        plan = plans.get(str(selected.get("weapon_pawn")))
        weapon = plan and plan["weapons"].get(str(selected.get("weapon_item")))
        if not weapon:
            return {"applied": False, "reason": "No compatible weapon selected"}
        response = order("/api/v1/pawn/job", {"pawn_id": plan["pawn"]["id"], "job_def": "Equip", "target_thing_id": weapon["id"],
            "map_id": map_id, "allow_unforbid_equip": bool(weapon.get("is_forbidden"))})
    if response is None:
        return {"applied": False, "reason": "No capability order prepared"}
    applied = accepted(response)
    return {"applied": applied, "reason": response.get("reason") if isinstance(response, dict) else "invalid_response", "response": response, "selection": selected}


def execute(client: Any, snapshot: dict[str, Any], map_state: dict[str, Any], action: str, selected: dict[str, Any]) -> dict[str, Any]:
    """Remember accepted primary effects and repair only missing permissions."""
    _prune(snapshot, map_state)
    auxiliary_paths = {"/api/v1/colonist/work-priority", "/api/v1/map/zone/growing/sowing"}
    missing, steps = [], []

    def auxiliary(path: str, kwargs: dict[str, Any]) -> None:
        try:
            value = client.post(path, **kwargs)
            ok = isinstance(value, dict) and (value.get("applied") is True if "applied" in value else value.get("success") is True)
            steps.append({"path": path, "applied": ok, "response": value})
            if not ok:
                missing.append({"path": path, "kwargs": kwargs})
        except Exception as exc:
            steps.append({"path": path, "applied": False, "outcome_unknown": True, "reason": str(exc)})
            missing.append({"path": path, "kwargs": kwargs})

    pending_key = str(selected.get("auxiliary_retry") or action + "|" + _selection_key(action, selected))
    pending = map_state["capability_auxiliary"].get(pending_key)
    if selected.get("auxiliary_retry"):
        if not pending:
            return {"applied": False, "reason": "auxiliary_expired"}
        for step in (pending.get("steps") or [])[:3]:
            if isinstance(step, dict) and step.get("path") in auxiliary_paths and isinstance(step.get("kwargs"), dict):
                auxiliary(step["path"], step["kwargs"])
        result = {"applied": not missing and bool(steps), "reason": "auxiliary_repaired" if not missing else "auxiliary_pending"}
    else:
        class Orders:
            def post(self, path: str, **kwargs: Any) -> Any:
                if path in auxiliary_paths:
                    auxiliary(path, kwargs)
                    return steps[-1]
                return client.post(path, **kwargs)
        try:
            result = _execute_primary(Orders(), snapshot, map_state, action, selected)
        except Exception as exc:
            result = {"applied": False, "reason": str(exc), "outcome_unknown": True}
        key = _selection_key(action, selected)
        if str(result.get("reason") or "").startswith("laya_"):
            question = {"plan_colonist_augmentation": "augmentation_patient", "improve_weapon_loadout": "weapon_pawn",
                        "research_greenhouse": "greenhouse_research"}.get(action)
            shown = selected.get("shown_subjects", {}).get(question, [])
            if action == "improve_weapon_loadout" and selected.get("weapon_pawn") not in (None, "defer"):
                shown = [str(selected["weapon_pawn"])]
            for target in shown[:256]:
                _remember(snapshot, map_state, _scope(action, target), 250)
        elif action in {"clear_plant_blight", "harvest_at_risk_crops"}:
            for plant in snapshot["development"].get("capability_plans", {}).get(action, {}).get("plants", [])[:200]:
                _remember(snapshot, map_state, _scope(action, str(plant["thing_id"])), 250, not result.get("applied"))
        else:
            _remember(snapshot, map_state, _scope(action, key) if result.get("applied") else action + ":failed:" + key,
                      15000 if result.get("applied") else 250, not result.get("applied"))
    if missing:
        map_state["capability_auxiliary"][pending_key] = {"tick": pending["tick"] if pending else int(snapshot["game"].get("tick") or 0),
            "map_id": int(snapshot["map"]["id"]), "duration": 15000, "action": action, "steps": missing[:3]}
        _remember(snapshot, map_state, pending_key + ":aux_failed", 250, True)
    else:
        map_state["capability_auxiliary"].pop(pending_key, None)
    if steps:
        result.update(auxiliary_steps=steps, partial=bool(missing))
        if any(s.get("outcome_unknown") for s in steps):
            result["outcome_unknown"] = True
    return result
