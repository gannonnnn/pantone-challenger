from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from .colors import delta, hex_from_oklab, oklab_from_hex, oklab_to_oklch
from .config import Settings
from .evidence import best_local_evidence
from .models import Candidate, QualityGate, Source, SourceObservation, Swatch, observation_from_dict
from .naming import family_label_for_candidate


HistoryDay = list[SourceObservation]


def load_history(
    archive_root: Path,
    target_date: date,
    lookback_days: int,
    *,
    methodology_version: str = "1.3.0",
) -> list[HistoryDay]:
    """Load prior non-blocked observations used for source-specific baselines.

    Calibration-only days are included after they are merged because their purpose
    is to warm source baselines. Blocked days are excluded.
    """
    history: list[HistoryDay] = []
    for offset in range(lookback_days, 0, -1):
        day = target_date - timedelta(days=offset)
        day_dir = archive_root / day.isoformat()
        result_path = day_dir / "result.json"
        observations_path = day_dir / "observations.json"
        if not result_path.exists() or not observations_path.exists():
            continue
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
            if result.get("status") not in {"ready", "review_only"}:
                continue
            expected_series = ".".join(methodology_version.split(".")[:2]) + "."
            if not str(result.get("methodology_version", "")).startswith(expected_series):
                continue
            payload = json.loads(observations_path.read_text(encoding="utf-8"))
            raw = payload.get("observations", payload if isinstance(payload, list) else [])
            observations = [
                observation
                for item in raw
                if (observation := observation_from_dict(item)).regions
            ]
        except (OSError, ValueError, TypeError, KeyError):
            continue
        if observations:
            history.append(observations)
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
        nearest: Swatch | None = None
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
    sources: list[Source] | None = None,
) -> None:
    """Reduce persistent house colors without deleting them from the record."""
    history_index = _history_by_source(history)
    source_index = {source.id: source for source in (sources or [])}
    baseline_confidence = min(len(history) / max(settings.baseline_warmup_days, 1), 1.0)

    for observation in observations:
        source_history = history_index.get(observation.source_id, [])
        configured = source_index.get(observation.source_id)
        house_labs: list[tuple[float, float, float]] = []
        for value in configured.known_house_colors if configured else ():
            try:
                house_labs.append(oklab_from_hex(value))
            except ValueError:
                continue

        unchanged = False
        if source_history:
            previous = source_history[-1]
            unchanged = bool(
                observation.screenshot_hashes
                and previous.screenshot_hashes
                and observation.screenshot_hashes == previous.screenshot_hashes
            )

        for swatch in observation.swatches:
            baseline_share, _ = _source_baseline(
                source_history,
                swatch.oklab,
                settings.source_cluster_distance,
            )
            if baseline_share <= 0:
                adjusted = swatch.share
            else:
                rarity = swatch.share / (swatch.share + 2.0 * baseline_share + 1e-9)
                suppression_factor = (1.0 - settings.baseline_suppression) + (
                    settings.baseline_suppression * rarity
                )
                baseline_adjusted = swatch.share * suppression_factor
                adjusted = (
                    (1.0 - baseline_confidence) * swatch.share
                    + baseline_confidence * baseline_adjusted
                )

            if any(
                delta(swatch.oklab, house_lab) <= settings.source_cluster_distance
                for house_lab in house_labs
            ):
                adjusted *= 0.35
            if unchanged:
                adjusted *= settings.unchanged_page_factor
            swatch.adjusted_share = max(adjusted, 0.0)


def _build_cluster_members(
    observations: list[SourceObservation],
    distance_threshold: float,
) -> list[dict[str, Any]]:
    """Cluster company-level swatches while retaining at most one vote per company."""
    clusters: list[dict[str, Any]] = []
    entries: list[tuple[SourceObservation, Swatch]] = []
    for observation in observations:
        for swatch in observation.swatches:
            if swatch.share >= 0.018:
                entries.append((observation, swatch))
    entries.sort(key=lambda item: item[1].adjusted_share, reverse=True)

    for observation, swatch in entries:
        best_index: int | None = None
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
    if chroma >= 0.070:
        penalty = 0.0
    elif chroma <= 0.030:
        penalty = 22.0
    else:
        penalty = 22.0 * (0.070 - chroma) / 0.040
    if chroma < 0.055 and (lightness > 0.90 or lightness < 0.16):
        penalty += 7.0
    return min(penalty, 29.0)


def _candidate_baseline(
    evidence_source_ids: list[str],
    history_index: dict[str, list[SourceObservation]],
    lab: tuple[float, float, float],
    settings: Settings,
) -> float:
    values: list[float] = []
    for source_id in evidence_source_ids:
        baseline, _ = _source_baseline(
            history_index.get(source_id, []),
            lab,
            settings.source_cluster_distance,
        )
        values.append(baseline)
    return float(np.mean(values)) if values else 0.0


