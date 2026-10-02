"""Procedural, data-driven architecture for Laya's RimWorld director.

Laya chooses a building program and a compact set of constraints.  This module
then creates deterministic variants from the building definitions actually
loaded by the game.  It avoids a growing pile of one-off coordinates while
still exposing meaningful architectural choices to the model.
"""

from __future__ import annotations

import random
import math
from collections import Counter
from typing import Any


PROGRAM_CATALOG: dict[str, dict[str, Any]] = {
    "residence": {"label": "private house", "category": "housing", "skills": ["Construction", "Artistic"]},
    "residential_compound": {"label": "multi-room residential compound", "category": "housing", "skills": ["Construction"]},
    "dining_recreation": {"label": "dining and recreation hall", "category": "community", "skills": ["Construction", "Artistic"]},
    "kitchen": {"label": "clean dedicated kitchen", "category": "food", "skills": ["Cooking", "Construction"]},
    "freezer": {"label": "freezer and food storage", "category": "food", "skills": ["Construction"]},
    "greenhouse_soil": {"label": "heated soil greenhouse", "category": "food", "skills": ["Plants", "Construction"]},
    "greenhouse_hydroponics": {"label": "heated hydroponic greenhouse", "category": "food", "skills": ["Plants", "Construction"]},
    "hospital": {"label": "hospital or medical annex", "category": "medical", "skills": ["Medicine", "Construction"]},
    "throne_room": {"label": "royal throne hall", "category": "culture", "skills": ["Construction", "Artistic"]},
    "temple": {"label": "ideology temple", "category": "culture", "skills": ["Construction", "Artistic"]},
    "workshop": {"label": "low- or mid-tech workshop", "category": "production", "skills": ["Crafting", "Construction"]},
    "factory": {"label": "powered industrial factory", "category": "production", "skills": ["Crafting", "Intellectual"]},
    "research_lab": {"label": "research laboratory", "category": "technology", "skills": ["Intellectual", "Construction"]},
    "storage": {"label": "shelved warehouse", "category": "logistics", "skills": ["Construction"]},
    "prison": {"label": "secure humane prison", "category": "care", "skills": ["Social", "Construction"]},
    "barn": {"label": "animal barn", "category": "animals", "skills": ["Animals", "Construction"]},
    "nursery": {"label": "nursery and school room", "category": "care", "skills": ["Childcare", "Social"]},
    "defense": {"label": "layered defensive position", "category": "defense", "skills": ["Construction", "Shooting"]},
    "power_utility": {"label": "power and utility block", "category": "infrastructure", "skills": ["Construction"]},
}

HOUSE_STYLES = {
    "compact": "Compact inexpensive single bedroom with light and climate allowance",
    "comfort": "Bedroom with end table and dresser when Complex Furniture is available",
    "garden": "Larger bright bedroom with plant pots and more free space",
    "artisan": "Decorated bedroom intended for art and higher impressiveness",
    "couple": "Private couple's house with a double bed and symmetric furniture",
    "family": "Expandable family house with double bed and crib when Biotech buildings are loaded",
}

WORKBENCH_UPGRADE_CHAINS = [
    ("ButcherSpot", "TableButcher", "cleaner, faster permanent butchery"),
    ("FueledStove", "ElectricStove", "powered cooking with no wood refuelling"),
    ("HandTailoringBench", "ElectricTailoringBench", "faster powered tailoring"),
    ("FueledSmithy", "ElectricSmithy", "powered smithing"),
    ("SimpleResearchBench", "HiTechResearchBench", "advanced research and higher research speed"),
    ("TableMachining", "FabricationBench", "advanced components and high-tech production"),
]

SPECIALIZATION_BENCHES = {
    "food_agriculture": ["ElectricStove", "FueledStove", "TableButcher", "Brewery"],
    "animal_husbandry": ["TableButcher", "ElectricStove", "HandTailoringBench"],
    "construction_architecture": ["TableStonecutter", "TableSculpting", "ElectricSmithy", "FueledSmithy"],
    "mining_metallurgy": ["TableStonecutter", "ElectricSmelter", "ElectricSmithy", "TableMachining"],
    "craft_industry": ["ElectricTailoringBench", "HandTailoringBench", "ElectricSmithy", "TableMachining", "TableSculpting"],
    "research_technology": ["HiTechResearchBench", "SimpleResearchBench", "FabricationBench", "TableMachining"],
    "medicine_biotech": ["DrugLab", "HiTechResearchBench", "BiofuelRefinery"],
    "trade_diplomacy": ["ElectricTailoringBench", "TableSculpting", "Brewery"],
    "art_culture": ["TableSculpting", "ElectricTailoringBench"],
    "security_hunting": ["TableMachining", "ElectricSmithy", "FabricationBench"],
    "colony_services": ["ElectricCrematorium", "TableButcher", "ElectricStove"],
}


def position(x: int, z: int) -> dict[str, int]:
    return {"x": int(x), "y": 0, "z": int(z)}


def building(def_name: str, x: int, z: int, *, stuff: str | None = None, rotation: int = 0) -> dict[str, Any]:
    result: dict[str, Any] = {"def_name": def_name, "rel_x": int(x), "rel_z": int(z), "rotation": int(rotation)}
    if stuff:
        result["stuff_def_name"] = stuff
    return result


def floor(def_name: str, x: int, z: int) -> dict[str, Any]:
    return {"def_name": def_name, "rel_x": int(x), "rel_z": int(z)}


def blueprint(items: list[dict[str, Any]], width: int, height: int, floors: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"width": int(width), "height": int(height), "buildings": items, "floors": floors or []}


def catalog_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("def_name")): row
        for row in rows or []
        if isinstance(row, dict) and row.get("def_name")
    }


def summarize_catalog(rows: list[dict[str, Any]]) -> dict[str, Any]:
    categories: Counter[str] = Counter()
    buildable = 0
    worktables = []
    powered = []
    lights = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        categories[str(row.get("designation_category") or "Other")] += 1
        if row.get("available_now"):
            buildable += 1
        if row.get("is_work_table"):
            worktables.append(str(row.get("def_name")))
        if row.get("requires_power"):
            powered.append(str(row.get("def_name")))
        if float(row.get("light_radius") or 0.0) > 0:
            lights.append(str(row.get("def_name")))
    return {
        "total_player_buildings": sum(categories.values()),
        "available_now": buildable,
        "categories": dict(categories.most_common()),
        "worktables": sorted(worktables),
        "powered_buildings": sorted(powered),
        "light_sources": sorted(lights),
        "programs": PROGRAM_CATALOG,
    }


