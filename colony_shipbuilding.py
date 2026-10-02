"""Observed, staged ship construction. A placed blueprint is not a finished ship."""
from __future__ import annotations

import copy
from collections import Counter
import colony_architect as architect


def identity(row, origin=None):
    if origin is not None:
        return (row["def_name"], origin["x"] + row["rel_x"], origin["z"] + row["rel_z"])
    pos = row.get("position") or {}
    return (row.get("def") or row.get("def_name"), pos.get("x"), pos.get("z"))


def prepare(snapshot, memory, layout):
    dev = snapshot.setdefault("development", {})
    project = memory.get("ship_project")
    if project is None:
        anchor = memory.get("anchor") or dev.get("base_anchor")
        if not anchor:
            return None
        project = {"origin": {"x": anchor["x"] - 5, "z": anchor["z"] + 25},
                   "layout": copy.deepcopy(layout)}
    origin, full = project["origin"], project["layout"]
    built = {identity(row) for row in dev.get("buildings") or []}
    queued = {identity(row) for row in dev.get("construction_projects") or []}
    missing = [row for row in full["buildings"] if identity(row, origin) not in built | queued]
    beams_done = all(identity(row, origin) in built for row in full["buildings"] if row["def_name"] == "Ship_Beam")
    # PlaceWorker_HeadOnShipBeam needs a completed edifice under the casket head.
    stage = [row for row in missing if row["def_name"] != "Ship_CryptosleepCasket" or beams_done]
    catalog = {row.get("def_name"): row for row in dev.get("building_catalog") or []}
    budget = Counter(dev.get("item_counts") or {})
    for pending in dev.get("construction_projects") or []:
        for cost in pending.get("materials_needed") or []:
            budget[str(cost.get("def_name"))] -= max(0, int(cost.get("required_count") or 0))
    chosen, shortages, blocked_defs = [], Counter(), []
    for row in stage:
        if row["def_name"] not in catalog:
            blocked_defs.append(row["def_name"])
            continue
        cost = architect.estimated_stuff_cost({"buildings": [row]}, list(catalog.values()))
        lack = {name: count - budget[name] for name, count in cost.items() if count > budget[name]}
        if lack:
            shortages.update(lack)
            continue
        chosen.append(row)
        budget.subtract(cost)
    plan = {**project, "remaining": len(missing), "waiting_for_completed_beams": not beams_done,
            "shortages": dict(shortages), "unobserved_definitions": sorted(set(blocked_defs)),
            "ready_layout": {**full, "buildings": chosen}, "queued": sum(identity(row, origin) in queued for row in full["buildings"]),
            "completed": all(identity(row, origin) in built for row in full["buildings"])}
    dev["ship_construction"] = plan
    age = int(snapshot.get("game", {}).get("tick") or 0) - int(memory.get("ship_site_retry_tick", -1000000))
    if 0 <= age < 2500:
        plan["ready_layout"] = {**full, "buildings": []}
    return plan


def execute(client, snapshot, memory, layout):
    # Re-read physical evidence and unallocated stock immediately before placement.
    fresh = copy.deepcopy(snapshot)
    dev = fresh.setdefault("development", {})
    map_id = snapshot["map"]["id"]
    dev["buildings"] = client.get("/api/v1/map/buildings", map_id=map_id)
    dev["construction_projects"] = client.get("/api/v1/builder/projects", map_id=map_id).get("projects", [])
    things = client.get("/api/v1/map/things", map_id=map_id)
    stock = Counter()
    for row in things:
        if not row.get("is_forbidden"):
            stock[str(row.get("def_name"))] += max(1, int(row.get("stack_count") or 1))
    dev["item_counts"] = dict(stock)
    plan = prepare(fresh, memory, layout)
    if not plan or not plan["ready_layout"]["buildings"]:
        return {"applied": False, "reason": "ship_waiting_for_parts_materials_or_beams", "completion": "unverified"}
    origin = plan["origin"]
    def preview(at, proposal):
        return client.post("/api/v1/builder/blueprint/preview", body={"map_id": map_id,
            "position": {"x": at["x"], "y": 0, "z": at["z"]}, "blueprint": proposal,
            "clear_obstacles": False})
    if "ship_project" not in memory:
        # Inspect the whole connected footprint before funding its first piece.
        # Caskets are checked after their native beam prerequisite is completed.
        foundation = {**plan["layout"], "buildings": [row for row in plan["layout"]["buildings"]
                                                    if row["def_name"] != "Ship_CryptosleepCasket"]}
        candidates = [origin] + [{"x": origin["x"] + dx, "z": origin["z"] + dz}
            for distance in (20, 40, 60) for dx, dz in ((distance, 0), (-distance, 0), (0, distance),
                (0, -distance), (distance, distance), (-distance, distance), (distance, -distance), (-distance, -distance))]
        origin = next((at for at in candidates if preview(at, foundation).get("all_placeable") is True), None)
        if origin is None:
            memory["ship_site_retry_tick"] = int(snapshot.get("game", {}).get("tick") or 0)
            return {"applied": False, "reason": "no_native_valid_connected_ship_site", "completion": "unverified"}
    checked = preview(origin, plan["ready_layout"])
    accepted_indices = {row["index"] for row in checked.get("elements") or []
                        if row.get("kind") == "building" and row.get("accepted") is True}
    proposed = {**plan["ready_layout"], "buildings": [row for index, row in enumerate(plan["ready_layout"]["buildings"])
                                                     if index in accepted_indices]}
    if not proposed["buildings"]:
        memory["ship_site_retry_tick"] = int(snapshot.get("game", {}).get("tick") or 0)
        return {"applied": False, "reason": "ship_native_placement_blocked", "preview": checked, "completion": "unverified"}
    memory["ship_project"] = {"origin": origin, "layout": plan["layout"]}
    response = client.post("/api/v1/builder/blueprint", body={"map_id": map_id,
        "position": {"x": origin["x"], "y": 0, "z": origin["z"]},
        "blueprint": proposed, "clear_obstacles": False})
    after = client.get("/api/v1/builder/projects", map_id=map_id).get("projects", [])
    after_built = client.get("/api/v1/map/buildings", map_id=map_id)
    observed = {identity(row) for row in after + after_built}
    accepted = [row for row in plan["ready_layout"]["buildings"] if identity(row, origin) in observed]
    return {"applied": bool(accepted), "reason": "ship_blueprints_observed" if accepted else "no_ship_blueprints_observed",
            "placed": len(accepted), "requested": len(plan["ready_layout"]["buildings"]),
            "completion": "unverified", "response": response}
