"""Profession, passion and timetable reasoning for the autonomous director.

The module deliberately consumes WorkTypeDef data exported by the running game.
That keeps mod-added work types visible and avoids treating the English labels in
the base game as the complete profession list.
"""

from __future__ import annotations

from typing import Any


PASSION = {
    0: {"name": "no flame", "icon": "—", "xp_percent": 35, "mood": 0},
    1: {"name": "small flame", "icon": "🔥", "xp_percent": 100, "mood": 8},
    2: {"name": "large flame", "icon": "🔥🔥", "xp_percent": 150, "mood": 14},
}

# These are strategic directions, not a hard-coded replacement for WorkTypeDefs.
# The live work catalog below still exposes every vanilla, DLC and modded job.
PROFESSION_DIRECTIONS: dict[str, dict[str, Any]] = {
    "food_agriculture": {
        "label": "food, farming and cooking",
        "skills": {"Plants": 1.0, "Cooking": 1.0, "Animals": 0.45},
        "works": ["Growing", "PlantCutting", "Cooking", "Handling"],
        "buildings": ["kitchen", "freezer", "barn", "dining_recreation"],
    },
    "animal_husbandry": {
        "label": "animal husbandry and animal products",
        "skills": {"Animals": 1.0, "Plants": 0.45, "Shooting": 0.2},
        "works": ["Handling", "Growing", "Hunting"],
        "buildings": ["barn", "freezer", "workshop"],
    },
    "construction_architecture": {
        "label": "construction and settlement architecture",
        "skills": {"Construction": 1.0, "Mining": 0.5, "Artistic": 0.3},
        "works": ["Construction", "Mining", "Art"],
        "buildings": ["residence", "residential_compound", "defense", "storage"],
    },
    "mining_metallurgy": {
        "label": "mining, stone and metallurgy",
        "skills": {"Mining": 1.0, "Crafting": 0.75, "Construction": 0.45},
        "works": ["Mining", "Crafting", "Smithing", "Construction"],
        "buildings": ["workshop", "factory", "storage"],
    },
    "craft_industry": {
        "label": "crafting, tailoring and industrial production",
        "skills": {"Crafting": 1.0, "Intellectual": 0.4, "Construction": 0.3},
        "works": ["Crafting", "Smithing", "Tailoring", "Research"],
        "buildings": ["workshop", "factory", "storage"],
    },
    "research_technology": {
        "label": "research and high technology",
        "skills": {"Intellectual": 1.0, "Crafting": 0.55, "Construction": 0.35},
        "works": ["Research", "Crafting", "Construction"],
        "buildings": ["research_lab", "factory", "power_utility"],
    },
    "medicine_biotech": {
        "label": "medicine, surgery and biotechnology",
        "skills": {"Medicine": 1.0, "Intellectual": 0.65, "Social": 0.2},
        "works": ["Doctor", "Patient", "PatientBedRest", "Research"],
        "buildings": ["hospital", "research_lab"],
    },
    "trade_diplomacy": {
        "label": "trade, diplomacy and prisoner relations",
        "skills": {"Social": 1.0, "Animals": 0.35, "Intellectual": 0.2},
        "works": ["Warden", "Handling"],
        "buildings": ["dining_recreation", "prison", "storage"],
    },
    "art_culture": {
        "label": "art, beauty and culture",
        "skills": {"Artistic": 1.0, "Social": 0.35, "Construction": 0.2},
        "works": ["Art", "Construction"],
        "buildings": ["dining_recreation", "temple", "throne_room", "residence"],
    },
    "security_hunting": {
        "label": "security, hunting and layered defense",
        "skills": {"Shooting": 0.9, "Melee": 0.75, "Construction": 0.55, "Medicine": 0.3},
        "works": ["Hunting", "Construction", "Doctor"],
        "buildings": ["defense", "hospital", "workshop"],
    },
    "colony_services": {
        "label": "logistics, cleaning and general colony services",
        "skills": {"Construction": 0.25, "Social": 0.2},
        "works": ["Firefighter", "BasicWorker", "Hauling", "Cleaning", "Childcare"],
        "buildings": ["storage", "nursery", "dining_recreation"],
    },
}


def passion_info(value: Any) -> dict[str, Any]:
    try:
        numeric = max(0, min(2, int(value)))
    except (TypeError, ValueError):
        numeric = 0
    return PASSION[numeric]


