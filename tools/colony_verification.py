"""Build a comparable evidence card and layout from saved observations only.

No network, model inference, game commands or writes to the running director.
Unknown outcomes remain unknown; a building or accepted order is not a result.
"""
from __future__ import annotations

import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path


def read_json(path: Path | None, fallback):
    return json.loads(path.read_text(encoding="utf-8")) if path else fallback


def definition(row):
    return row.get("def") or row.get("def_name") or row.get("plant_def_name")


def observed_counts(rows):
    return dict(Counter(definition(row) or "unknown" for row in rows))


def project(row, fields):
    return {field: row.get(field) for field in fields}


def evidence_card(snapshot, evidence, metadata, timeline, decisions, events, review, baseline):
    ending = evidence.get("native_ending") or evidence.get("ending") or {}
    campaign = ending.get("campaign_id")
    if not campaign or campaign != metadata.get("campaign_id"):
        raise ValueError("A verified matching campaign_id is required")
    if len(decisions) > 100:
        raise ValueError("Supply at most 100 decisions from a bounded 8 MB tail")
    dev = snapshot.get("development") or {}
    buildings = dev.get("buildings")
    baseline_buildings = (baseline.get("development") or {}).get("buildings")
    original_ids = {b.get("id") for b in baseline_buildings or []}
    new_buildings = ([b for b in buildings if b.get("id") not in original_ids]
                     if buildings is not None and baseline_buildings is not None else None)
    zones = dev.get("zones")
    growing = ([z for z in zones if z.get("type") == "Zone_Growing"]
               if zones is not None else None)
    rooms = dev.get("rooms")
    bed_rooms = ([project(r, ("id", "role_def_name", "temperature", "open_roof_count",
                             "cleanliness", "impressiveness", "contained_beds_ids", "min", "max"))
                  for r in rooms if r.get("contained_beds_ids")] if rooms is not None else None)
    choices = Counter((r.get("decision") or {}).get("choice") or r.get("mode") or "unknown"
                      for r in decisions)
    rejections = Counter((r.get("result") or {}).get("reason") or "unspecified"
                         for r in decisions if (r.get("result") or {}).get("applied") is False)
    jobs = {}
    for sample in timeline:
        for pawn in sample.get("colonists") or []:
            identity = str(pawn.get("id"))
            jobs.setdefault(identity, Counter())[pawn.get("job") or pawn.get("current_job") or "unknown"] += 1
    food_samples = [s["resources"] for s in timeline if isinstance(s.get("resources"), dict)]
    letters = events.get("letters") or []
    raid_announcements = [project(row, ("id", "label", "arrival_tick", "text"))
                          for row in letters if str(row.get("label") or "").startswith("Raid:")]
    deaths = [project(row, ("id", "label", "arrival_tick", "text"))
              for row in letters if row.get("letter_def") == "Death"]
    clinical = [{**project(p, ("id", "name", "health", "hunger", "mood", "downed", "bleeding_rate",
                               "current_job", "health_conditions"))} for p in snapshot.get("colonists") or []]
    # The ledger is the observed transactions, not the doctrine's economy label.
    ledger = evidence.get("trade_ledger")
    if ledger is None and timeline:
        ledger = timeline[-1].get("trade_ledger")
    doctrine = evidence.get("doctrine") or (timeline[-1].get("doctrine") if timeline else None)
    card = {
        "schema_version": 1, "campaign_id": campaign,
        "colony": metadata.get("colony"), "tile": (snapshot.get("map") or {}).get("tile_id"),
        "source_revision": metadata.get("source_commit") or metadata.get("python_commit"),
        "captured_at_utc": evidence.get("captured_at_utc"),
        "game": snapshot.get("game"), "native_ending": ending,
        "settlement": {"buildings": buildings, "counts": observed_counts(buildings) if buildings is not None else None,
                       "new_since_baseline": observed_counts(new_buildings) if new_buildings is not None else None,
                       "bed_rooms": bed_rooms, "power": dev.get("power_info"),
                       "projects": dev.get("construction_projects"), "work_tables": dev.get("work_tables")},
        "agriculture": {"zones": growing, "farm": dev.get("farm"), "weather": dev.get("weather")},
        "site": {"tile_details": dev.get("tile_details"), "review": review.get("site"),
                 "zone_coordinates": review.get("zone_coordinates")},
        "nutrition": {"stock": (snapshot.get("map") or {}).get("resources"),
                      "timeline_samples": len(food_samples),
                      "stock_zero_samples": sum(s.get("food") == 0 for s in food_samples),
                      "max_meals": max((s["meals"] for s in food_samples if s.get("meals") is not None), default=None)},
        "population": {"on_map": clinical, "caravans": dev.get("caravans"),
                       "quests": {group: [project(q, ("id", "quest_def", "name", "state", "ever_accepted"))
                                          for q in rows] for group, rows in (dev.get("quests") or {}).items()},
                       "verified_status_changes": review.get("population_changes", [])},
        "animals": {"current": snapshot.get("animals"), "verified_losses": review.get("animal_losses", []),
                    "coverage": review.get("animal_loss_coverage", "Only supplied evidence; not a complete lifetime count")},
        "raids": {"recent_announcements": raid_announcements, "verified_outcomes": review.get("raid_outcomes", []),
                  "unreviewed_outcomes": "Unknown; no enemies in one poll does not establish a repelled raid"},
        "economy": {"doctrine": doctrine, "transactions": ledger,
                    "verified_income": review.get("income", None), "review": review.get("economy")},
        "progression": {"research": dev.get("current_research"), "finished_research": dev.get("finished_research"),
                        "ending_evidence": ending, "review": review.get("progression")},
        "priorities": {"bounded_decision_count": len(decisions), "choices": dict(choices),
                       "rejection_reasons": dict(rejections), "sampled_jobs_by_pawn": jobs,
                       "window_start": timeline[0].get("time_utc") if timeline else None,
                       "window_end": timeline[-1].get("time_utc") if timeline else None},
        "recent_native_death_letters": deaths,
        "assessment": review.get("assessment", {}), "screenshot": review.get("screenshot"),
        "limits": ["No counterfactual guarantee of survival", "Unknown is not zero or pass",
                   "Snapshots are sequential observations, not an atomic whole-game transaction",
                   "A declared plan, accepted command or building count does not establish useful completion"],
    }
    return card


