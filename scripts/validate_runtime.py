from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from challenger.config import load_settings, load_sources, source_is_configured



def main() -> int:
    errors: list[str] = []
    settings = load_settings()
    _, sources = load_sources()
    capture = settings.get("capture", {})
    active = [source for source in sources if source.enabled and source_is_configured(source)]
    benchmark = [source for source in active if source.panel_type.value == "benchmark"]
    discovery_limit = int(settings.get("discovery", {}).get("sources_per_run", 0))
    declared_run_size = len(benchmark) + min(
        discovery_limit,
        sum(source.panel_type.value == "discovery" for source in active),
    )
    workers = int(capture.get("browser_workers", 0))
    source_timeout = float(capture.get("browser_source_timeout_s", 0))
    collection_budget = float(capture.get("collection_budget_s", 0))
    theoretical_browser_seconds = (
        ((declared_run_size + max(1, workers) - 1) // max(1, workers)) * source_timeout
    )

    if workers < 4:
        errors.append("browser_workers must be at least 4")
    if not 0 < source_timeout <= 75:
        errors.append("browser_source_timeout_s must be between 1 and 75 seconds")
    if not 0 < collection_budget <= 20 * 60:
        errors.append("collection_budget_s must be no more than 20 minutes")
    if theoretical_browser_seconds >= collection_budget:
        errors.append(
            "The configured browser waves can exceed the collection budget before all sources start"
        )
    if float(capture.get("http_timeout_s", 0)) > 15:
        errors.append("http_timeout_s must be at most 15 seconds")
    if int(capture.get("max_candidate_regions", 0)) > 8:
        errors.append("max_candidate_regions must be at most 8")

    workflow = (ROOT / ".github/workflows/daily.yml").read_text(encoding="utf-8")
    required_snippets = [
        "timeout-minutes: 35",
        'PYTHONUNBUFFERED: "1"',
        "Upload failed-run diagnostics",
        "continue-on-error: true",
        "cancel-in-progress: true",
        "actions/upload-artifact@v7",
        "timeout --signal=TERM --kill-after=30s 28m",
    ]
    for snippet in required_snippets:
        if snippet not in workflow:
            errors.append(f"Daily workflow lacks runtime guard: {snippet}")

    required_files = [
        ROOT / "challenger/runtime.py",
        ROOT / "tests/test_runtime.py",
        ROOT / "scripts/source_health.py",
    ]
    for path in required_files:
        if not path.exists():
            errors.append(f"Missing runtime file: {path.relative_to(ROOT)}")

    report = {
        "methodology_version": settings.get("methodology_version"),
        "declared_run_size": declared_run_size,
        "browser_workers": workers,
        "browser_source_timeout_seconds": source_timeout,
        "theoretical_browser_wave_seconds": theoretical_browser_seconds,
        "collection_budget_seconds": collection_budget,
        "errors": errors,
    }
    (ROOT / "runtime-validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
