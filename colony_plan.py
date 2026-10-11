"""Persistent observations of development, and a complete short planning brief.

The model still chooses work. Orders do not complete a milestone, and waiting
or issuing another order cannot erase an unchanged research/food/defense gap.
"""
from __future__ import annotations

import math
from typing import Any

import colony_capabilities as capabilities
import colony_growth as growth


def number(value):
    try:
        result = float(value)
        return round(result, 2) if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def observations(snapshot):
    dev = snapshot.get("development") or {}
    resources = (snapshot.get("map") or {}).get("resources") or {}
    briefing = growth.development_briefing(snapshot)
    research = dev.get("current_research") or {}
    # Missing telemetry stays unknown. Blueprints, selected research and
    # estimated yields are commitments, not material progress.
    return {
        "food": number(resources.get("nutrition")),
        "research": {"target": research.get("name"), "points": number(research.get("progress")),
                     "finished": sorted(str(r.get("name")) if isinstance(r, dict) else str(r)
                                        for r in dev.get("finished_research") or [])}
                    if "current_research" in dev or "finished_research" in dev else None,
        "defense": {k: briefing[k] for k in ("ranged_fighters", "cover") if k in briefing} or None,
        "housing": sorted(int(b["id"]) for b in dev.get("buildings") or []
                          if isinstance(b.get("id"), int) and b.get("def") in
                          {"Bed", "DoubleBed", "RoyalBed", "SleepingSpot", "DoubleSleepingSpot"}
                          and not b.get("for_prisoners")) if "buildings" in dev else None,
    }


def reconcile(snapshot: dict[str, Any], map_state: dict[str, Any]) -> dict[str, Any]:
    """Compare domains across intervening actions; persist only bounded facts."""
    tick = int((snapshot.get("game") or {}).get("tick") or 0)
    state = map_state.setdefault("development_observations", {})
    if tick < int(state.get("tick", tick)):
        state.clear()
    metrics = state.setdefault("metrics", {})
    unchanged = {}
    for domain, value in observations(snapshot).items():
        if value is None:
            metrics.pop(domain, None)
            continue
        if domain == "research":
            # Switching a selected target is not research work. Credit only
            # points gained on an already observed project or a changed list
            # of completed unlocks; first observations establish a baseline.
            projects = state.setdefault("research_points", {})
            target, points = value["target"], value["points"]
            if target and str(target).lower() != "none" and points is not None:
                previous = projects.get(target)
                if previous is not None and points > previous:
                    state["research_work"] = number((state.get("research_work") or 0) + points - previous)
                projects[target] = points
                while len(projects) > 128:
                    projects.pop(next(iter(projects)))
            value = {"finished": value["finished"], "work_observed": state.get("research_work", 0)}
        prior = metrics.get(domain)
        if not isinstance(prior, dict) or prior.get("value") != value:
            metrics[domain] = {"value": value, "since_tick": tick}
        else:
            unchanged[domain] = max(0, tick - int(prior.get("since_tick", tick)))
    state["tick"] = tick
    feedback = {"unchanged_ticks": unchanged, "completion": "unverified"}
    snapshot.setdefault("development", {})["plan_observation"] = feedback
    return feedback


def brief(snapshot: dict[str, Any], roofed_sleepers: int | None, care: dict | None) -> dict:
    """Root domain/family/action calls receive this unit without prefix cuts."""
    dev = snapshot.get("development") or {}
    people = snapshot.get("colonists") or []
    combat = snapshot.get("combat") or {}
    details = {p.get("id"): p for p in combat.get("colonists") or []}
    protected = capabilities.CARE_JOBS
    free = [p for p in growth.available_workers(snapshot)
            if not (p.get("drafted") or p.get("is_drafted") or details.get(p.get("id"), {}).get("is_drafted"))
            and p.get("current_job") not in protected]
    workforce = growth.development_briefing(snapshot)
    food = capabilities.food_planning_facts(snapshot)
    route = ((dev.get("doctrine") or {}).get("endgame")
             or (dev.get("progression") or {}).get("chosen_ending_route"))
    from colony_progression import canonical_route
    route = canonical_route(route)
    research = dev.get("current_research") or {}
    clinical = care or {}
    needs = [f"food {food['stored_food_days']} days", f"free labor {len(free)}/{len(people)}",
             f"roofed sleep {roofed_sleepers}/{len(people)}"]
    if clinical.get("malnutrition_max"):
        needs.append(f"malnutrition {clinical['malnutrition_max']}")
    if clinical.get("bleed_rate_max"):
        needs.append(f"bleeding {clinical['bleed_rate_max']}")
    if clinical.get("downed"):
        needs.append(f"downed {clinical['downed']}")
    if clinical.get("animal_bleed_max"):
        needs.append(f"animal bleeding {clinical['animal_bleed_max']}")
    if clinical.get("thermal"):
        for name, row in clinical["thermal"].items():
            needs.append(f"{name} {row['severity']} stage {row.get('stage')} lethal {row.get('life_threatening')}")
        needs.append(f"bedroom C {clinical.get('roofed_bed_room_c', 'unknown')}")
    if clinical.get("recreation_deprived"):
        needs.append("recreation deprived")
    readiness = [f"guns {workforce.get('ranged_fighters', 'unknown')}",
                 f"cover {workforce.get('cover', 'unknown')}",
                 f"research {research.get('name') or workforce.get('research', 'unknown')} {number(research.get('progress'))}"]
    # A short list of genuine labor constraints, never a tutorial transcript.
    for key, label in (("missing_roles", "incapable"), ("unassigned_roles", "unassigned")):
        if workforce.get(key):
            readiness.append(label + " " + "/".join(workforce[key][:4]))
    if workforce.get("recruit_offers"):
        readiness.append(f"recruit offers {workforce['recruit_offers']}")
    if workforce.get("empty_workshops"):
        readiness.append(f"empty workshops {workforce['empty_workshops']}")
    pending = len(dev.get("construction_projects") or [])
    if pending:
        readiness.append(f"unfinished {pending}")
    unchanged = (dev.get("plan_observation") or {}).get("unchanged_ticks") or {}
    stalled = [f"{key} {ticks} ticks" for key, ticks in unchanged.items() if ticks >= 60000][:2]
    progress = dev.get('progression') or {}
    support = ((progress.get('support_research') or {}).get(route) or {})
    frontier = (progress.get('ship_research') or {}).get('frontier') if route == 'ship_escape' else support.get('frontier')
    next_step = (frontier or [])[:2]
    return {"needs": "; ".join(needs), "development": "; ".join(readiness),
            "ending": route or "not chosen; select a feasible finite route",
            **({'next_research': next_step} if next_step else {}),
            **({"unchanged": "; ".join(stalled)} if stalled else {})}