def _trait_names(pawn: dict[str, Any]) -> set[str]:
    return {
        str(trait.get("name") or trait.get("label") or "").replace(" ", "").lower()
        for trait in pawn.get("traits", [])
        if isinstance(trait, dict) and not trait.get("suppressed")
    }


def learning_trait_factor(pawn: dict[str, Any]) -> float:
    """Approximate global learning factor for planning, not simulation."""
    traits = _trait_names(pawn)
    factor = 1.0
    if any(name in traits for name in ("fastlearner", "quicklearner")):
        factor += 0.75
    if "toosmart" in traits:
        factor += 0.75
    if "slowlearner" in traits:
        factor -= 0.75
    return max(0.25, factor)


def skill_potential(pawn: dict[str, Any], skill_name: str) -> float:
    skill = (pawn.get("skills") or {}).get(skill_name) or {}
    if skill.get("disabled"):
        return -100.0
    level = int(skill.get("level") or 0)
    passion = int(skill.get("passion") or 0)
    health_factor = max(0.35, float(pawn.get("health") or 1.0))
    capacity_factor = min(
        float((pawn.get("capacities") or {}).get("consciousness") or 1.0),
        float((pawn.get("capacities") or {}).get("manipulation") or 1.0),
    )
    # Current competence matters, while passions make low-level apprentices a
    # strategically meaningful option instead of always selecting the veteran.
    return (level * 2.0 + (0.0, 7.0, 13.0)[max(0, min(2, passion))]) * learning_trait_factor(pawn) * health_factor * max(0.35, capacity_factor)


def live_work_catalog(work_types: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in work_types or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("def_name") or row.get("name") or "")
        if not name:
            continue
        result.append({
            "def_name": name,
            "label": str(row.get("label") or name),
            "description": str(row.get("description") or ""),
            "relevant_skills": [str(value) for value in (row.get("relevant_skills") or [])],
            "natural_priority": int(row.get("natural_priority") or 0),
            "work_tags": str(row.get("work_tags") or ""),
        })
    return sorted(result, key=lambda row: (-row["natural_priority"], row["def_name"]))


def profession_context(colonists: list[dict[str, Any]], work_types: list[dict[str, Any]]) -> dict[str, Any]:
    all_skills = sorted({name for pawn in colonists for name in (pawn.get("skills") or {})})
    skill_summary: dict[str, Any] = {}
    for skill_name in all_skills:
        ranked = sorted(colonists, key=lambda pawn: skill_potential(pawn, skill_name), reverse=True)
        if not ranked:
            continue
        best = ranked[0]
        skill = (best.get("skills") or {}).get(skill_name) or {}
        flame = passion_info(skill.get("passion"))
        skill_summary[skill_name] = {
            "best_pawn_id": best.get("id"),
            "best_pawn": best.get("name"),
            "level": int(skill.get("level") or 0),
            "passion": int(skill.get("passion") or 0),
            "flame": flame["icon"],
            "learning_percent": flame["xp_percent"],
            "learning_trait_factor": round(learning_trait_factor(best), 2),
        }

    direction_rows: dict[str, Any] = {}
    for direction, spec in PROFESSION_DIRECTIONS.items():
        contributions = []
        total = 0.0
        for skill_name, weight in spec["skills"].items():
            ranked = sorted(colonists, key=lambda pawn: skill_potential(pawn, skill_name), reverse=True)
            if not ranked or skill_potential(ranked[0], skill_name) < 0:
                continue
            pawn = ranked[0]
            skill = (pawn.get("skills") or {}).get(skill_name) or {}
            value = skill_potential(pawn, skill_name) * float(weight)
            total += value
            contributions.append({
                "skill": skill_name,
                "pawn": pawn.get("name"),
                "level": int(skill.get("level") or 0),
                "flame": passion_info(skill.get("passion"))["icon"],
                "weighted_fit": round(value, 1),
            })
        relevant={"animal_husbandry":{"Inspired_Taming"},"art_culture":{"Inspired_Creativity","Frenzy_Work"},
                  "craft_industry":{"Inspired_Creativity","Frenzy_Work"},"medicine_biotech":{"Inspired_Surgery"},
                  "trade_diplomacy":{"Inspired_Trade","Inspired_Recruitment"},"security_hunting":{"Frenzy_Shoot","Frenzy_Go"}}
        inspiration_rows=[{"pawn":p.get("name"),"def":p.get("inspiration"),
                          "effect":(p.get("inspiration_context") or {}).get("effect"),
                          "left":(p.get("inspiration_context") or {}).get("remaining_ticks")}
                         for p in colonists if p.get("inspiration") in relevant.get(direction,{"Frenzy_Work","Frenzy_Go"})]
        direction_rows[direction] = {
            "inspirations":inspiration_rows,
            "label": spec["label"],
            "fit_score": round(total, 1),
            "people": sorted(contributions, key=lambda row: row["weighted_fit"], reverse=True),
            "work_types": [name for name in spec["works"] if any(w["def_name"] == name for w in live_work_catalog(work_types))],
            "building_programs": list(spec["buildings"]),
        }

    return {
        "directions": dict(sorted(direction_rows.items(), key=lambda item: item[1]["fit_score"], reverse=True)),
        "skills": skill_summary,
        "work_types": live_work_catalog(work_types),
        "passion_legend": PASSION,
        "inspirations": [{"pawn_id": p.get("id"), "pawn":p.get("name"), "def":p.get("inspiration"),
                         "context":p.get("inspiration_context")} for p in colonists if p.get("inspiration")],
    }


