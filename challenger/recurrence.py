from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .colors import delta, hex_from_oklab, oklab_from_hex, oklab_to_oklch
from .models import Candidate, RecurrenceSummary


SECTOR_LABELS = {
    "technology": "tech",
    "retail": "retail",
    "food_beverage": "food & beverage",
    "entertainment": "entertainment",
    "beauty": "beauty",
    "travel": "travel",
    "finance": "finance",
    "automotive": "automotive",
    "sports": "sports",
    "home": "home & design",
    "fashion": "fashion",
    "gaming": "gaming",
}


def human_sector(value: str) -> str:
    return SECTOR_LABELS.get(value, value.replace("_", " "))


def human_sector_list(values: Iterable[str], *, limit: int = 4) -> str:
    labels = [human_sector(value) for value in values]
    if limit > 0:
        labels = labels[:limit]
    if not labels:
        return "multiple commercial sectors"
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return f"{', '.join(labels[:-1])}, and {labels[-1]}"


def _base_hue_family(hue: float) -> str:
    if hue < 15 or hue >= 345:
        return "Rose"
    if hue < 45:
        return "Red"
    if hue < 70:
        return "Orange"
    if hue < 95:
        return "Gold"
    if hue < 118:
        return "Yellow"
    if hue < 138:
        return "Chartreuse"
    if hue < 175:
        return "Green"
    if hue < 210:
        return "Teal"
    if hue < 240:
        return "Cyan Blue"
    if hue < 280:
        return "Blue"
    if hue < 315:
        return "Violet"
    return "Magenta"


def color_family_name(lab: Iterable[float]) -> str:
    lightness, chroma, hue = oklab_to_oklch(lab)
    if chroma < 0.028:
        if lightness >= 0.93:
            return "White"
        if lightness >= 0.76:
            return "Light Gray"
        if lightness >= 0.48:
            return "Gray"
        if lightness >= 0.22:
            return "Charcoal"
        return "Black"

    if chroma < 0.095:
        if 12 <= hue < 48:
            return "Clay Red"
        if 48 <= hue < 78:
            return "Burnt Orange"
        if 78 <= hue < 108:
            return "Ochre"
        if 108 <= hue < 145:
            return "Olive Green"
        if 145 <= hue < 185:
            return "Sage Green"
        if 185 <= hue < 235:
            return "Slate Teal"
        if 235 <= hue < 305:
            return "Slate Blue"
        if 305 <= hue < 345:
            return "Dusty Magenta"
        return "Dusty Rose"

    return _base_hue_family(hue)


def winner_lab(result: dict[str, Any]) -> tuple[float, float, float] | None:
    winner = result.get("winner") or {}
    raw = winner.get("oklab")
    if isinstance(raw, list) and len(raw) == 3:
        try:
            return tuple(float(value) for value in raw)
        except (TypeError, ValueError):
            return None
    value = winner.get("hex")
    if isinstance(value, str):
        try:
            return oklab_from_hex(value)
        except ValueError:
            return None
    return None