def score_candidates(
    observations: list[SourceObservation],
    sources: list[Source],
    history: list[HistoryDay],
    settings: Settings,
) -> list[Candidate]:
    if not observations:
        return []

    apply_source_baselines(observations, history, settings, sources)
    clusters = _build_cluster_members(observations, settings.cluster_distance)
    history_index = _history_by_source(history)
    source_config = {source.id: source for source in sources}
    usable_sources = len(observations)
    usable_sectors = len({observation.sector for observation in observations})
    candidates: list[Candidate] = []

    for cluster in clusters:
        raw_members: dict[str, tuple[SourceObservation, Swatch]] = cluster["members"]
        if len(raw_members) < 2:
            continue
        lab = tuple(float(value) for value in cluster["lab"])

        evidence_rows = []
        for observation, aggregate_swatch in raw_members.values():
            raw_weight = max(aggregate_swatch.adjusted_share, 0.0) * source_config.get(
                observation.source_id,
                Source(
                    id=observation.source_id,
                    name=observation.source_name,
                    sector=observation.sector,
                    url=observation.url,
                ),
            ).weight
            evidence = best_local_evidence(
                observation,
                lab,
                settings.max_evidence_distance,
                source_weight=raw_weight,
            )
            if evidence is None:
                continue
            evidence_rows.append((observation, aggregate_swatch, evidence, raw_weight))

        if len(evidence_rows) < 2:
            continue

        total_weight = sum(max(item[3], 1e-9) for item in evidence_rows)
        for _, _, evidence, raw_weight in evidence_rows:
            evidence.source_weight = round(max(raw_weight, 0.0) / total_weight, 6)

        source_count = len(evidence_rows)
        sector_weights: Counter[str] = Counter()
        for observation, _, evidence, _ in evidence_rows:
            sector_weights[observation.sector] += evidence.source_weight
        sectors = sorted(sector_weights)
        sector_count = len(sectors)

        weights = np.asarray([row[2].source_weight for row in evidence_rows], dtype=float)
        adjusted_shares = np.asarray(
            [max(row[1].adjusted_share, 0.0) for row in evidence_rows], dtype=float
        )
        confidences = np.asarray([row[2].region_confidence for row in evidence_rows], dtype=float)
        distances = np.asarray([row[2].distance_to_candidate for row in evidence_rows], dtype=float)

        prevalence = float(adjusted_shares.sum() / max(usable_sources, 1))
        mean_salience = float(np.average(adjusted_shares, weights=np.maximum(weights, 1e-9)))
        baseline_prevalence = _candidate_baseline(
            [row[0].source_id for row in evidence_rows],
            history_index,
            lab,
            settings,
        )
        momentum_ratio = (prevalence + 0.02) / (baseline_prevalence + 0.02)
        momentum = min(max(math.log2(momentum_ratio + 1.0) / 2.0, 0.0), 1.0)

        source_breadth = source_count / max(usable_sources, 1)
        sector_breadth = sector_count / max(usable_sectors, 1)
        evidence_confidence = float(np.mean(confidences))
        evidence_proximity = float(
            np.mean(1.0 - np.minimum(distances / max(settings.max_evidence_distance, 1e-9), 1.0))
        )
        top_source_weight = float(max(weights))
        top_sector_weight = float(max(sector_weights.values()))

        independence_component = min(source_count / max(settings.min_winner_sources * 2, 1), 1.0)
        sector_component = min(sector_count / max(settings.min_winner_sectors * 2, 1), 1.0)
        salience_component = min(mean_salience / 0.30, 1.0)
        prevalence_component = min(prevalence / 0.20, 1.0)
        evidence_component = min((evidence_confidence * 0.65 + evidence_proximity * 0.35), 1.0)

        oklch = oklab_to_oklch(lab)
        neutral_penalty = _neutral_penalty(oklch)
        concentration_penalty = 0.0
        if top_sector_weight > settings.max_sector_weight:
            concentration_penalty += min(
                14.0,
                35.0 * (top_sector_weight - settings.max_sector_weight),
            )
        if top_source_weight > settings.max_source_weight:
            concentration_penalty += min(
                10.0,
                40.0 * (top_source_weight - settings.max_source_weight),
            )

        components = {
            "source_breadth": round(independence_component * 27.0, 3),
            "sector_breadth": round(sector_component * 20.0, 3),
            "momentum": round(momentum * 16.0, 3),
            "visual_salience": round(salience_component * 13.0, 3),
            "prevalence": round(prevalence_component * 8.0, 3),
            "evidence_integrity": round(evidence_component * 16.0, 3),
        }
        score = sum(components.values()) - neutral_penalty - concentration_penalty

        ordered = sorted(
            evidence_rows,
            key=lambda row: (
                row[2].source_weight
                * row[2].region_confidence
                * max(0.05, 1.0 - row[2].distance_to_candidate / settings.max_evidence_distance)
            ),
            reverse=True,
        )
        ordered_evidence = [row[2] for row in ordered]
        candidate = Candidate(
            hex=hex_from_oklab(lab),
            oklab=lab,
            oklch=oklch,
            score=round(max(score, 0.0), 3),
            source_count=source_count,
            sector_count=sector_count,
            source_ids=[item.source_id for item in ordered_evidence],
            source_names=[item.source_name for item in ordered_evidence],
            sectors=sectors,
            prevalence=round(prevalence, 6),
            sector_breadth=round(sector_breadth, 6),
            mean_salience=round(mean_salience, 6),
            momentum=round(momentum, 6),
            baseline_prevalence=round(baseline_prevalence, 6),
            neutral_penalty=round(neutral_penalty, 3),
            concentration_penalty=round(concentration_penalty, 3),
            components=components,
            source_sectors=[item.sector for item in ordered_evidence],
            source_salience=[round(item.local_share, 6) for item in ordered_evidence],
            evidence=ordered_evidence,
            top_source_weight=round(top_source_weight, 6),
            top_sector_weight=round(top_sector_weight, 6),
            evidence_region_count=len({(item.source_id, item.region_id) for item in ordered_evidence}),
            mean_evidence_confidence=round(evidence_confidence, 6),
            mean_evidence_distance=round(float(np.mean(distances)), 6),
            max_evidence_distance=round(float(np.max(distances)), 6),
        )
        candidate.family_label = family_label_for_candidate(candidate)
        candidates.append(candidate)

    candidates.sort(
        key=lambda candidate: (
            candidate.score,
            candidate.source_count,
            candidate.sector_count,
            candidate.oklch[1],
        ),
        reverse=True,
    )
    for index, candidate in enumerate(candidates):
        next_score = candidates[index + 1].score if index + 1 < len(candidates) else 0.0
        candidate.score_margin_to_next = round(candidate.score - next_score, 3)
    return candidates


