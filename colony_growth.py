"""Compact recruitment context for Laya, not a scripted recruitment policy."""

from __future__ import annotations

from typing import Any


CRITICAL_SKILLS = ("Construction", "Plants", "Cooking", "Medicine", "Social", "Shooting", "Intellectual", "Crafting")
ROLE_SKILLS = {"Construction": "Construction", "Growing": "Plants", "Cooking": "Cooking",
               "Doctor": "Medicine", "Research": "Intellectual", "Warden": "Social",
               "Firefighter": None}


def live_quests(development: dict[str, Any]) -> list[dict[str, Any]]:
    """The native endpoint groups current quests and history in an object."""
    quests = development.get("quests")
    rows = quests.get("active_quests", []) if isinstance(quests, dict) else quests or []
    return [row for row in rows if isinstance(row, dict)
            and str(row.get("state") or "") in {"", "NotYetAccepted", "Ongoing"}]


def workforce_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Separate unavailable work from novice skill or an unassigned priority.

    Missing observations are unknown. A level-zero novice who can work is not
    equivalent to a pawn incapable of research, firefighting or wardening.
    """
    living = [p for p in snapshot.get("colonists") or [] if not p.get("dead") and not p.get("is_dead")]
    mobile_ids = {str(p.get("id")) for p in available_workers(snapshot)}
    capable, available, unassigned = {}, {}, []
    for role, skill in ROLE_SKILLS.items():
        def can_do(pawn):
            work = (pawn.get("work_priorities") or {}).get(role)
            ability = (pawn.get("skills") or {}).get(skill) if skill else None
            if (isinstance(work, dict) and work.get("disabled") is True
                    or isinstance(ability, dict) and ability.get("disabled") is True):
                return False
            if isinstance(work, dict) or isinstance(ability, dict):
                return True
            return None
        observations = [(p, can_do(p)) for p in living]
        unknown = any(value is None for _, value in observations)
        capable[role] = None if unknown else sum(value is True for _, value in observations)
        available[role] = None if unknown else sum(value is True and str(p.get("id")) in mobile_ids
                                                 for p, value in observations)
        providers = [p for p, value in observations if value is True]
        if providers and not unknown and all(
                ((p.get("work_priorities") or {}).get(role) or {}).get("priority") == 0
                for p in providers):
            unassigned.append(role)
    return {"capable": capable, "available": available,
            "missing_roles": [role for role, count in capable.items() if count == 0 and living],
            "unassigned_roles": unassigned}


def development_briefing(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Small measured development gaps for root comparisons, not a build order."""
    people = snapshot.get("colonists") or []
    if not people:
        return {}
    dev = snapshot.get("development") or {}
    workforce = workforce_context(snapshot)
    result = {"mobile_workers": len(available_workers(snapshot))}
    if workforce["missing_roles"]:
        result["missing_roles"] = workforce["missing_roles"]
    if workforce["unassigned_roles"]:
        result["unassigned_roles"] = workforce["unassigned_roles"]
    unavailable = [role for role, count in workforce["available"].items()
                   if count == 0 and (workforce["capable"].get(role) or 0) > 0]
    if unavailable:
        result["unavailable_roles"] = unavailable
    combat_people = (snapshot.get("combat") or {}).get("colonists")
    actors = [p for p in combat_people or []
              if not p.get("is_dead") and p.get("can_fight") is True]
    living_ids = {str(p.get("id")) for p in people if not p.get("dead") and not p.get("is_dead")}
    observed_ids = {str(p.get("id")) for p in combat_people or []}
    if (isinstance(combat_people, list) and living_ids <= observed_ids
            and all(isinstance(p.get("can_fight"), bool) for p in combat_people)
            and all(isinstance(p.get("has_ranged_weapon"), bool) for p in actors)):
        result["ranged_fighters"] = f"{sum(p.get('has_ranged_weapon') is True for p in actors)}/{len(actors)}"
    counts = dev.get("building_counts")
    if isinstance(counts, dict):
        result["cover"] = sum(int(counts.get(name) or 0) for name in ("Barricade", "Sandbags"))
        research = dev.get("current_research") or {}
        if not any(int(counts.get(name) or 0) for name in ("SimpleResearchBench", "HiTechResearchBench")):
            result["research"] = "no_bench"
        elif "Research" in workforce["missing_roles"]:
            result["research"] = "no_capable_worker"
        elif "Research" in workforce["unassigned_roles"]:
            result["research"] = "no_assigned_worker"
        else:
            result["research"] = research.get("name", "unknown")
    if dev.get("quests") is not None:
        result["recruit_offers"] = sum(q.get("increases_population") is True and q.get("can_accept") is True
                                       for q in live_quests(dev))
    tables = dev.get("work_tables")
    if isinstance(tables, list):
        result["empty_workshops"] = sum(t.get("bills_count") == 0 and t.get("thing_def") not in {
            "Campfire", "FueledStove", "ElectricStove", "ButcherSpot", "TableButcher"} for t in tables)
    return result


