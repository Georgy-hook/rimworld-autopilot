"""Index installed Learning Helper concepts without copying game prose."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import xml.etree.ElementTree as ET

def inventory(game: Path) -> dict:
    concepts, errors, definitions = [], [], {}
    for dlc in sorted((game / "Data").iterdir()):
        if not (dlc / "Defs").is_dir():
            continue
        counts = Counter()
        for source in sorted((dlc / "Defs").rglob("*.xml")):
            try:
                root = ET.parse(source).getroot()
            except (OSError, ET.ParseError) as exc:
                errors.append({"file": str(source.relative_to(game)), "error": str(exc)})
                continue
            for node in root:
                if node.tag == "ConceptDef":
                    concepts.append({"content": dlc.name, "id": node.findtext("defName"),
                                     "source": source.relative_to(game).as_posix(),
                                     "parent": node.get("ParentName")})
                if node.findtext("defName"):
                    counts[node.tag] += 1
        definitions[dlc.name] = dict(sorted(counts.items()))
    return {"schema": 1, "source_version": (game / "Version.txt").read_text().strip(),
            "installed_content": sorted(definitions), "odyssey_installed": "Odyssey" in definitions,
            "concepts": concepts, "definition_counts": definitions, "parse_errors": errors,
            "interpretation": "Discovery only; executable coverage requires native API, director reachability and scenario QA."}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = inventory(args.game)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps({"concepts": len(data["concepts"]), "content": data["installed_content"], "errors": len(data["parse_errors"])}))
