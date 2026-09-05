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

source_payload = yaml.safe_load((ROOT / "config/sources.yml").read_text())
panel_version = str(source_payload.get("panel_version", ""))
if panel_version != "1.3":
    errors.append(f"Expected panel version 1.3, found {panel_version!r}")
sources = source_payload["sources"]
sectors: dict[str, int] = {}
for source in sources:
    sectors[source["sector"]] = sectors.get(source["sector"], 0) + 1
if len(sources) != 48:
    errors.append(f"Expected 48 panel sources, found {len(sources)}")
if len(sectors) != 12:
    errors.append(f"Expected 12 panel sectors, found {len(sectors)}")
if set(sectors.values()) != {4}:
    errors.append(f"Panel is not balanced: {sectors}")

expected_registry = {
    "spotify": "entertainment",
    "max": "entertainment",
    "playstation": "gaming",
    "epic-games-store": "gaming",
    "nike": "sports",
    "peloton": "sports",
    "apple": "technology",
    "sephora": "beauty",
}
source_by_id = {source["id"]: source for source in sources}
for source_id, sector in expected_registry.items():
    actual = source_by_id.get(source_id, {}).get("sector")
    if actual != sector:
        errors.append(f"Registry mismatch for {source_id}: {actual!r} != {sector!r}")

for source in sources:
    status = source.get("brand_mark_status", "text_only")
    if status not in {"approved", "text_only"}:
        errors.append(f"Invalid brand mark status for {source['id']}: {status}")
    if status == "approved":
        mark = ROOT / str(source.get("brand_mark_path", ""))
        if not mark.is_file():
            errors.append(f"Approved mark is missing for {source['id']}: {mark}")

daily_workflow = (ROOT / ".github/workflows/daily.yml").read_text(encoding="utf-8")
publish_workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
if "workflow_dispatch:" not in daily_workflow or "schedule:" in daily_workflow:
    errors.append("Daily Challenger must remain manual-only during V1.3 calibration")
if "workflow_dispatch:" not in publish_workflow or "schedule:" in publish_workflow:
    errors.append("Social publishing must remain manual-only during V1.3 calibration")

for required in (
    ROOT / "challenger/evidence.py",
    ROOT / "challenger/integrity.py",
    ROOT / "docs/v1.3-repair-spec.md",
    ROOT / "assets/brands/README.md",
):
    if not required.is_file():
        errors.append(f"Required V1.3 file is missing: {required.relative_to(ROOT)}")

for path in ROOT.rglob("*"):
    if not path.is_file():
        continue
    if any(part in {"preview", "previews", "demo-output"} for part in path.parts):
        errors.append(f"Preview/demo file is present in production: {path.relative_to(ROOT)}")
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} and "assets/brands" not in str(path):
        errors.append(f"Unexpected bundled image in production: {path.relative_to(ROOT)}")

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
    "panel_version": panel_version,
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