def _available(index: dict[str, dict[str, Any]], def_name: str, *, fallback: bool = True) -> bool:
    if not index:
        return fallback
    row = index.get(def_name)
    return bool(row and row.get("available_now", True))


def _shell(width: int, height: int, material: str, door_side: str, door_offset: int) -> list[dict[str, Any]]:
    door_offset = max(1, min((width if door_side in {"north", "south"} else height) - 2, door_offset))
    door_cell = {
        "south": (door_offset, 0),
        "north": (door_offset, height - 1),
        "west": (0, door_offset),
        "east": (width - 1, door_offset),
    }[door_side]
    items: list[dict[str, Any]] = []
    for x in range(width):
        for z in (0, height - 1):
            if (x, z) != door_cell:
                items.append(building("Wall", x, z, stuff=material))
    for z in range(1, height - 1):
        for x in (0, width - 1):
            if (x, z) != door_cell:
                items.append(building("Wall", x, z, stuff=material))
    items.append(building("Door", door_cell[0], door_cell[1], stuff=material))
    return items


def _interior_floor(width: int, height: int, floor_def: str | None) -> list[dict[str, Any]]:
    if not floor_def:
        return []
    return [floor(floor_def, x, z) for x in range(1, width - 1) for z in range(1, height - 1)]


def _floor_for_material(material: str, finished: set[str], item_counts: dict[str, Any], area: int) -> str | None:
    if material.startswith("Blocks") and "Stonecutting" in finished:
        stone = material.removeprefix("Blocks")
        if int(item_counts.get(material) or 0) >= area * 4 + 100:
            return f"Tile{stone}"
    if material == "WoodLog" and int(item_counts.get("WoodLog") or 0) >= area * 3 + 250:
        return "WoodPlankFloor"
    return None


def _light_def(index: dict[str, dict[str, Any]], powered: bool) -> str:
    if powered and _available(index, "StandingLamp"):
        return "StandingLamp"
    return "TorchLamp"


def _climate_items(index: dict[str, dict[str, Any]], climate: str, powered: bool, x: int, z: int) -> list[dict[str, Any]]:
    if climate == "cold" and powered and _available(index, "Heater"):
        return [building("Heater", x, z)]
    if climate == "hot" and _available(index, "PassiveCooler"):
        return [building("PassiveCooler", x, z)]
    return []