def available_workers(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [person for person in snapshot.get("colonists") or []
            if not person.get("dead") and not person.get("is_dead")
            and not person.get("downed") and not person.get("is_downed")
            and not person.get("in_mental_state") and not person.get("is_in_mental_state")
            and float((person.get("capacities") or {}).get("moving", 1) or 0) > .15]


def population_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    people = snapshot.get("colonists") or []
    living = [person for person in people if not person.get("dead") and not person.get("is_dead")]
    bedbound = [person for person in living if person.get("downed") or
                float((person.get("capacities") or {}).get("moving", 1) or 0) <= 0.15]
    available = available_workers(snapshot)
    able_workers = len(available)
    resources = (snapshot.get("map") or {}).get("resources") or {}
    development = snapshot.get("development") or {}
    best_skills = {
        skill: max((int(((person.get("skills") or {}).get(skill) or {}).get("level") or 0)
                    for person in available if not ((person.get("skills") or {}).get(skill) or {}).get("disabled")), default=0)
        for skill in CRITICAL_SKILLS
    }
    active_mods = " ".join(str(row.get("package_id") or "").lower()
                           for row in development.get("active_mods") or [] if isinstance(row, dict))
    routes = [
        "A visiting slaver can sell a person directly; no prison is needed. Compare price, health, skills and work limits. With Ideology, check whether the buyer receives a colonist or a slave.",
        "Answer live joiner letters before they expire; the new person adds labor and defense but needs food and a bed.",
        "Rescue a downed neutral: they might join after treatment, or leave; care is not guaranteed recruitment.",
        "Capture a downed enemy into a prison bed, then assign recruitment and wardening; food and treatment are ongoing costs.",
        "A wild human can be tamed by a handler with Animals 7 when one appears; ordinary prisoner recruitment does not work for wild people.",
        "A rescue quest can add a person but requires travel, supplies and enough defenders left at home.",
        "A threatened joiner or deserter quest may add a person immediately after acceptance, but can bring attackers or diplomatic costs; inspect the live offer.",
        "Temporary refugees may later ask to stay when treated well. They are not permanent recruits on arrival and can betray the colony.",
        "A faction settlement may sell a person when a visiting slaver does not appear; check trip safety and available silver.",
        "Ancient cryptosleep caskets may contain neutral or hostile people who can be rescued or captured, but opening an ancient danger is a serious combat risk, not an early guaranteed recruit.",
    ]
    if "biotech" in active_mods:
        routes.append("Childbirth is a long-term Biotech route, not an immediate worker; plan food, childcare and shelter.")
    if "ideology" in active_mods:
        routes.append("A successful Ideology ritual with a Random Recruit reward can yield a colonist, if this colony actually has such a ritual.")
    if "anomaly" in active_mods:
        routes.append("An Anomaly creepjoiner can request entry; evaluate the person and possible hidden threat before answering the live offer.")
    combat = snapshot.get("combat") or {}
    signals = {
        "wild_people_on_map": len(snapshot.get("wild_humans") or []),
        "prisoners_held": len(combat.get("prisoners") or []),
        "friendly_settlements_in_range": sum(bool(row.get("can_trade_now"))
                                             for row in development.get("trade_destinations") or []
                                             if isinstance(row, dict)),
        "visiting_trade_contacts": len(development.get("trade_opportunities") or []),
        "active_quests": len(live_quests(development)),
    }
    return {
        "population": len(people),
        "able_workers": able_workers,
        "bedbound": len(bedbound),
        "unavailable_workers": len(people) - able_workers,
        "ready_meals": resources.get("meals"),
        "total_food": resources.get("food"),
        "silver": (development.get("item_counts") or {}).get("Silver", 0),
        "best_skills": best_skills,
        "workforce": workforce_context(snapshot),
        "live_signals": signals,
        "routes": routes,
        "tradeoff": "A small crew is fragile, but adding a person raises food, shelter, defense and medical needs. A trader may leave before another chance appears.",
    }


def trade_population_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Keep labor and survival facts visible within Laya's short trade context."""
    full = population_context(snapshot)
    return {key: full[key] for key in (
        "population", "able_workers", "bedbound", "unavailable_workers", "ready_meals", "total_food",
        "silver", "best_skills", "workforce", "live_signals", "tradeoff")}


def brief_humanlike_offer_description(offer: dict[str, Any]) -> str:
    skills = ", ".join(str(value) for value in (offer.get("skills") or [])[:3]) or "skills unknown"
    conditions = ", ".join(str(value) for value in (offer.get("health_conditions") or [])[:2])
    disabled = ", ".join(str(value) for value in (offer.get("disabled_work") or [])[:2])
    return (f"{offer.get('name') or offer.get('pawn_id')} age {offer.get('age')}, "
            f"{float(offer.get('unit_price') or 0):.0f} silver; {skills}"
            + (f"; health issues {conditions}" if conditions else "")
            + (f"; cannot {disabled}" if disabled else ""))


def humanlike_offer_description(offer: dict[str, Any]) -> str:
    skills = ", ".join(str(value) for value in (offer.get("skills") or [])[:6]) or "skills unknown"
    traits = ", ".join(str(value) for value in (offer.get("traits") or [])[:4]) or "none listed"
    conditions = ", ".join(str(value) for value in (offer.get("health_conditions") or [])[:5]) or "none listed"
    disabled = ", ".join(str(value) for value in (offer.get("disabled_work") or [])[:5]) or "none listed"
    return (
        f"{offer.get('name') or offer.get('pawn_id')}; price {float(offer.get('unit_price') or 0):.0f} silver; "
        f"age {offer.get('age')}, {offer.get('gender')}; health {offer.get('health')}; "
        f"skills {skills}; traits {traits}; health issues {conditions}; cannot do {disabled}"
    )
