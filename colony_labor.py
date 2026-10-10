"""Worker commitments tied to live tasks, not repeated priority acknowledgements."""
from __future__ import annotations
from typing import Any
import colony_retry as retry

FOOD_WORK = {"Cooking", "Hunting", "Growing", "PlantCutting"}
COMMITTED_WORK = FOOD_WORK | {"Mining", "Research"}
JOBS = {"Cooking": {"DoBill", "ButcherDoBill"}, "Hunting": {"Hunt"},
        "Growing": {"Sow"}, "PlantCutting": {"Harvest", "HarvestDesignated", "CutPlant", "CutPlantDesignated"},
        "Mining": {"Mine"}, "Research": {"Research"}}
DWELL_TICKS = 30000
DWELL_SECONDS = 120


def cooking_workers(snapshot: dict[str, Any]) -> set[int] | None:
    """None means a legacy observation; an observed empty queue is not ready."""
    context = snapshot.get("development", {}).get("sustenance") or {}
    if "tables" not in context:
        return None
    result = set()
    for table in context.get("tables") or []:
        if table.get("usable") is False:
            continue
        for bill in table.get("bills") or []:
            # Burning clothes/weapons/drugs is not cooking. New native DTOs
            # classify loaded recipes; the old public recipe names are fallback.
            recipe = str(bill.get("recipe") or "")
            food = bill.get("food_product")
            if food is None:
                food = recipe.startswith("Cook") or recipe in {"ButcherCorpseFlesh", "Make_Kibble"}
            if not food or not bill.get("requested") or bill.get("block_reason") not in {
                    "ready_for_ordinary_work", "ordinary_job_in_progress", "work_disabled"}:
                continue
            result.update(int(i) for i in bill.get("capable_worker_ids", bill.get("eligible_worker_ids")) or [])
            result.update(int(i) for i in bill.get("active_worker_ids") or [])
    return result


def source_ready(snapshot, work, pawn_id=None):
    dev = snapshot.get("development") or {}
    if work == "Cooking":
        workers = cooking_workers(snapshot)
        return workers is None or bool(workers if pawn_id is None else int(pawn_id) in workers)
    if work == "Hunting":
        wildlife = dev.get("wildlife") or {}
        if wildlife.get("available") is True:
            return bool(wildlife.get("actor_options") or wildlife.get("options") or wildlife.get("plans") or
                        dev.get("hunt_options") or any(p.get("current_job") == "Hunt" for p in snapshot.get("colonists") or []))
        return bool(dev.get("hunt_options")) if "hunt_options" in dev else True
    if work == "PlantCutting":
        if "plants" not in dev:
            return True
        return bool(dev.get("tree_options") or dev.get("wild_plant_options") or dev.get("early_crop_options") or
                    any(p.get("harvestable_now") or p.get("is_designated_for_harvest") or p.get("is_designated_for_cut")
                        for p in dev.get("plants") or []))
    return True


def prepare(snapshot, memory):
    tick = int(snapshot.get("game", {}).get("tick") or 0)
    map_id = int(snapshot.get("map", {}).get("id") or 0)
    people = {str(p.get("id")): p for p in snapshot.get("colonists") or []}
    rows = memory.setdefault("labor_commitments", {})
    if not isinstance(rows, dict):
        rows = memory["labor_commitments"] = {}
    for key in list(rows):
        row, pawn = rows[key], people.get(key)
        target_ids = row.get("target_ids") if isinstance(row, dict) else None
        ores = (snapshot.get("development", {}).get("ores") or {}).get("ores")
        finished_batch = (target_ids and isinstance(ores, dict)
            and all(isinstance(g, dict) and isinstance(g.get("thing_ids"), list) for g in ores.values())
            and not set(target_ids) & {i for g in ores.values() for i in g["thing_ids"]})
        if (not isinstance(row, dict) or row.get("map_id") != map_id or not pawn
                or not isinstance(row.get("tick"), (int, float)) or row.get("work") not in COMMITTED_WORK
                or pawn.get("dead") or pawn.get("is_dead")
                or not retry.recent(row, tick, DWELL_TICKS)
                and pawn.get("current_job") not in JOBS.get(row.get("work"), set())
                or tick < row.get("tick", tick)
                or finished_batch
                or not source_ready(snapshot, row.get("work"), key)):
            del rows[key]
    snapshot.setdefault("development", {})["labor_commitments"] = rows
    return rows


def can_assign(snapshot, pawn, work):
    if work in FOOD_WORK and not source_ready(snapshot, work, pawn.get("id")):
        return False
    row = (snapshot.get("development", {}).get("labor_commitments") or {}).get(str(pawn.get("id")))
    # Research/mining commitments protect normal development, but cannot lock
    # the only mobile worker away from ready food or required cooking fuel.
    # Eating, care and another food job still own their actors.
    from colony_capabilities import food_planning_facts
    urgent_food = work in FOOD_WORK and food_planning_facts(snapshot)["immediate_food_gap"]
    yielding = {"Research", "Mining"} if urgent_food else set()
    if work not in {"Doctor", "Patient", "BedRest", "Firefighter"} and any(pawn.get("current_job") in jobs for name, jobs in JOBS.items() if name != work and name not in yielding):
        return False
    # Care, eating, firefighting and urgent thermal work have their own fresh
    # native checks. A food priority must not steal another accepted food task.
    return not (row and row.get("work") != work and row.get("work") not in yielding
                and work not in {"Doctor", "Patient", "BedRest", "Firefighter"})


def remember(snapshot, pawn_id, work, target_ids=None):
    if work not in COMMITTED_WORK:
        return
    rows = snapshot.setdefault("development", {}).setdefault("labor_commitments", {})
    rows[str(pawn_id)] = {**retry.failure_record(int(snapshot.get("game", {}).get("tick") or 0), DWELL_SECONDS),
                         "map_id": int(snapshot.get("map", {}).get("id") or 0), "work": work,
                         "completion": "assignment_observed; job_completion_unverified"}
    if target_ids:
        rows[str(pawn_id)]["target_ids"] = list(target_ids)