def generate_house_candidates(
    material: str,
    building_catalog: list[dict[str, Any]],
    finished_research: set[str],
    item_counts: dict[str, Any],
    *,
    powered: bool,
    climate: str,
    seed: int = 0,
    entry_side: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Generate 24 deterministic houses (six styles × four layouts)."""
    index = catalog_index(building_catalog)
    result: dict[str, dict[str, Any]] = {}
    style_sizes = {
        "compact": (7, 7), "comfort": (7, 8), "garden": (8, 8),
        "artisan": (8, 9), "couple": (8, 8), "family": (9, 9),
    }
    for style_index, (style, description) in enumerate(HOUSE_STYLES.items()):
        base_width, base_height = style_sizes[style]
        for variant in range(4):
            rng = random.Random(seed * 1009 + style_index * 101 + variant * 17)
            width = base_width + (1 if variant in {2, 3} else 0)
            height = base_height + (1 if variant in {1, 3} else 0)
            door_side = entry_side if entry_side in {"south", "east", "north", "west"} else (
                "south", "east", "north", "west")[(variant + style_index) % 4]
            edge_length = width if door_side in {"north", "south"} else height
            door_offset = rng.randint(2, max(2, edge_length - 3))
            items = _shell(width, height, material, door_side, door_offset)
            bed_def = "DoubleBed" if style in {"couple", "family"} and _available(index, "DoubleBed") else "Bed"
            bed_x = 2 if variant % 2 == 0 else max(2, width - 4)
            bed_z = max(2, height // 2)
            items.append(building(bed_def, bed_x, bed_z, stuff="WoodLog", rotation=variant % 4))
            light_x, light_z = width - 2, height - 2
            items.append(building(_light_def(index, powered), light_x, light_z))
            if style in {"comfort", "garden", "artisan", "couple", "family"} and _available(index, "EndTable"):
                items.append(building("EndTable", max(1, bed_x - 1), bed_z, stuff="WoodLog"))
            if style in {"comfort", "artisan", "couple", "family"} and _available(index, "Dresser"):
                items.append(building("Dresser", width // 2, height - 2, stuff="WoodLog", rotation=2))
            if style in {"garden", "artisan"} and _available(index, "PlantPot"):
                items.extend([
                    building("PlantPot", 1, height - 2, stuff="WoodLog"),
                    building("PlantPot", width - 2, 1, stuff="WoodLog"),
                ])
            if style == "family" and _available(index, "Crib"):
                items.append(building("Crib", width - 3, 2, stuff="WoodLog", rotation=1))
            if style in {"artisan", "family"} and _available(index, "Table1x2c"):
                items.append(building("Table1x2c", width // 2, 2, stuff="WoodLog", rotation=1))
                if _available(index, "DiningChair"):
                    items.append(building("DiningChair", width // 2 - 1, 2, stuff="WoodLog", rotation=1))
            items.extend(_climate_items(index, climate, powered, width - 2, 2))
            area = (width - 2) * (height - 2)
            floor_def = _floor_for_material(material, finished_research, item_counts, area) if style in {"artisan", "couple", "family"} else None
            layout = blueprint(items, width, height, _interior_floor(width, height, floor_def))
            layout = resolve_layout_materials(layout, index, item_counts)
            if layout is None:
                continue
            option_id = f"house_{style}_{variant + 1}"
            result[option_id] = {
                "id": option_id,
                "program": "residence",
                "style": style,
                "name": f"{style} house {variant + 1}",
                "summary": f"{description}; {width}×{height}; door {door_side} at {door_offset}; "
                           f"wall {material}; {bed_def}; {floor_def or 'natural floor'}; {_light_def(index, powered)}",
                "width": width,
                "height": height,
                "layout": layout,
            }
    return result


def _furnished_room(
    program: str,
    width: int,
    height: int,
    material: str,
    catalog: list[dict[str, Any]],
    finished: set[str],
    item_counts: dict[str, Any],
    powered: bool,
    climate: str,
    variant: int,
    context: dict[str, Any],
    seed: int,
) -> dict[str, Any]:
    index = catalog_index(catalog)
    requested_side = str(context.get("entry_side") or "")
    door_side = requested_side if requested_side in {"south", "east", "north", "west"} else (
        "south", "east", "north")[variant % 3]
    edge_length = width if door_side in {"south", "north"} else height
    rng = random.Random(seed * 1009 + sum(map(ord, program)) * 101 + variant * 17)
    door_offset = rng.randint(2, max(2, edge_length - 3))
    items = _shell(width, height, material, door_side, door_offset)
    items.append(building(_light_def(index, powered), width - 2, height - 2))
    floors: list[dict[str, Any]] = []
    interior_area = (width - 2) * (height - 2)

    def add(name: str, x: int, z: int, *, stuff: str | None = None, rotation: int = 0) -> None:
        if _available(index, name):
            items.append(building(name, x, z, stuff=stuff, rotation=rotation))

    if program == "dining_recreation":
        add("Table2x2c", width // 2 - 1, height // 2, stuff="WoodLog")
        for x, z, rotation in ((width // 2 - 2, height // 2, 1), (width // 2 + 1, height // 2, 3), (width // 2, height // 2 - 2, 2), (width // 2, height // 2 + 2, 0)):
            add("DiningChair", x, z, stuff="WoodLog", rotation=rotation)
        add("ChessTable", 2, height - 3, stuff="WoodLog")
        add("PlantPot", width - 2, 1, stuff="WoodLog")
    elif program == "kitchen":
        stove = "ElectricStove" if powered and _available(index, "ElectricStove") else "FueledStove"
        add(stove, 2, height - 3, rotation=2)
        add("Shelf", width - 3, height - 2, stuff=material, rotation=1)
        add("Shelf", width - 3, 2, stuff=material, rotation=1)
        # Butchery is intentionally excluded: corpse/leather filth belongs in a
        # separate annex so the cooking room can stay clean.
        floor_def = "SterileTile" if "SterileMaterials" in finished and int(item_counts.get("Silver") or 0) >= interior_area * 12 + 300 else "MetalTile" if "Smithing" in finished and int(item_counts.get("Steel") or 0) >= interior_area * 7 + 200 else None
        floors = _interior_floor(width, height, floor_def)
    elif program == "hospital":
        hospital_bed = _available(index, "HospitalBed")
        bed_def = "HospitalBed" if hospital_bed else "Bed"
        center_x, center_z = width // 2, height // 2
        # The first four beds face a shared central monitor. Extra beds form an
        # overflow annex; they never cause multiple-monitor stacking on a bed.
        bed_positions = [
            (center_x - 2, center_z, 1), (center_x + 2, center_z, 3),
            (center_x, center_z - 2, 2), (center_x, center_z + 2, 0),
            (2, 2, 1), (width - 3, height - 3, 3),
        ]
        bed_count = min(len(bed_positions), 2 + variant * 2)
        for x, z, rotation in bed_positions[:bed_count]:
            add(bed_def, x, z, stuff=None if hospital_bed else "WoodLog", rotation=rotation)
        if hospital_bed and _available(index, "VitalsMonitor"):
            add("VitalsMonitor", center_x, center_z)
        add("Shelf", 1, height // 2, stuff=material, rotation=1)
        if "SterileMaterials" in finished and int(item_counts.get("Silver") or 0) >= interior_area * 12 + 300:
            floors = _interior_floor(width, height, "SterileTile")
        elif "Smithing" in finished and int(item_counts.get("Steel") or 0) >= interior_area * 7 + 200:
            floors = _interior_floor(width, height, "MetalTile")
        items.extend(_climate_items(index, climate, powered, width - 2, 2))
    elif program == "throne_room":
        royalty = context.get("royalty") or {}
        title_names = {str(row.get("title_def_name") or "") for row in royalty.get("colonists", [])}
        grand = any(name in {"Baron", "Baroness", "Count", "Countess"} or "Count" in name or "Baron" in name for name in title_names)
        throne = "GrandThrone" if grand and _available(index, "GrandThrone") else "Throne"
        add(throne, width // 2, height - 3, stuff=material, rotation=2)
        for x in (2, width - 3):
            add("Brazier", x, height - 3, stuff=material)
            add("Column", x, 3, stuff=material)
        for x in range(2, width - 2, 3):
            add("Drape", x, height - 2, stuff=material, rotation=2)
        floor_def = _floor_for_material(material, finished, item_counts, interior_area)
        floors = _interior_floor(width, height, floor_def)
    elif program in {"workshop", "factory"}:
        specialization = str((context.get("doctrine") or {}).get("specialization") or "")
        preferred = SPECIALIZATION_BENCHES.get(specialization, [])
        bench_defs = [
            name for name in preferred
            if _available(index, name, fallback=False)
            and (program != "factory" or bool((index.get(name) or {}).get("requires_power")))
        ]
        if not bench_defs:
            bench_defs = [
                name for name in (context.get("bench_defs") or [])
                if program != "factory" or bool((index.get(name) or {}).get("requires_power"))
            ]
        selected = bench_defs[variant % len(bench_defs)] if bench_defs else "TableStonecutter"
        add(selected, 2, height // 2, stuff=material if (index.get(selected) or {}).get("cost_stuff_count") else None, rotation=2)
        add("Shelf", width - 3, 2, stuff=material, rotation=1)
        add("Shelf", width - 3, height - 3, stuff=material, rotation=1)
    elif program == "research_lab":
        bench = "HiTechResearchBench" if _available(index, "HiTechResearchBench") else "SimpleResearchBench"
        add(bench, 2, height // 2, stuff="Steel" if bench == "HiTechResearchBench" else material, rotation=2)
        if bench == "HiTechResearchBench":
            add("MultiAnalyzer", width - 3, height // 2)
        add("Shelf", width - 3, 2, stuff=material, rotation=1)
        floor_def = "SterileTile" if "SterileMaterials" in finished and int(item_counts.get("Silver") or 0) >= interior_area * 12 + 300 else None
        floors = _interior_floor(width, height, floor_def)
    elif program == "storage":
        for x in range(2, width - 2, 3):
            for z in range(2, height - 2, 3):
                add("Shelf", x, z, stuff=material, rotation=variant % 2)
    elif program == "prison":
        for i in range(2 + variant):
            add("Bed", 2 + (i % 3) * 2, 2 + (i // 3) * 3, stuff="WoodLog")
        add("Table1x2c", width // 2, height - 2, stuff="WoodLog", rotation=1)
        add("DiningChair", width // 2 - 1, height - 2, stuff="WoodLog", rotation=1)
    elif program == "barn":
        # Swap the human door for an animal flap when loaded.
        if _available(index, "AnimalFlap"):
            for item in items:
                if item["def_name"] == "Door":
                    item["def_name"] = "AnimalFlap"
                    break
        for i in range(min(10, max(3, int(context.get("animal_count") or 3) + variant))):
            add("AnimalSleepingSpot", 1 + (i % 4) * 2, 2 + (i // 4) * 2)
        if "StrawMatting" in index and int(item_counts.get("Hay") or item_counts.get("HayGrass") or 0) >= interior_area:
            floors = _interior_floor(width, height, "StrawMatting")
        items.extend(_climate_items(index, climate, powered, width - 2, 2))
    elif program == "nursery":
        for x in range(2, width - 2, 3):
            add("Crib", x, 3, stuff="WoodLog")
        add("Blackboard", width // 2, height - 2, stuff="WoodLog", rotation=2)
        add("SchoolDesk", width // 2, height - 4, stuff="WoodLog", rotation=2)
        add("ToyBox", 2, height - 2, stuff="WoodLog")
    elif program == "freezer":
        # Cooler occupies the exterior wall opening, not the same cell as a
        # second wall or the model-selected entrance blueprint.
        cooler_z = height // 2
        if any(item["def_name"] == "Door" and item["rel_x"] == width - 1
               and item["rel_z"] == cooler_z for item in items):
            cooler_z -= 1
        items = [item for item in items if not (
            item["def_name"] == "Wall" and item["rel_x"] == width - 1 and item["rel_z"] == cooler_z
        )]
        add("Cooler", width - 1, cooler_z, rotation=1)
        for x in range(2, width - 2, 3):
            for z in range(2, height - 2, 3):
                add("Shelf", x, z, stuff=material)
    elif program == "power_utility":
        generator = "SolarGenerator" if _available(index, "SolarGenerator") else "WoodFiredGenerator"
        add(generator, 2, 2)
        add("Battery", width - 3, 2)
        add("FirefoamPopper", width // 2, height - 3)
        for x in range(1, width - 1):
            add("PowerConduit", x, height // 2)
    elif program == "temple":
        altar_defs = context.get("altar_defs") or []
        if altar_defs:
            add(altar_defs[variant % len(altar_defs)], width // 2, height - 3, stuff=material, rotation=2)
        for x in range(2, width - 2, 2):
            add("Pew", x, 3, stuff=material, rotation=2)
        floor_def = _floor_for_material(material, finished, item_counts, interior_area)
        floors = _interior_floor(width, height, floor_def)
    elif program == "residential_compound":
        # Three partitioned bedrooms share a lit central corridor.  Each room
        # remains a separate RimWorld room rather than turning beds into a barracks.
        partition_z = height // 2
        for x in range(1, width - 1):
            if x not in {width // 4, width // 2, (width * 3) // 4}:
                items.append(building("Wall", x, partition_z, stuff=material))
        for x in {width // 4, width // 2, (width * 3) // 4}:
            add("Door", x, partition_z, stuff=material)
        for x in (2, width // 2, width - 3):
            add("Bed", x, 2, stuff="WoodLog")
        add("Table2x2c", width // 2, height - 3, stuff="WoodLog")
    items.extend(_climate_items(index, climate, powered, width - 2, 2) if program not in {"hospital", "barn"} else [])
    return blueprint(items, width, height, floors)


def _defense_variant(material: str, variant: int, index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    width, height = 9 + variant * 2, 9
    items: list[dict[str, Any]] = []
    for z in range(height - 2):
        items.append(building("Wall", 0, z, stuff=material))
        items.append(building("Wall", width - 1, z, stuff=material))
    for x in range(1, width - 1):
        if x != width // 2:
            items.append(building("TrapSpike", x, 2 + (x % 2) * 2, stuff="WoodLog"))
    for x in range(1, width - 1):
        items.append(building("Barricade", x, height - 2, stuff=material))
    if variant >= 1 and _available(index, "TurretGun", fallback=False):
        items.extend([building("TurretGun", 1, height - 1), building("TurretGun", width - 2, height - 1)])
    return blueprint(items, width, height)


def greenhouse_context(context: dict[str, Any]) -> dict[str, Any]:
    index = catalog_index(context.get("building_catalog") or [])
    climate = str(context.get("climate") or "temperate")
    required = ["SunLamp", "PowerConduit", "Wall", "Door"]
    if climate == "cold":
        required.append("Heater")
    elif climate == "hot":
        required.append("Cooler")
    prerequisites = sorted({r for name in required + ["HydroponicsBasin"]
                            for r in (index.get(name) or {}).get("research_prerequisites") or []
                            if r not in set(context.get("finished_research") or [])})
    short_season = "tundra" in str(context.get("biome") or "").lower() or "ice" in str(context.get("biome") or "").lower()
    watts = float((index.get("SunLamp") or {}).get("nominal_power_consumption") or 2900)
    if climate == "cold":
        watts += (2 if short_season else 1) * float((index.get("Heater") or {}).get("nominal_power_consumption") or 175)
    elif climate == "hot":
        watts += float((index.get("Cooler") or {}).get("nominal_power_consumption") or 200)
    basic = all(index.get(name, {}).get("available_now") for name in required)
    hydro = basic and index.get("HydroponicsBasin", {}).get("available_now", False)
    counts = context.get("building_counts") or {}
    roofed_beds = int(context.get("sheltered_beds") or 0)
    settled = bool(context.get("colonists")) and roofed_beds >= len(context["colonists"])
    supply = float((context.get("power_info") or {}).get("current_power") or 0)
    demand = float((context.get("power_info") or {}).get("total_consumption") or 0)
    return {"required_buildings": required, "missing_research": prerequisites, "short_season": short_season,
            "soil_unlocked": basic, "hydroponics_unlocked": hydro, "settled": settled,
            "soil_daytime_w": watts, "hydroponics_daytime_w": watts + 8 * float((index.get("HydroponicsBasin") or {}).get("nominal_power_consumption") or 70),
            "current_generation_w": supply, "current_consumption_w": demand,
            "has_sun_lamp": bool(counts.get("SunLamp")),
            "guidance": "Research early in tundra/ice or short growing seasons. Finish warm human shelter first. A greenhouse needs roof, grow light, suitable soil or researched basins, heating/cooling and continuous connected power. Lamp draws daytime peak; basins/heating need night power. Brownouts can kill hydroponic crops. Choose energy supply and crops separately; do not assume a single wood generator is sufficient."}


def generate_greenhouse_variants(program: str, context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    info = greenhouse_context(context)
    hydro = program == "greenhouse_hydroponics"
    if not info["hydroponics_unlocked" if hydro else "soil_unlocked"] or not info["settled"]:
        return {}
    # Compact enough for a supported roof, with no floors covering fertile soil.
    width = height = 13
    material = str(context.get("material") or "WoodLog")
    index = catalog_index(context.get("building_catalog") or [])
    items = _shell(width, height, material, str(context.get("entry_side") or "south"), 6)
    items.append(building("SunLamp", 6, 6))
    if context.get("climate") == "cold":
        items.append(building("Heater", 11, 6))
        if info["short_season"]:
            items.append(building("Heater", 1, 6))
    elif context.get("climate") == "hot":
        cooler_z = 8 if context.get("entry_side") == "east" else 6
        items = [i for i in items if (i["rel_x"], i["rel_z"]) != (12, cooler_z)]
        items.append(building("Cooler", 12, cooler_z, rotation=1))
    if hydro:
        # Vanilla basins are 1x4 north-facing; rotation east makes a 4x1 row.
        basin = index["HydroponicsBasin"]
        if (int(basin.get("size_x") or 1), int(basin.get("size_z") or 4)) != (1, 4):
            return {}  # A modded footprint needs a compatible layout, not clipping.
        for z in (3, 5, 7, 9):
            for x in (3, 8):
                items.append(building("HydroponicsBasin", x, z, rotation=1))
    # Transmitters may share cells with walls and other buildings, including the
    # lamp. A continuous cross avoids a wire stopping at a wall or dead-end.
    cables = {(x, 6) for x in range(1, 12)} | {(6, z) for z in range(13)}
    items.extend(building("PowerConduit", x, z) for x, z in sorted(cables))
    layout = resolve_layout_materials({**blueprint(items, width, height), "roof": True}, index, context.get("item_counts") or {})
    if layout is None:
        return {}
    watts = sum(float(index.get(i["def_name"], {}).get("nominal_power_consumption") or 0)
                for i in items)
    if not watts:
        watts = info["hydroponics_daytime_w" if hydro else "soil_daytime_w"]
    return {program + "_1": {"program": program, "style": "hydroponics" if hydro else "soil", "name": PROGRAM_CATALOG[program]["label"],
            "width": width, "height": height, "layout": layout, "planned_power_w": watts,
            "summary": f"13×13 roofed room, SunLamp, {'8 basins/32 growing cells' if hydro else 'unfloored fertile soil'}; climate {context.get('climate')}; connected internal cable cross; peak about {watts:.0f} W plus existing colony demand. Requires external grid connection and dependable supply. Select crops after temperature/light/power are verified; do not sow on cold blueprints."}}


def generate_program_variants(program: str, context: dict[str, Any], *, seed: int = 0) -> dict[str, dict[str, Any]]:
    if program in {"greenhouse_soil", "greenhouse_hydroponics"}:
        return generate_greenhouse_variants(program, context)
    catalog = context.get("building_catalog") or []
    if program == "freezer" and not _available(catalog_index(catalog), "Cooler"):
        return {}
    finished = set(map(str, context.get("finished_research") or []))
    item_counts = context.get("item_counts") or {}
    material = str(context.get("material") or "WoodLog")
    powered = bool(context.get("powered"))
    climate = str(context.get("climate") or "temperate")
    if program == "residence":
        return generate_house_candidates(material, catalog, finished, item_counts, powered=powered,
                                         climate=climate, seed=seed, entry_side=str(context.get("entry_side") or ""))

    sizes = {
        "residential_compound": [(13, 10), (15, 11), (17, 12)],
        "dining_recreation": [(9, 9), (11, 9), (13, 11)],
        "kitchen": [(7, 7), (8, 7), (9, 8)],
        "freezer": [(7, 7), (9, 7), (10, 8)],
        "hospital": [(9, 9), (11, 9), (13, 11)],
        "throne_room": [(9, 11), (11, 11), (13, 13)],
        "temple": [(9, 9), (11, 11), (13, 11)],
        "workshop": [(8, 7), (9, 8), (11, 9)],
        "factory": [(9, 8), (11, 9), (13, 10)],
        "research_lab": [(8, 8), (10, 9), (12, 10)],
        "storage": [(9, 8), (11, 9), (13, 10)],
        "prison": [(8, 7), (10, 8), (12, 9)],
        "barn": [(9, 7), (11, 8), (13, 9)],
        "nursery": [(9, 8), (11, 9), (13, 10)],
        "power_utility": [(9, 7), (11, 8), (13, 9)],
        "defense": [(9, 9), (11, 9), (13, 9)],
    }.get(program, [(9, 9)])
    if program == "throne_room":
        minimum_area = max(
            (int(row.get("minimum_throne_room_area") or 0) for row in (context.get("royalty") or {}).get("colonists", [])),
            default=0,
        )
        minimum_side = max(7, int(math.ceil(math.sqrt(max(1, minimum_area)))))
        # Width/height include walls, while Royalty requirements measure the
        # usable interior. Every option must satisfy the title's minimum area.
        sizes = [
            (minimum_side + 2 + extra * 2, minimum_side + 2)
            for extra in range(3)
        ]
    index = catalog_index(catalog)
    result: dict[str, dict[str, Any]] = {}
    for variant, (width, height) in enumerate(sizes):
        layout = _defense_variant(material, variant, index) if program == "defense" else _furnished_room(
            program, width, height, material, catalog, finished, item_counts,
            powered, climate, variant, context, seed,
        )
        layout = resolve_layout_materials(layout, index, item_counts)
        if layout is None:
            continue
        option_id = f"{program}_{variant + 1}"
        defs = Counter(row["def_name"] for row in layout["buildings"])
        highlights = ", ".join(f"{name}×{count}" for name, count in defs.items() if name not in {"Wall", "Door", "PowerConduit"})
        result[option_id] = {
            "id": option_id,
            "program": program,
            "style": ("compact", "standard", "expanded")[min(variant, 2)],
            "name": f"{PROGRAM_CATALOG.get(program, {}).get('label', program)} {variant + 1}",
            "summary": f"{width}×{height}; {highlights or 'functional shell'}; wall {material}; "
                       f"entry {context.get('entry_side') or 'generated'}; light included",
            "width": width,
            "height": height,
            "layout": layout,
        }
    return result


def estimated_stuff_cost(layout: dict[str, Any], building_catalog: list[dict[str, Any]]) -> dict[str, int]:
    """Estimate stuff, fixed ingredients and known floors before offering a plan."""
    index = catalog_index(building_catalog)
    fallback = {"Wall": 5, "Door": 25, "AnimalFlap": 10, "Barricade": 5}
    cost: Counter[str] = Counter()
    for item in layout.get("buildings") or []:
        definition = str(item.get("def_name") or "")
        catalog_row = index.get(definition) or {}
        material = str(item.get("stuff_def_name") or "")
        if material:
            amount = int(catalog_row.get("cost_stuff_count") or fallback.get(definition, 0))
            cost[material] += max(0, amount)
        for ingredient in catalog_row.get("cost_list") or []:
            resource = str(ingredient.get("thing_def") or "")
            if resource:
                cost[resource] += max(0, int(ingredient.get("count") or 0))
    floor_costs = {
        "WoodPlankFloor": {"WoodLog": 3},
        "MetalTile": {"Steel": 7},
        "SterileTile": {"Steel": 3, "Silver": 12},
    }
    for tile in layout.get("floors") or []:
        definition = str(tile.get("def_name") or "")
        ingredients = floor_costs.get(definition)
        if ingredients is None and definition.startswith("Tile"):
            ingredients = {f"Blocks{definition.removeprefix('Tile')}": 4}
        for resource, amount in (ingredients or {}).items():
            cost[resource] += amount
    return dict(cost)


def layout_anchor_conflicts(layout: dict[str, Any]) -> list[tuple[int, int]]:
    """Reject obviously overlapping or out-of-bounds blueprint anchors.

    The engine remains authoritative for multi-cell footprints and modded
    placement rules; this check catches errors in our own generated plans.
    """
    width, height = int(layout.get("width") or 0), int(layout.get("height") or 0)
    occupied: set[tuple[int, int]] = set()
    conflicts: list[tuple[int, int]] = []
    for item in layout.get("buildings") or []:
        cell = (int(item.get("rel_x") or 0), int(item.get("rel_z") or 0))
        if item.get("def_name") in {"PowerConduit", "HiddenConduit", "WaterproofConduit"}:
            if not (0 <= cell[0] < width and 0 <= cell[1] < height):
                conflicts.append(cell)
            continue
        if cell in occupied or not (0 <= cell[0] < width and 0 <= cell[1] < height):
            conflicts.append(cell)
        occupied.add(cell)
    return conflicts


def affordable_variants(variants: dict[str, dict[str, Any]], context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Keep layouts whose known material costs fit stock plus modest reserves."""
    stock = context.get("item_counts") or {}
    catalog = context.get("building_catalog") or []
    affordable: dict[str, dict[str, Any]] = {}
    for key, variant in variants.items():
        if layout_anchor_conflicts(variant["layout"]):
            continue
        costs = estimated_stuff_cost(variant["layout"], catalog)
        if all(int(stock.get(material) or 0) >= amount + (
                   80 if material == "WoodLog" else 50 if material.startswith("Blocks") else
                   100 if material == "Steel" else 1 if material.startswith("Component") else 0)
               for material, amount in costs.items()):
            affordable[key] = {**variant, "estimated_stuff_cost": costs,
                               "summary": f"{variant['summary']}; estimated materials {costs}"}
    return affordable


def affordable_material_options(program: str, context: dict[str, Any],
                                material_options: dict[str, str], *, seed: int = 0) -> dict[str, str]:
    """Offer Laya only wall materials with at least one buildable layout."""
    result = {}
    for material, description in material_options.items():
        trial = {**context, "material": material}
        variants = affordable_variants(generate_program_variants(program, trial, seed=seed), trial)
        if variants:
            minimum = min(variant["estimated_stuff_cost"].get(material, 0) for variant in variants.values())
            result[material] = f"{description}; smallest plan needs about {minimum} units plus reserve"
    return result


def program_options(context: dict[str, Any]) -> dict[str, str]:
    """Expose relevant programs with colony need context, not every layout."""
    counts = context.get("building_counts") or {}
    rooms = context.get("rooms") or []
    colonists = context.get("colonists") or []
    animals = context.get("animals") or []
    royalty = context.get("royalty") or {}
    ideology = context.get("ideology") or {}
    storage = context.get("storage") or {}
    professions = context.get("professions") or {}
    doctrine = context.get("doctrine") or {}
    chosen_direction = str(doctrine.get("specialization") or "")
    direction_buildings = set(((professions.get("directions") or {}).get(chosen_direction) or {}).get("building_programs") or [])
    direction_buildings.update(map(str, doctrine.get("building_programs") or []))
    strategic_direction = str(doctrine.get("primary_direction") or chosen_direction)
    private_rooms = sum(1 for room in rooms if "bedroom" in str(room.get("role_label") or "").lower() and not room.get("is_prison_cell"))
    medical_beds = sum(1 for row in context.get("buildings") or [] if row.get("medical"))
    patient_count = len(context.get("potential_patients") or [])
    options: dict[str, str] = {}
    greenhouse = greenhouse_context(context)
    if greenhouse["settled"] and not greenhouse["has_sun_lamp"]:
        for program, available in (("greenhouse_soil", greenhouse["soil_unlocked"]), ("greenhouse_hydroponics", greenhouse["hydroponics_unlocked"])):
            if available:
                watts = greenhouse["hydroponics_daytime_w" if "hydroponics" in program else "soil_daytime_w"]
                options[program] = (f"{'Short outdoor season; ' if greenhouse['short_season'] else ''}{PROGRAM_CATALOG[program]['label']}; researched components; about {watts:.0f} W peak added to existing demand; generation now {greenhouse['current_generation_w']:.0f} W. Choose sufficient power and roofed thermal control; crops later. Soil variant needs fertile ground, hydroponics admits only compatible crops.")
    if private_rooms < len(colonists):
        options["residence"] = f"Housing shortage: {private_rooms} private bedrooms for {len(colonists)} colonists; 24 generated house variants"
        if len(colonists) - private_rooms >= 3:
            options["residential_compound"] = "Several separate bedrooms plus a shared lit central room; faster than isolated houses"
    if not any(name in counts for name in ("Table2x2c", "Table1x2c", "Table2x4c")):
        options["dining_recreation"] = "No proper shared dining hall; a pleasant high-use room gives broad mood value"
    if not any(int(counts.get(name) or 0) > 0 for name in ("FueledStove", "ElectricStove")):
        options["kitchen"] = "No stove; creates a clean lit cooking room and keeps butchery elsewhere"
    if medical_beds < max(2, len(colonists) // 3):
        options["hospital"] = f"Medical capacity {medical_beds}, current/potential patients {patient_count}; variants upgrade normal beds to hospital beds, monitor, clean floor and light when technology permits"
    if any(row.get("requires_throne_room") and row.get("has_unmet_throne_room_requirements") for row in royalty.get("colonists", [])):
        titles = ", ".join(str(row.get("title_label")) for row in royalty.get("colonists", []) if row.get("requires_throne_room"))
        requirement_rows = [row for row in royalty.get("colonists", []) if row.get("requires_throne_room")]
        requirements = sorted({str(value) for row in requirement_rows for value in (row.get("throne_room_requirements") or [])})
        area = max((int(row.get("minimum_throne_room_area") or 0) for row in requirement_rows), default=0)
        impressiveness = max((float(row.get("minimum_throne_room_impressiveness") or 0) for row in requirement_rows), default=0)
        options["throne_room"] = (
            f"Royal requirement is unmet for {titles}; minimum area {area}, impressiveness {impressiveness}; "
            f"requirements {requirements}; no beds or production benches are included"
        )
    if ideology.get("active"):
        options["temple"] = "Ideology is active; a dedicated floored ritual room avoids invalid mixed-room uses"
    if animals:
        options["barn"] = f"{len(animals)} colony animals; sleeping places, light/climate and optional straw floor"
    if not any(int(counts.get(name) or 0) > 0 for name in ("SimpleResearchBench", "HiTechResearchBench")) or "research_lab" in direction_buildings:
        options["research_lab"] = "Research room with the best unlocked bench, strong light and optional sterile flooring/multi-analyzer"
    if "workshop" in direction_buildings or not any((row.get("is_work_table") for row in context.get("building_catalog") or [])):
        options["workshop"] = "Workshop matched to the chosen workforce specialization, with nearby input shelves and lighting"
    if "factory" in direction_buildings or "Fabrication" in set(map(str, context.get("finished_research") or [])):
        options["factory"] = "Powered industrial room for unlocked advanced workbenches and short hauling paths"
    if int(storage.get("utilization_percent") or 0) >= 75:
        options["storage"] = f"Storage is {int(storage.get('utilization_percent') or 0)}% full; shelved warehouse increases density"
    if not any(room.get("is_prison_cell") for room in rooms):
        options["prison"] = "No valid prison cell; secure beds, table and light for capture/recruitment"
    if any(int(pawn.get("age") or 99) < 13 for pawn in colonists):
        options["nursery"] = "Children present; cribs, learning furniture and safe indoor light when DLC definitions exist"
    if int(context.get("wealth") or 0) >= 30000 or not any(int(counts.get(name) or 0) > 0 for name in ("Barricade", "Sandbags", "TurretGun")):
        options["defense"] = "Layered funnel/firing line; later variants add turrets only when actually unlocked"
    if not any(int(counts.get(name) or 0) > 0 for name in ("WoodFiredGenerator", "SolarGenerator", "WindTurbine")):
        options["power_utility"] = "No durable power block; generator, battery/conduit and fire protection where available"
    # Stable colonies may consider specialization buildings even when a basic
    # need is already satisfied.
    for program in direction_buildings:
        if program in PROGRAM_CATALOG:
            options.setdefault(program, f"Supports chosen strategic/workforce direction {strategic_direction}: {PROGRAM_CATALOG[program]['label']}")
    return options


def workbench_upgrade_options(development: dict[str, Any]) -> dict[str, dict[str, Any]]:
    counts = development.get("building_counts") or {}
    catalog = catalog_index(development.get("building_catalog") or [])
    item_counts = development.get("item_counts") or {}
    options: dict[str, dict[str, Any]] = {}
    for old, new, benefit in WORKBENCH_UPGRADE_CHAINS:
        if int(counts.get(old) or 0) <= 0 or int(counts.get(new) or 0) > 0:
            continue
        target = catalog.get(new)
        if catalog and (not target or not target.get("available_now")):
            continue
        affordable = True
        missing = []
        for cost in (target or {}).get("cost_list") or []:
            name = str(cost.get("thing_def") or "")
            amount = int(cost.get("count") or 0)
            if int(item_counts.get(name) or 0) < amount:
                affordable = False
                missing.append(f"{name} {amount}")
        stuff_cost = int((target or {}).get("cost_stuff_count") or 0)
        stuff = select_building_stuff(
            target or {}, item_counts,
            str((development.get("doctrine") or {}).get("material") or ""),
            reserve=80,
        ) if stuff_cost else None
        if stuff_cost and not stuff:
            affordable = False
            missing.append(f"compatible stuff {stuff_cost}")
        if not affordable:
            continue
        options[f"{old}|{new}"] = {
            "old": old,
            "new": new,
            "benefit": benefit,
            "research": (target or {}).get("research_prerequisites") or [],
            "costs": (target or {}).get("cost_list") or [],
            "stuff": stuff,
            "stuff_cost": stuff_cost,
            "missing": missing,
        }
    return options


def select_building_stuff(
    building_def: dict[str, Any],
    item_counts: dict[str, Any],
    preferred: str = "",
    *,
    reserve: int = 0,
) -> str | None:
    """Choose a compatible material from live StuffCategoryDef metadata."""
    amount = int(building_def.get("cost_stuff_count") or 0)
    if amount <= 0:
        return None
    exact_allowed = building_def.get("allowed_stuff_defs")
    categories = {str(value).lower() for value in building_def.get("stuff_categories") or []}

    def compatible(name: str) -> bool:
        if isinstance(exact_allowed, list):
            return name in exact_allowed
        lowered = name.lower()
        if name == "Jade":
            return not categories or any("stone" in category or "stony" in category for category in categories)
        if name == "WoodLog":
            return not categories or any("wood" in category for category in categories)
        if name in {"Steel", "Plasteel", "Gold", "Silver", "Uranium"}:
            return not categories or any("metal" in category for category in categories)
        if lowered.startswith("blocks"):
            return not categories or any("stone" in category or "stony" in category for category in categories)
        if name in {"Cloth", "DevilstrandCloth", "Hyperweave", "Synthread"} or "leather" in lowered or "wool" in lowered:
            return not categories or any("fabric" in category or "textile" in category for category in categories)
        # This catalog does not expose StuffCategoryDefs for arbitrary modded
        # materials. Never mistake components or food for construction stuff.
        return False

    candidates = [preferred, "WoodLog", "Steel", "BlocksSandstone", "BlocksGranite", "BlocksLimestone", "BlocksSlate", "BlocksMarble", "Plasteel",
                  *sorted(item_counts, key=lambda name: -int(item_counts.get(name) or 0))]
    for name in dict.fromkeys(value for value in candidates if value):
        if compatible(name) and int(item_counts.get(name) or 0) >= amount + reserve:
            return name
    return None


def catalog_construction_options(development: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    """Expose every unlocked, affordable live building by its real category.

    The full catalog remains in the snapshot. Laya chooses a category, then an
    exact def; no hand-maintained list can silently omit a new DLC or mod bench.
    """
    stock = development.get("item_counts") or {}
    counts = development.get("building_counts") or {}
    options: dict[str, dict[str, dict[str, Any]]] = {}
    for row in development.get("building_catalog") or []:
        if not isinstance(row, dict) or not row.get("def_name") or not row.get("available_now") or row.get("metadata_error"):
            continue
        fixed: Counter[str] = Counter()
        for cost in row.get("cost_list") or []:
            name = str(cost.get("thing_def") or "")
            if name:
                fixed[name] += max(0, int(cost.get("count") or 0))
        if any(int(stock.get(name) or 0) < amount for name, amount in fixed.items()):
            continue
        stuff_count = max(0, int(row.get("cost_stuff_count") or 0))
        materials: dict[str, str] = {}
        if stuff_count:
            for name in stock:
                if int(stock.get(name) or 0) < stuff_count + fixed.get(name, 0):
                    continue
                if select_building_stuff(row, {name: int(stock[name])}, name) == name:
                    materials[name] = f"{stuff_count} {name}; stock {int(stock[name])}"
            if not materials:
                continue
        name = str(row["def_name"])
        category = str(row.get("designation_category") or "Other")
        options.setdefault(category, {})[name] = {
            "def_name": name,
            "construction_kind": str(row.get("construction_kind") or "building"),
            "label": str(row.get("label") or name),
            "description": " ".join(str(row.get("description") or "").split())[:160],
            "category": category,
            "size_x": max(1, int(row.get("size_x") or 1)),
            "size_z": max(1, int(row.get("size_z") or 1)),
            "cost_list": dict(fixed),
            "cost_stuff_count": stuff_count,
            "materials": materials,
            "requires_power": bool(row.get("requires_power")),
            "is_power_generator": bool(row.get("is_power_generator")),
            "requires_fuel": bool(row.get("requires_fuel")),
            "nominal_power_output": float(row.get("nominal_power_output") or 0),
            "minimum_construction_skill": int(row.get("minimum_construction_skill") or 0),
            "is_work_table": bool(row.get("is_work_table")),
            "existing_count": int(counts.get(name) or 0),
        }
    return options


def catalog_access_audit(development: dict[str, Any],
                         options: dict[str, dict[str, dict[str, Any]]] | None = None) -> dict[str, Any]:
    """Account for every loaded definition, including locked and unaffordable ones."""
    rows = [row for row in development.get("building_catalog") or []
            if isinstance(row, dict) and row.get("def_name")]
    plans = options if options is not None else catalog_construction_options(development)
    actionable = {name for category in plans.values() for name in category}
    unlocked = {str(row["def_name"]) for row in rows if row.get("available_now") and not row.get("metadata_error")}
    return {
        "loaded": len(rows),
        "unlocked": len(unlocked),
        "affordable_now": len(actionable),
        "locked_or_metadata_error": sorted(str(row["def_name"]) for row in rows if str(row["def_name"]) not in unlocked),
        "need_materials": sorted(unlocked - actionable),
        "categories": {name: len(category) for name, category in sorted(plans.items())},
    }


def resolve_layout_materials(layout: dict[str, Any], catalog: dict[str, dict[str, Any]],
                             item_counts: dict[str, Any]) -> dict[str, Any] | None:
    """Choose compatible stuff for each building from the live game catalog."""
    if not catalog:
        return layout
    resolved_items = []
    for item in layout.get("buildings") or []:
        row = catalog.get(str(item.get("def_name") or "")) or {}
        if int(row.get("cost_stuff_count") or 0) <= 0:
            resolved_items.append(item)
            continue
        material = select_building_stuff(row, item_counts, str(item.get("stuff_def_name") or ""))
        if not material:
            return None
        if item.get("def_name") in {"Wall", "Door", "AnimalFlap", "Barricade"} and material != item.get("stuff_def_name"):
            # The wall palette was chosen by Laya. Never silently substitute
            # a different shell material while resolving secondary furniture.
            return None
        resolved_items.append({**item, "stuff_def_name": material})
    return {**layout, "buildings": resolved_items}