def layout_svg(card):
    """A labeled coordinate diagram, distinct from an actual game screenshot."""
    buildings = card["settlement"].get("buildings") or []
    positions = [b["position"] for b in buildings if isinstance(b.get("position"), dict)]
    if not positions:
        raise ValueError("No observed building coordinates for a layout")
    xs, zs = [p["x"] for p in positions], [p["z"] for p in positions]
    lo_x, hi_x, lo_z, hi_z = min(xs)-2, max(xs)+3, min(zs)-2, max(zs)+3
    scale = min(16, 1000 / max(hi_x-lo_x, hi_z-lo_z))
    margin = 36
    width, height = (hi_x-lo_x)*scale+margin*2, (hi_z-lo_z)*scale+margin*2
    colors = {"Wall": "#52647a", "Door": "#f4bd59", "Bed": "#80b8ee", "Campfire": "#f68c4e",
              "ButcherSpot": "#ef8faa", "SimpleResearchBench": "#b998ee", "ElectricStove": "#ed9572",
              "WoodFiredGenerator": "#d3b059", "Cooler": "#69d0df", "PowerConduit": "#efd76a",
              "TrapSpike": "#d85f69", "Barricade": "#a27859", "Fence": "#667961"}
    legend_height = 90+len(card["settlement"]["counts"])*15
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width+330:.0f}" height="{max(height,legend_height):.0f}">',
           '<rect width="100%" height="100%" fill="#15202e"/>',
           '<g font-family="sans-serif" font-size="11" fill="#eef4fb">',
           f'<text x="20" y="20">Observed coordinates; tick {escape(str((card.get("game") or {}).get("tick")))}</text>']
    for zone in (card.get("site", {}).get("zone_coordinates") or {}).get("zones", []):
        for cell in zone.get("cells", []):
            # Save-derived cells carry a separate save tick in the evidence card.
            values = str(cell).strip("() ").split(",")
            if len(values) != 3:
                continue
            x, _, z = map(int, values)
            out.append(f'<rect x="{margin+(x-lo_x)*scale:.1f}" y="{margin+(hi_z-z-1)*scale:.1f}" '
                       f'width="{scale:.1f}" height="{scale:.1f}" fill="#a562aa" opacity=".5">'
                       f'<title>Zone {escape(str(zone.get("id")))} {escape(str(zone.get("plant")))}</title></rect>')
    for b in buildings:
        p, size = b.get("position"), b.get("size") or {}
        if not isinstance(p, dict):
            continue
        sx, sz = size.get("x") or 1, size.get("z") or 1
        if b.get("rotation", 0) % 2:
            sx, sz = sz, sx
        x = margin+(p["x"]-lo_x-(sx-1)/2)*scale
        y = margin+(hi_z-p["z"]-(sz-1)/2-1)*scale
        name = definition(b) or "unknown"
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{sx*scale:.1f}" height="{sz*scale:.1f}" '
                   f'fill="{colors.get(name,"#718076")}" stroke="#15202e" stroke-width=".6">'
                   f'<title>{escape(name)} {b.get("id")} @ {p["x"]},{p["z"]}</title></rect>')
        if name not in ("Wall", "Fence", "Barricade", "Grave", "TrapSpike", "AnimalSleepingSpot"):
            out.append(f'<text x="{x:.1f}" y="{y+10:.1f}" font-size="8" fill="#081522">{b.get("id")}</text>')
    out.append(f'<text x="{width+12:.0f}" y="42" font-size="15">Building inventory</text>')
    for index, (name, count) in enumerate(sorted(card["settlement"]["counts"].items())):
        out.append(f'<text x="{width+12:.0f}" y="{64+index*15}">{escape(name)}: {count}</text>')
    out.extend(['</g>', '</svg>'])
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("snapshot", "evidence", "metadata", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    for name in ("timeline", "decisions-tail", "events", "review", "baseline", "layout"):
        parser.add_argument(f"--{name}", type=Path)
    args = parser.parse_args()
    # Only prepared JSON evidence, never a full decisions.jsonl history.
    if args.decisions_tail and args.decisions_tail.suffix != ".json":
        parser.error("--decisions-tail requires a prepared bounded JSON array")
    card = evidence_card(read_json(args.snapshot, {}), read_json(args.evidence, {}),
                         read_json(args.metadata, {}), read_json(args.timeline, []),
                         read_json(args.decisions_tail, []), read_json(args.events, {}),
                         read_json(args.review, {}), read_json(args.baseline, {}))
    card["sources"] = {name: str(getattr(args, name).resolve()) for name in
                       ("snapshot", "evidence", "metadata", "timeline", "decisions_tail", "events", "review", "baseline")
                       if getattr(args, name)}
    protected = {Path(path) for path in card["sources"].values()}
    for output in (args.output, args.layout):
        if output and output.resolve() in protected:
            parser.error("An output cannot overwrite source evidence")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.layout:
        args.layout.parent.mkdir(parents=True, exist_ok=True)
        args.layout.write_text(layout_svg(card), encoding="utf-8")
    print(json.dumps({"campaign_id": card["campaign_id"], "card": str(args.output.resolve()),
                      "layout": str(args.layout.resolve()) if args.layout else None}, ensure_ascii=False))


if __name__ == "__main__":
    main()
