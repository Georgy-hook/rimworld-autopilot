"""Compact recruitment context for Laya, not a scripted recruitment policy."""

from __future__ import annotations

from typing import Any


CRITICAL_SKILLS = ("Construction", "Plants", "Cooking", "Medicine", "Social", "Shooting")


def population_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    people = snapshot.get("colonists") or []
    able_workers = sum(not person.get("downed") and
                       float((person.get("capacities") or {}).get("moving", 1) or 0) > 0.15
                       for person in people)
    resources = (snapshot.get("map") or {}).get("resources") or {}
    development = snapshot.get("development") or {}
    best_skills = {
        skill: max((int(((person.get("skills") or {}).get(skill) or {}).get("level") or 0)
                    for person in people), default=0)
        for skill in CRITICAL_SKILLS
    }
    active_mods = " ".join(str(row.get("package_id") or "").lower()
                           for row in development.get("active_mods") or [] if isinstance(row, dict))
    routes = [
        "A visiting slaver can sell a person directly; no prison is needed. Compare price, health, skills and work limits. With Ideology, check whether the buyer receives a colonist or a slave.",
        "Answer live joiner letters before they expire; the new person adds labor and defense but needs food and a bed.",
        "Rescue a downed neutral: they might join after treatment, or leave; care is not guaranteed recruitment.",
        "Capture a downed enemy into a prison bed, then assign recruitment and wardening; food and treatment are ongoing costs.",
        "A wild human can be tamed by a skilled handler when one appears; hostile capture is not an instant recruit.",
        "A rescue quest can add a person but requires travel, supplies and enough defenders left at home.",
    ]
    if "biotech" in active_mods:
        routes.append("Childbirth is a long-term Biotech route, not an immediate worker; plan food, childcare and shelter.")
    return {
        "population": len(people),
        "able_workers": able_workers,
        "bedbound": len(people) - able_workers,
        "ready_meals": resources.get("meals"),
        "total_food": resources.get("food"),
        "silver": (development.get("item_counts") or {}).get("Silver", 0),
        "best_skills": best_skills,
        "routes": routes,
        "tradeoff": "A small crew is fragile, but adding a person raises food, shelter, defense and medical needs. A trader may leave before another chance appears.",
    }


def trade_population_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Keep labor and survival facts visible within Laya's short trade context."""
    full = population_context(snapshot)
    return {key: full[key] for key in (
        "population", "able_workers", "bedbound", "ready_meals", "total_food",
        "silver", "best_skills", "tradeoff")}


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
