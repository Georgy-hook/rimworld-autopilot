"""Compact recruitment context for Laya, not a scripted recruitment policy."""

from __future__ import annotations

from typing import Any


CRITICAL_SKILLS = ("Construction", "Plants", "Cooking", "Medicine", "Social", "Shooting")


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
        "active_quests": len(development.get("quests") or []),
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
        "live_signals": signals,
        "routes": routes,
        "tradeoff": "A small crew is fragile, but adding a person raises food, shelter, defense and medical needs. A trader may leave before another chance appears.",
    }


def trade_population_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Keep labor and survival facts visible within Laya's short trade context."""
    full = population_context(snapshot)
    return {key: full[key] for key in (
        "population", "able_workers", "bedbound", "unavailable_workers", "ready_meals", "total_food",
        "silver", "best_skills", "live_signals", "tradeoff")}


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
