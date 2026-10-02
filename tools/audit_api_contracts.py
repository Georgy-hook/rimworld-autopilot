"""Offline client/server route inventory. Does not contact or start RimWorld.

This checks route/method wiring, not runtime payload values or native job success.
Dynamic routes are listed separately and require their module scenario tests.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def inventory(root=ROOT):
    routes = {}
    for path in (root / "vendor/RIMAPI/Source/RIMAPI").rglob("*.cs"):
        text = path.read_text(encoding="utf-8-sig")
        for match in re.finditer(r'\[(Get|Post|Put|Delete|Patch)\("([^"\s]+)"', text):
            routes.setdefault((match[1].upper(), match[2]), []).append(str(path.relative_to(root)))
    calls, dynamic = [], []
    for path in sorted(root.glob("*.py")):
        if not (path.name.startswith("colony_") or path.name in {"rimworld_laya.py", "stream_observer.py"}):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else ""
            method, index = ("GET", 1) if name == "safe_get" else (name.upper(), 0)
            if method not in {"GET", "POST", "PUT", "DELETE", "PATCH"} or len(node.args) <= index:
                continue
            arg = node.args[index]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith("/api/"):
                calls.append({"method": method, "path": arg.value, "file": path.name, "line": node.lineno,
                              "registered": (method, arg.value) in routes})
            elif not isinstance(arg, ast.Constant):
                receiver = ast.unparse(node.func.value) if isinstance(node.func, ast.Attribute) else ""
                # Variable and concatenated endpoints are not literal evidence.
                # Avoid treating ordinary dictionary.get(key) as an HTTP call.
                if name == "safe_get" or receiver == "client" or receiver.endswith(".client") or "/api/" in ast.unparse(arg):
                    dynamic.append({"method": method, "expression": ast.unparse(arg), "file": path.name, "line": node.lineno})
    return {"registered_routes": len(routes), "literal_calls": calls, "dynamic_calls": dynamic,
            "missing": [row for row in calls if not row["registered"]],
            "duplicate_routes": [{"method": key[0], "path": key[1], "files": value}
                                 for key, value in routes.items() if len(value) > 1],
            "runtime_contacted": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = inventory()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"registered_routes": data["registered_routes"], "literal_calls": len(data["literal_calls"]),
                      "missing": data["missing"], "dynamic_calls": len(data["dynamic_calls"]),
                      "duplicate_routes": data["duplicate_routes"], "runtime_contacted": False}))
    return int(bool(data["missing"] or data["duplicate_routes"]))


if __name__ == "__main__":
    raise SystemExit(main())
