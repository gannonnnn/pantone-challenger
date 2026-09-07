#!/usr/bin/env python3
"""Release checks specific to Pantone Challenger V1.5.2."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        ERRORS.append(message)


required = [
    ROOT / "challenger" / "temporal_semantic_integrity.py",
    ROOT / "config" / "temporal_semantic_integrity.json",
    ROOT / "docs" / "TEMPORAL_AND_SEMANTIC_INTEGRITY.md",
    ROOT / "tests" / "test_temporal_semantic_integrity.py",
    ROOT / ".github" / "workflows" / "daily.yml",
]
for path in required:
    require(path.exists(), f"Missing required V1.5.2 file: {path.relative_to(ROOT)}")

config_path = ROOT / "config" / "temporal_semantic_integrity.json"
if config_path.exists():
    config = json.loads(config_path.read_text(encoding="utf-8"))
    require(config.get("methodology_version") == "1.5.2", "Methodology version must be 1.5.2")
    require(int(config.get("baseline_days_required", 0)) >= 7, "At least seven baseline days are required")
    require(float(config.get("muted_cluster_max_diameter", 1)) < float(config.get("chromatic_cluster_max_diameter", 0)), "Muted clusters must use a tighter diameter")
    require(int(config.get("candidate_min_sources", 0)) >= 6, "Candidate source floor must be at least six")

workflow_path = ROOT / ".github" / "workflows" / "daily.yml"
if workflow_path.exists():
    workflow = workflow_path.read_text(encoding="utf-8")
    require("Enforce temporal and semantic integrity" in workflow, "Daily workflow is missing the integrity postflight step")
    require("python -m challenger.temporal_semantic_integrity" in workflow, "Daily workflow does not invoke the integrity module")
    require("resolve-date --value" in workflow, "Daily workflow must retain the corrected date CLI syntax")

try:
    sys.path.insert(0, str(ROOT))
    from challenger.temporal_semantic_integrity import _load_config, _temporal_status
    cfg = _load_config(ROOT)
    status, *_ = _temporal_status(
        {
            "source_id": "future",
            "domain": "art",
            "signal_stage": "creation",
            "panel_type": "discovery",
            "event_type": "newly_published",
            "source_url": "https://example.test/2026/09/06/item",
        },
        date(2026, 9, 5),
        {"sources": {}},
        "fingerprint",
        cfg,
    )
    require(status == "rejected_future", "Future-dated evidence smoke test failed")
except Exception as exc:  # pragma: no cover
    ERRORS.append(f"Could not import or smoke-test integrity module: {exc}")

if ERRORS:
    print("V1.5.2 validation failed:")
    for error in ERRORS:
        print(f"- {error}")
    raise SystemExit(1)

print("V1.5.2 temporal and semantic integrity validation passed.")