def candidate_is_display_eligible(
    candidate: Candidate,
    history_days: int,
    settings: Settings,
) -> bool:
    """Keep generic neutrals out unless a mature baseline shows a real surge."""
    _, chroma, _ = candidate.oklch
    if chroma >= settings.display_min_chroma:
        return True
    if history_days < settings.neutral_warmup_days:
        return False
    momentum_ratio = (candidate.prevalence + 0.02) / (
        candidate.baseline_prevalence + 0.02
    )
    return (
        momentum_ratio >= settings.neutral_min_momentum_ratio
        and candidate.source_count >= settings.neutral_min_sources
        and candidate.sector_count >= settings.neutral_min_sectors
        and candidate.mean_evidence_confidence >= settings.min_mean_evidence_confidence
        and candidate.top_source_weight <= settings.max_source_weight
        and candidate.top_sector_weight <= settings.max_sector_weight
    )


def select_daily_candidates(
    candidates: list[Candidate],
    history_days: int,
    settings: Settings,
) -> list[Candidate]:
    return [
        candidate
        for candidate in candidates
        if candidate_is_display_eligible(candidate, history_days, settings)
    ]


def select_distinct_runners(
    winner: Candidate,
    candidates: list[Candidate],
    settings: Settings,
    limit: int = 3,
) -> list[Candidate]:
    selected: list[Candidate] = []
    for candidate in candidates:
        if candidate.source_count < settings.min_runner_sources:
            continue
        if candidate.sector_count < settings.min_runner_sectors:
            continue
        if len(candidate.evidence) < settings.min_runner_sources:
            continue
        if delta(candidate.oklab, winner.oklab) < settings.runner_distinct_distance:
            continue
        if any(
            delta(candidate.oklab, existing.oklab) < settings.runner_distinct_distance
            for existing in selected
        ):
            continue
        selected.append(candidate)
        if len(selected) >= limit:
            break
    return selected


