from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from challenger.color import distance, hex_to_oklab


def load_history(
    archive_dir: str | Path,
    before_date: str,
    limit_days: int = 30,
    *,
    compatibility_key: str = "",
) -> list[dict[str, Any]]:
    root = Path(archive_dir)
    history = []
    if not root.exists():
        return history
    for day_dir in sorted((p for p in root.iterdir() if p.is_dir() and p.name < before_date), reverse=True):
        if compatibility_key:
            manifest_path = day_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if str(manifest.get("baseline_compatibility_key", "")) != compatibility_key:
                continue
        path = day_dir / "observations.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        history.append({"date": day_dir.name, "observations": payload})
        if len(history) >= limit_days:
            break
    return list(reversed(history))


def source_color_history(
    history: list[dict[str, Any]],
    candidate_lab: tuple[float, float, float],
    threshold: float = 0.055,
) -> dict[str, dict[str, float]]:
    days_by_source: dict[str, int] = defaultdict(int)
    present_by_source: dict[str, int] = defaultdict(int)
    share_sum: dict[str, float] = defaultdict(float)
    last_share: dict[str, float] = defaultdict(float)
    for day in history:
        seen_today: dict[str, float] = {}
        for obs in day.get("observations", []):
            source_id = str(obs.get("source_id", ""))
            if not source_id:
                continue
            days_by_source[source_id] += 0  # counted once below
            best = 0.0
            for swatch in obs.get("swatches", []):
                try:
                    lab = tuple(swatch.get("oklab") or hex_to_oklab(swatch["hex"]))
                except Exception:  # noqa: BLE001
                    continue
                if distance(lab, candidate_lab) <= threshold:
                    best = max(
                        best,
                        float(swatch.get("adjusted_share", swatch.get("share", 0.0)) or 0.0),
                    )
            seen_today[source_id] = max(seen_today.get(source_id, 0.0), best)
        for source_id, share in seen_today.items():
            days_by_source[source_id] += 1
            if share > 0:
                present_by_source[source_id] += 1
                share_sum[source_id] += share
                last_share[source_id] = share
    result = {}
    for source_id, days in days_by_source.items():
        present = present_by_source[source_id]
        result[source_id] = {
            "days": float(days),
            "present_days": float(present),
            "frequency": present / days if days else 0.0,
            "mean_share": share_sum[source_id] / present if present else 0.0,
            "last_share": last_share[source_id],
        }
    return result


def panel_candidate_history(
    history: list[dict[str, Any]], candidate_lab: tuple[float, float, float], threshold: float = 0.055
) -> dict[str, float]:
    counts = []
    domain_counts = []
    for day in history:
        sources = set()
        domains = set()
        for obs in day.get("observations", []):
            matched = False
            for swatch in obs.get("swatches", []):
                try:
                    lab = tuple(swatch.get("oklab") or hex_to_oklab(swatch["hex"]))
                except Exception:  # noqa: BLE001
                    continue
                if distance(lab, candidate_lab) <= threshold:
                    matched = True
                    break
            if matched:
                sources.add(str(obs.get("source_id", "")))
                domains.add(str(obs.get("domain", "")))
        counts.append(len(sources))
        domain_counts.append(len(domains))
    return {
        "days": float(len(history)),
        "mean_source_count": sum(counts) / len(counts) if counts else 0.0,
        "mean_domain_count": sum(domain_counts) / len(domain_counts) if domain_counts else 0.0,
        "previous_source_count": float(counts[-1]) if counts else 0.0,
    }
