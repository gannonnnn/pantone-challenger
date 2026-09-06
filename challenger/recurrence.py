from __future__ import annotations

import json
from pathlib import Path

from challenger.color import distance, hex_to_oklab


def recurrence_for_candidates(archive_dir: str | Path, year: int, candidates: list, current_date: str) -> dict:
    root = Path(archive_dir)
    output = {}
    for candidate in candidates:
        matched_dates = []
        unique_sources = set()
        domains = set()
        day_share = 0.0
        day_dirs = sorted(root.glob(f"{year}-*")) if root.exists() else []
        for day_dir in day_dirs:
            if not day_dir.is_dir() or day_dir.name >= current_date:
                continue
            result_path = day_dir / "result.json"
            if not result_path.exists():
                continue
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            if result.get("state") != "ready":
                continue
            winners = result.get("challenger", [])
            matched = [w for w in winners if distance(hex_to_oklab(w["hex"]), candidate.oklab) <= 0.055]
            if not matched:
                continue
            matched_dates.append(day_dir.name)
            day_share += 1.0 / max(1, len(winners))
            for winner in matched:
                unique_sources.update(e.get("source_id", "") for e in winner.get("evidence", []))
                domains.update(e.get("domain", "") for e in winner.get("evidence", []))
        output[candidate.hex] = {
            "appearance_days": len(matched_dates) + 1,
            "leaderboard_day_share": round(day_share + 1.0 / max(1, len(candidates)), 2),
            "matching_dates": matched_dates + [current_date],
            "unique_sources": len(unique_sources | {e.source_id for e in candidate.evidence}),
            "domains": sorted(domains | {e.domain for e in candidate.evidence}),
        }
    return output
