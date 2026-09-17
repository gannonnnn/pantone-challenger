from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from challenger.pipeline import DailyPipeline
from challenger.reports import write_json
from challenger.runtime import RuntimeLedger
from challenger.serialize import clean


def run_health_check(output: Path, *, date_value: str = "auto", max_sources: int = 0) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    pipeline = DailyPipeline(
        archive_dir=output / "archive-unused",
        work_dir=output,
    )
    resolved = pipeline.resolve_date(date_value)
    active, unconfigured = pipeline._select_sources(resolved, max_sources)
    ledger = RuntimeLedger(output / resolved, total_sources=len(active))
    try:
        ledger.start_phase("source health collection")
        results = pipeline._collect(active, resolved, ledger)
        ledger.end_phase("source health collection")
        statuses = Counter(result.report.get("status", "unknown") for result in results)
        captured_by_domain = Counter(
            result.source.domain.value for result in results if result.regions
        )
        payload = {
            "date": resolved,
            "declared_sources": len(active),
            "unconfigured_sources": [source.id for source in unconfigured],
            "status_counts": dict(sorted(statuses.items())),
            "captured_by_domain": dict(sorted(captured_by_domain.items())),
            "results": [
                {
                    "source": clean(result.source),
                    "report": result.report,
                    "region_count": len(result.regions),
                }
                for result in results
            ],
        }
        write_json(output / "collection-report.json", payload)
        ledger.finalize(status="complete", extra={"health_report": str(output / "collection-report.json")})
        return payload
    except BaseException as exc:
        ledger.fail(exc)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the bounded Pantone Challenger source-health check.")
    parser.add_argument("--output", type=Path, default=Path(".work/source-health"))
    parser.add_argument("--date", default="auto")
    parser.add_argument("--max-sources", type=int, default=0)
    args = parser.parse_args()
    payload = run_health_check(args.output, date_value=args.date, max_sources=args.max_sources)
    print(json.dumps({key: value for key, value in payload.items() if key != "results"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
