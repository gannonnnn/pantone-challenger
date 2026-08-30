from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from .colors import delta, hex_from_oklab, oklab_to_oklch
from .config import Settings
from .models import (
    Candidate,
    QualityGate,
    Source,
    SourceObservation,
    Swatch,
    observation_from_dict,
)


HistoryDay = list[SourceObservation]


def load_history(
    archive_root: Path,
    target_date: date,
    lookback_days: int,
) -> list[HistoryDay]:
    history: list[HistoryDay] = []
    for offset in range(lookback_days, 0, -1):
        day = target_date - timedelta(days=offset)
        path = archive_root / day.isoformat() / "observations.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            raw = payload.get("observations", payload if isinstance(payload, list) else [])
            observations = [observation_from_dict(item) for item in raw]
            if observations:
                history.append(observations)
        except (OSError, ValueError, TypeError, KeyError):
            continue
    return history


def _history_by_source(history: list[HistoryDay]) -> dict[str, list[SourceObservation]]:
    index: dict[str, list[SourceObservation]] = defaultdict(list)
    for day in history:
        for observation in day:
            index[observation.source_id].append(observation)
    return index


def _source_baseline(
    source_history: list[SourceObservation],
    lab: tuple[float, float, float],
    distance_threshold: float,
) -> tuple[float, float]:
    if not source_history:
        return 0.0, 0.0
    shares: list[float] = []
    present = 0
    for observation in source_history:
        nearest = None
        nearest_distance = float("inf")
        for swatch in observation.swatches:
            current_distance = delta(lab, swatch.oklab)
            if current_distance < nearest_distance:
                nearest, nearest_distance = swatch, current_distance
        if nearest is not None and nearest_distance <= distance_threshold:
            shares.append(nearest.share)
            present += 1
        else:
            shares.append(0.0)
    return float(np.mean(shares)), present / len(source_history)


def apply_source_baselines(
    observations: list[SourceObservation],
    history: list[HistoryDay],
    settings: Settings,
) -> None:
    index = _history_by_source(history)
    confidence = min(len(history) / max(settings.baseline_warmup_days, 1), 1.0)
    for observation in observations:
        source_history = index.get(observation.source_id, [])
        for swatch in observation.swatches:
            baseline_share, _ = _source_baseline(
                source_history,
                swatch.oklab,
                settings.source_cluster_distance,
            )
            if baseline_share <= 0:
                rarity_adjusted = swatch.share
            else:
                rarity = swatch.share / (swatch.share + 2.0 * baseline_share + 1e-9)
                factor = (1.0 - settings.baseline_suppression) + (
                    settings.baseline_suppression * rarity
                )
                rarity_adjusted = swatch.share * factor
            swatch.adjusted_share = (
                (1.0 - confidence) * swatch.share + confidence * rarity_adjusted
            )
            if source_history:
                previous = source_history[-1]
                if (
                    observation.screenshot_hashes
                    and previous.screenshot_hashes
                    and observation.screenshot_hashes == previous.screenshot_hashes
                ):
                    swatch.adjusted_share *= settings.unchanged_page_factor


def _build_cluster_members(
    observations: list[SourceObservation],
    distance_threshold: float,
) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    entries: list[tuple[SourceObservation, Swatch]] = []
    for observation in observations:
        for swatch in observation.swatches:
            if swatch.share >= 0.025:
                entries.append((observation, swatch))
    entries.sort(key=lambda item: item[1].adjusted_share, reverse=True)

    for observation, swatch in entries:
        best_index = None
        best_distance = float("inf")
        for index, cluster in enumerate(clusters):
            current = delta(swatch.oklab, cluster["lab"])
            if current < best_distance:
                best_index, best_distance = index, current
        if best_index is None or best_distance > distance_threshold:
            clusters.append(
                {
                    "lab": np.asarray(swatch.oklab, dtype=float),
                    "members": {observation.source_id: (observation, swatch)},
                }
            )
            continue

        cluster = clusters[best_index]
        existing = cluster["members"].get(observation.source_id)
        if existing is None or existing[1].adjusted_share < swatch.adjusted_share:
            cluster["members"][observation.source_id] = (observation, swatch)

        members = list(cluster["members"].values())
        weights = np.asarray(
            [max(member[1].adjusted_share, 1e-6) for member in members], dtype=float
        )
        labs = np.asarray([member[1].oklab for member in members], dtype=float)
        cluster["lab"] = np.average(labs, axis=0, weights=weights)

    return clusters


def _neutral_penalty(oklch: tuple[float, float, float]) -> float:
    lightness, chroma, _ = oklch
    if chroma >= 0.065:
        penalty = 0.0
    elif chroma <= 0.025:
        penalty = 18.0
    else:
        penalty = 18.0 * (0.065 - chroma) / 0.040
    if chroma < 0.055 and (lightness > 0.92 or lightness < 0.12):
        penalty += 5.0
    return min(penalty, 23.0)