def direction_choice_descriptions(context: dict[str, Any]) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for name, row in (context.get("directions") or {}).items():
        people = ", ".join(
            f"{person['pawn']} {person['skill']} {person['level']} {person['flame']}"
            for person in row.get("people", [])[:4]
        ) or "no specialist"
        descriptions[name] = (
            f"{row.get('label')}; workforce fit {row.get('fit_score')}; {people}; "
            f"work {', '.join(row.get('work_types') or [])}; buildings {', '.join(row.get('building_programs') or [])}; "
            f"active opportunities {row.get('inspirations') or 'none'}"
        )
    return descriptions


def training_options(colonists: list[dict[str, Any]], work_types: list[dict[str, Any]], limit: int = 18) -> dict[str, dict[str, Any]]:
    by_skill: dict[str, list[str]] = {}
    for work in live_work_catalog(work_types):
        for skill in work["relevant_skills"]:
            by_skill.setdefault(skill, []).append(work["def_name"])

    rows: list[tuple[float, str, dict[str, Any]]] = []
    for pawn in colonists:
        if pawn.get("downed") or float(pawn.get("health") or 0.0) < 0.65:
            continue
        for skill_name, skill in (pawn.get("skills") or {}).items():
            if skill.get("disabled") or int(skill.get("level") or 0) >= 18:
                continue
            available_work = [
                name for name in by_skill.get(skill_name, [])
                if not ((pawn.get("work_priorities") or {}).get(name) or {}).get("disabled")
            ]
            if not available_work:
                continue
            passion = int(skill.get("passion") or 0)
            # No-flame training is still offered for a serious colony gap, but
            # passion candidates rank ahead of it and are explicit to Laya.
            current_level = int(skill.get("level") or 0)
            score = (passion_info(passion)["xp_percent"] / 10.0) + (18 - current_level) * 0.45
            score *= learning_trait_factor(pawn)
            plan = {
                "pawn_id": int(pawn["id"]),
                "pawn_name": str(pawn.get("name") or pawn["id"]),
                "skill": skill_name,
                "level": current_level,
                "passion": passion,
                "flame": passion_info(passion)["icon"],
                "xp_percent": passion_info(passion)["xp_percent"],
                "learning_trait_factor": round(learning_trait_factor(pawn), 2),
                "work_type": available_work[0],
                "work_types": available_work,
                "traits": [trait.get("label") or trait.get("name") for trait in pawn.get("traits", [])],
            }
            key = f"{int(pawn['id'])}|{skill_name}|{available_work[0]}"
            rows.append((score, key, plan))
    rows.sort(key=lambda item: (-item[0], item[1]))
    return {key: plan for _, key, plan in rows[:limit]}


def night_owl_options(colonists: list[dict[str, Any]]) -> dict[str, str]:
    options: dict[str, str] = {}
    for pawn in colonists:
        traits = _trait_names(pawn)
        if "nightowl" not in traits and not any("nightowl" in value for value in traits):
            continue
        options[str(pawn["id"])] = (
            f"{pawn.get('name')}: sleep 11:00-18:59, Anything at night; "
            "avoids being awake during the Night Owl daytime penalty and still permits recreation"
        )
    return options


def night_owl_schedule() -> dict[int, str]:
    return {hour: ("Sleep" if 11 <= hour <= 18 else "Anything") for hour in range(24)}
