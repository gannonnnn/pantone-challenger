from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def summarize(report_path: str = ".work/latest/collection-report.json") -> dict:
    path = Path(report_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    statuses = Counter(item.get("report", {}).get("status", "unknown") for item in data)
    by_domain = Counter(item.get("source", {}).get("domain", "unknown") for item in data if item.get("regions"))
    return {"statuses": dict(statuses), "captured_by_domain": dict(by_domain)}


if __name__ == "__main__":
    import sys

    print(json.dumps(summarize(sys.argv[1] if len(sys.argv) > 1 else ".work/latest/collection-report.json"), indent=2))