def load_ready_results(
    archive_root: Path,
    *,
    year: int | None = None,
    before: date | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not archive_root.exists():
        return results
    for result_path in sorted(archive_root.glob("????-??-??/result.json")):
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            result_date = date.fromisoformat(str(payload.get("date", "")))
        except (OSError, ValueError, TypeError):
            continue
        if payload.get("status") != "ready" or not payload.get("winner"):
            continue
        if year is not None and result_date.year != year:
            continue
        if before is not None and result_date >= before:
            continue
        if winner_lab(payload) is None:
            continue
        results.append(payload)
    results.sort(key=lambda item: item["date"])
    return results


def cluster_ready_results(
    results: list[dict[str, Any]],
    distance_threshold: float,
) -> list[list[dict[str, Any]]]:
    """Group winners with complete-link perceptual matching.

    A result may join a family only when it is within the fixed OKLab threshold
    of every existing member. This prevents a chain of gradually shifting shades
    from silently turning one color family into another.
    """
    clusters: list[list[dict[str, Any]]] = []
    for result in sorted(results, key=lambda item: item["date"]):
        lab = winner_lab(result)
        if lab is None:
            continue
        compatible: list[tuple[float, list[dict[str, Any]]]] = []
        for cluster in clusters:
            distances = [
                delta(lab, member_lab)
                for member in cluster
                if (member_lab := winner_lab(member)) is not None
            ]
            if distances and max(distances) <= distance_threshold:
                compatible.append((max(distances), cluster))
        if compatible:
            _, best = min(compatible, key=lambda item: item[0])
            best.append(result)
        else:
            clusters.append([result])
    return clusters


def _longest_streak(values: Iterable[str]) -> int:
    days = sorted(date.fromisoformat(value) for value in values)
    if not days:
        return 0
    longest = 1
    current = 1
    for previous, following in zip(days, days[1:]):
        if following == previous + timedelta(days=1):
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def calculate_recurrence(
    *,
    archive_root: Path,
    target_date: date,
    winner: Candidate,
    panel_size: int,
    captured_sources: int,
    distance_threshold: float,
) -> RecurrenceSummary:
    historical = load_ready_results(
        archive_root,
        year=target_date.year,
        before=target_date,
    )
    current_payload = {
        "date": target_date.isoformat(),
        "status": "ready",
        "panel_size": panel_size,
        "captured_sources": captured_sources,
        "winner": winner.to_dict(),
    }
    year_results = [*historical, current_payload]
    clusters = cluster_ready_results(year_results, distance_threshold)
    all_matching = next(
        cluster
        for cluster in clusters
        if any(item["date"] == target_date.isoformat() for item in cluster)
    )
    matching = [item for item in all_matching if item["date"] != target_date.isoformat()]

    labs = [winner_lab(result) for result in all_matching]
    valid_labs = [lab for lab in labs if lab is not None]
    representative = tuple(
        float(value) for value in np.mean(np.asarray(valid_labs, dtype=float), axis=0)
    )

    company_names: dict[str, str] = {}
    sector_counter: Counter[str] = Counter()
    supporting_company_days = 0
    analyzed_counts: list[int] = []
    panel_counts: list[int] = []
    for result in all_matching:
        candidate = result.get("winner") or {}
        ids = list(candidate.get("source_ids") or [])
        names = list(candidate.get("source_names") or [])
        for index, source_id in enumerate(ids):
            source_name = names[index] if index < len(names) else source_id
            company_names[str(source_id)] = str(source_name)
        supporting_company_days += int(candidate.get("source_count", len(ids)) or 0)
        for sector in candidate.get("sectors") or []:
            sector_counter[str(sector)] += 1
        analyzed_counts.append(int(result.get("captured_sources", 0) or 0))
        panel_counts.append(int(result.get("panel_size", panel_size) or panel_size))

    ordered_sectors = [
        sector for sector, _ in sorted(
            sector_counter.items(),
            key=lambda item: (-item[1], human_sector(item[0])),
        )
    ]
    matching_dates = [str(result["date"]) for result in all_matching]
    matching_date_set = {date.fromisoformat(value) for value in matching_dates}
    streak = 0
    cursor = target_date
    while cursor in matching_date_set:
        streak += 1
        cursor -= timedelta(days=1)

    ready_days = len(year_results)
    return RecurrenceSummary(
        year=target_date.year,
        family_name=color_family_name(representative),
        representative_hex=hex_from_oklab(representative),
        distance_threshold=distance_threshold,
        winning_days=len(all_matching),
        previous_winning_days=len(matching),
        current_streak=streak,
        longest_streak=_longest_streak(matching_dates),
        first_win_date=min(matching_dates),
        latest_win_date=max(matching_dates),
        matching_dates=matching_dates,
        unique_company_count=len(company_names),
        unique_company_ids=sorted(company_names),
        unique_company_names=[company_names[key] for key in sorted(company_names)],
        panel_company_count=max([panel_size, *panel_counts]),
        supporting_company_days=supporting_company_days,
        average_analyzed_company_pages=round(
            sum(analyzed_counts) / max(len(analyzed_counts), 1),
            1,
        ),
        sectors=ordered_sectors,
        sector_count=len(ordered_sectors),
        sector_day_counts=dict(sector_counter),
        ready_days_in_year=ready_days,
    )
