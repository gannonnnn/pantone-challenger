#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []

for path in sorted(ROOT.rglob("*.py")):
    if any(part in {".venv", ".git", ".work"} for part in path.parts):
        continue
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        errors.append(f"Python syntax: {path.relative_to(ROOT)}: {exc}")

for path in sorted((ROOT / "config").glob("*.yml")):
    try:
        yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"YAML syntax: {path.relative_to(ROOT)}: {exc}")

for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
    try:
        yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"Workflow YAML syntax: {path.relative_to(ROOT)}: {exc}")

sources = yaml.safe_load((ROOT / "config/sources.yml").read_text())["sources"]
sectors: dict[str, int] = {}
for source in sources:
    sectors[source["sector"]] = sectors.get(source["sector"], 0) + 1
if len(sources) != 48:
    errors.append(f"Expected 48 panel sources, found {len(sources)}")
if len(sectors) != 12:
    errors.append(f"Expected 12 panel sectors, found {len(sectors)}")
if set(sectors.values()) != {4}:
    errors.append(f"Panel is not balanced: {sectors}")

for forbidden in (".env", "INSTAGRAM_ACCESS_TOKEN=", "BLUESKY_APP_PASSWORD="):
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in {".git", ".venv"} for part in path.parts):
            continue
        if path.name == ".env.example" and forbidden != ".env":
            continue
        if forbidden == ".env" and path.name == ".env":
            errors.append("A real .env file is present")
            break

test = subprocess.run(
    [sys.executable, "-m", "pytest", "-q"],
    cwd=ROOT,
    text=True,
    capture_output=True,
)
if test.returncode:
    errors.append("pytest failed:\n" + test.stdout + "\n" + test.stderr)

report = {
    "passed": not errors,
    "python": sys.version,
    "sources": len(sources),
    "sectors": len(sectors),
    "sector_counts": sectors,
    "pytest_output": test.stdout.strip(),
    "errors": errors,
}
(ROOT / "release-validation.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
if errors:
    print("\n\n".join(errors), file=sys.stderr)
    raise SystemExit(1)
print(json.dumps(report, indent=2))