def evaluate_quality(
    candidates: list[Candidate],
    observations: list[SourceObservation],
    sources: list[Source],
    settings: Settings,
) -> QualityGate:
    """Decide whether a run has enough integrity to be reviewed at all."""
    reasons: list[str] = []
    warnings: list[str] = []
    usable_sources = len(observations)
    configured_sources = len(sources)
    usable_sectors = len({item.sector for item in observations})
    configured_sectors = len({item.sector for item in sources})
    region_coverage = usable_sources / max(configured_sources, 1)
    review_coverage_floor = settings.min_review_region_coverage_ratio

    if usable_sources < settings.min_review_sources:
        reasons.append(
            f"Only {usable_sources} company pages produced eligible creative evidence; "
            f"at least {settings.min_review_sources} are required for internal review."
        )
    if usable_sectors < settings.min_review_sectors:
        reasons.append(
            f"Only {usable_sectors} sectors produced eligible creative evidence; "
            f"at least {settings.min_review_sectors} are required for internal review."
        )
    if region_coverage < review_coverage_floor:
        reasons.append(
            f"Only {region_coverage:.1%} of the panel produced eligible creative evidence; "
            f"at least {review_coverage_floor:.1%} is required for internal review."
        )
    if len(candidates) < settings.min_candidates:
        reasons.append("No traceable, display-eligible color candidate was found.")

    if candidates:
        winner = candidates[0]
        if winner.source_count < settings.min_winner_sources:
            reasons.append(
                f"The leading color appeared in only {winner.source_count} independent companies; "
                f"at least {settings.min_winner_sources} are required."
            )
        if winner.sector_count < settings.min_winner_sectors:
            reasons.append(
                f"The leading color crossed only {winner.sector_count} sectors; "
                f"at least {settings.min_winner_sectors} are required."
            )
        if winner.evidence_region_count < settings.min_winner_evidence_regions:
            reasons.append(
                "The leading color does not have enough distinct traceable creative regions."
            )
        if winner.source_count != len(winner.evidence):
            reasons.append("The leading color source count does not match its evidence records.")
        if winner.mean_evidence_confidence < settings.min_mean_evidence_confidence:
            reasons.append(
                f"Mean creative-region confidence was {winner.mean_evidence_confidence:.2f}; "
                f"at least {settings.min_mean_evidence_confidence:.2f} is required."
            )
        if winner.mean_evidence_distance > settings.max_mean_evidence_distance:
            reasons.append(
                f"Mean source-to-winner color distance was {winner.mean_evidence_distance:.3f}; "
                f"it must be no more than {settings.max_mean_evidence_distance:.3f}."
            )
        max_distance = max(
            (item.distance_to_candidate for item in winner.evidence),
            default=0.0,
        )
        if max_distance > settings.max_evidence_distance:
            reasons.append(
                f"At least one source match was too far from the candidate ({max_distance:.3f})."
            )
        if winner.top_source_weight > settings.max_source_weight:
            reasons.append(
                f"One company supplied {winner.top_source_weight:.0%} of weighted support; "
                f"the limit is {settings.max_source_weight:.0%}."
            )
        if winner.top_sector_weight > settings.max_sector_weight:
            reasons.append(
                f"One sector supplied {winner.top_sector_weight:.0%} of weighted support; "
                f"the limit is {settings.max_sector_weight:.0%}."
            )
        if winner.score_margin_to_next < settings.min_score_margin:
            warnings.append(
                f"The leading color is only {winner.score_margin_to_next:.1f} points ahead of "
                "the next qualified candidate."
            )

    return QualityGate(
        passed=not reasons,
        reasons=reasons,
        usable_sources=usable_sources,
        configured_sources=configured_sources,
        usable_sectors=usable_sectors,
        configured_sectors=configured_sectors,
        state="blocked" if reasons else "pending",
        warnings=warnings,
        region_coverage_ratio=round(region_coverage, 6),
    )


def publication_state(
    gate: QualityGate,
    history_days: int,
    settings: Settings,
) -> str:
    if not gate.passed:
        gate.state = "blocked"
        return "blocked"

    ready_coverage = gate.usable_sources / max(gate.configured_sources, 1)
    ready_reasons: list[str] = []
    if history_days < settings.calibration_days:
        ready_reasons.append(
            f"Baseline calibration is incomplete ({history_days}/{settings.calibration_days} approved days)."
        )
    if gate.usable_sources < settings.min_ready_sources:
        ready_reasons.append(
            f"Public readiness requires {settings.min_ready_sources} evidence-bearing company pages."
        )
    if gate.usable_sectors < settings.min_ready_sectors:
        ready_reasons.append(
            f"Public readiness requires {settings.min_ready_sectors} sectors."
        )
    if ready_coverage < settings.min_ready_region_coverage_ratio:
        ready_reasons.append(
            f"Public readiness requires {settings.min_ready_region_coverage_ratio:.0%} panel coverage."
        )
    if gate.warnings:
        ready_reasons.append("A close-call warning requires calibration review.")

    if ready_reasons:
        gate.warnings.extend(reason for reason in ready_reasons if reason not in gate.warnings)
        gate.state = "review_only"
        return "review_only"

    gate.state = "ready"
    return "ready"


def confidence_label(candidate: Candidate | None, state: str) -> str:
    if state == "blocked" or candidate is None:
        return "Blocked"
    if state == "review_only":
        return "Calibration"
    if (
        candidate.source_count >= 10
        and candidate.sector_count >= 6
        and candidate.mean_evidence_confidence >= 0.80
        and candidate.mean_evidence_distance <= 0.030
        and candidate.score_margin_to_next >= 8.0
    ):
        return "High"
    return "Moderate"