def score_candidates(
    observations: list[SourceObservation],
    sources: list[Source],
    history: list[HistoryDay],
    settings: Settings,
) -> list[Candidate]:
    if not observations:
        return []
    apply_source_baselines(observations, history, settings)
    clusters = _build_cluster_members(observations, settings.cluster_distance)
    history_index = _history_by_source(history)
    usable_sources = len(observations)
    usable_sectors = len({observation.sector for observation in observations})
    candidates: list[Candidate] = []

    for cluster in clusters:
        members: dict[str, tuple[SourceObservation, Swatch]] = cluster["members"]
        if len(members) < 2:
            continue
        lab = tuple(float(v) for v in cluster["lab"])
        oklch = oklab_to_oklch(lab)
        member_items = list(members.values())
        source_count = len(member_items)
        sector_counter = Counter(observation.sector for observation, _ in member_items)
        sectors = sorted(sector_counter)
        sector_count = len(sectors)
        prevalence = source_count / max(usable_sources, 1)
        sector_breadth = sector_count / max(usable_sectors, 1)
        mean_salience = float(
            np.mean([swatch.adjusted_share for _, swatch in member_items])
        )

        baseline_probabilities: list[float] = []
        for observation in observations:
            _, probability = _source_baseline(
                history_index.get(observation.source_id, []),
                lab,
                settings.cluster_distance,
            )
            baseline_probabilities.append(probability)
        baseline_prevalence = (
            float(np.mean(baseline_probabilities)) if baseline_probabilities else 0.0
        )

        if len(history) < settings.baseline_warmup_days:
            momentum = 0.50
        else:
            ratio = (prevalence + 0.02) / (baseline_prevalence + 0.02)
            momentum = min(1.0, max(0.0, 0.40 + 0.30 * math.log2(max(ratio, 1e-6))))

        independence_component = min(source_count / 12.0, 1.0)
        sector_component = min(sector_breadth / 0.65, 1.0)
        prevalence_component = min(prevalence / 0.35, 1.0)
        salience_component = min(mean_salience / 0.30, 1.0)
        neutral_penalty = _neutral_penalty(oklch)
        concentration = max(sector_counter.values()) / source_count
        concentration_penalty = (
            0.0
            if concentration <= 0.50
            else min(12.0, 12.0 * (concentration - 0.50) / 0.50)
        )
        components = {
            "source_breadth": round(independence_component * 30.0, 3),
            "sector_breadth": round(sector_component * 22.0, 3),
            "momentum": round(momentum * 20.0, 3),
            "visual_salience": round(salience_component * 18.0, 3),
            "prevalence": round(prevalence_component * 10.0, 3),
        }
        score = sum(components.values()) - neutral_penalty - concentration_penalty
        ordered = sorted(
            member_items,
            key=lambda item: item[1].adjusted_share,
            reverse=True,
        )
        candidates.append(
            Candidate(
                hex=hex_from_oklab(lab),
                oklab=lab,
                oklch=oklch,
                score=round(max(score, 0.0), 3),
                source_count=source_count,
                sector_count=sector_count,
                source_ids=[item[0].source_id for item in ordered],
                source_names=[item[0].source_name for item in ordered],
                sectors=sectors,
                prevalence=round(prevalence, 5),
                sector_breadth=round(sector_breadth, 5),
                mean_salience=round(mean_salience, 5),
                momentum=round(momentum, 5),
                baseline_prevalence=round(baseline_prevalence, 5),
                neutral_penalty=round(neutral_penalty, 3),
                concentration_penalty=round(concentration_penalty, 3),
                components=components,
                source_sectors=[item[0].sector for item in ordered],
                source_salience=[round(item[1].adjusted_share, 5) for item in ordered],
            )
        )

    candidates.sort(
        key=lambda candidate: (
            candidate.score,
            candidate.source_count,
            candidate.sector_count,
            candidate.oklch[1],
        ),
        reverse=True,
    )
    return candidates


def evaluate_quality(
    candidates: list[Candidate],
    observations: list[SourceObservation],
    sources: list[Source],
    settings: Settings,
) -> QualityGate:
    reasons: list[str] = []
    usable_sources = len(observations)
    configured_sources = len(sources)
    usable_sectors = len({item.sector for item in observations})
    configured_sectors = len({item.sector for item in sources})

    if usable_sources < settings.min_usable_sources:
        reasons.append(
            f"Only {usable_sources} sources were usable; at least "
            f"{settings.min_usable_sources} are required."
        )
    if usable_sectors < settings.min_usable_sectors:
        reasons.append(
            f"Only {usable_sectors} sectors were usable; at least "
            f"{settings.min_usable_sectors} are required."
        )
    if len(candidates) < settings.min_candidates:
        reasons.append(
            f"Only {len(candidates)} color candidates were supported; at least "
            f"{settings.min_candidates} are required."
        )
    if candidates:
        winner = candidates[0]
        if winner.source_count < settings.min_winner_sources:
            reasons.append(
                f"The leading color appeared in only {winner.source_count} independent "
                f"sources; at least {settings.min_winner_sources} are required."
            )
        if winner.sector_count < settings.min_winner_sectors:
            reasons.append(
                f"The leading color crossed only {winner.sector_count} sectors; at least "
                f"{settings.min_winner_sectors} are required."
            )
    else:
        reasons.append("No supported color candidate was found.")

    return QualityGate(
        passed=not reasons,
        reasons=reasons,
        usable_sources=usable_sources,
        configured_sources=configured_sources,
        usable_sectors=usable_sectors,
        configured_sectors=configured_sectors,
    )
