from __future__ import annotations

from collections import Counter

import numpy as np

from challenger.color import distance, family_label, oklab_to_oklch
from challenger.models import Candidate, CandidateEvidence, Observation, TrendState
from challenger.naming import creative_name
from challenger.palette import swatch_is_candidate_eligible


def build_candidates(
    observations: list[Observation],
    run_date: str,
    settings: dict,
) -> list[Candidate]:
    """Build compact, source-balanced color candidates.

    Cross-source clusters use complete-linkage membership. A new swatch may join
    a cluster only when it is close to *every* existing member, preventing a
    sequence of neighboring shades from drifting into one misleading color.
    The public HEX is a weighted medoid observed in real source pixels, not an
    averaged synthetic color.
    """

    threshold = float(settings.get("clustering", {}).get("oklab_distance", 0.050))
    points: list[tuple[Observation, object, float]] = []
    for obs in observations:
        for swatch in obs.swatches:
            if not swatch_is_candidate_eligible(swatch, settings):
                continue
            adjusted = swatch.adjusted_share if swatch.adjusted_share is not None else swatch.share
            strength = (
                0.45 * adjusted
                + 0.25 * swatch.salience
                + 0.20 * swatch.largest_component_share
                + 0.10 * swatch.spatial_coverage
            ) * obs.region.confidence
            points.append((obs, swatch, max(0.001, strength)))
    points.sort(key=lambda item: item[2], reverse=True)

    clusters: list[list[tuple[Observation, object, float]]] = []
    for point in points:
        _, swatch, _ = point
        possible: list[tuple[float, list[tuple[Observation, object, float]]]] = []
        for cluster in clusters:
            distances = [distance(member[1].oklab, swatch.oklab) for member in cluster]
            if distances and max(distances) <= threshold:
                possible.append((sum(distances) / len(distances), cluster))
        if possible:
            min(possible, key=lambda item: item[0])[1].append(point)
        else:
            clusters.append([point])

    source_platform = {}
    for obs in observations:
        source_platform.setdefault(obs.source_id, obs.platform or obs.source_id)

    candidates: list[Candidate] = []
    for cluster in clusters:
        # One strongest color observation per independent source.
        best_by_source: dict[str, tuple[float, Observation, object]] = {}
        for obs, swatch, strength in cluster:
            prior = best_by_source.get(obs.source_id)
            if prior is None or strength > prior[0]:
                best_by_source[obs.source_id] = (strength, obs, swatch)
        selected = list(best_by_source.values())
        if not selected:
            continue

        # Equal-source weighted medoid. Its HEX and OKLab coordinates came from
        # an actual sampled pixel in one evidence source.
        medoid_index = _medoid_index([entry[2].oklab for entry in selected])
        representative_obs = selected[medoid_index][1]
        representative_swatch = selected[medoid_index][2]
        canonical_lab = representative_swatch.oklab
        hex_value = representative_swatch.hex
        lch = oklab_to_oklch(canonical_lab)

        evidence: list[CandidateEvidence] = []
        for _, obs, swatch in selected:
            evidence.append(
                CandidateEvidence(
                    source_id=obs.source_id,
                    source_name=obs.source_name,
                    domain=obs.domain.value,
                    sector=obs.sector,
                    signal_stage=obs.signal_stage.value,
                    scale_class=obs.scale_class.value,
                    panel_type=obs.panel_type.value,
                    region_id=obs.region.region_id,
                    region_path=obs.region.screenshot_path,
                    local_hex=swatch.hex,
                    local_oklab=swatch.oklab,
                    distance_to_candidate=distance(canonical_lab, swatch.oklab),
                    local_share=swatch.share,
                    source_vote=1.0,
                    evidence_confidence=obs.region.confidence,
                    page_title=obs.region.page_title,
                    source_url=obs.region.page_url,
                    rights_mode=obs.rights_mode.value,
                    largest_component_share=swatch.largest_component_share,
                    spatial_coverage=swatch.spatial_coverage,
                    observed_pixel=swatch.observed_pixel,
                )
            )
        evidence.sort(
            key=lambda item: (
                item.evidence_confidence,
                item.largest_component_share,
                item.local_share,
            ),
            reverse=True,
        )
        family = family_label(lch)
        domain_counts = Counter(e.domain for e in evidence)
        dominant_domain = domain_counts.most_common(1)[0][0]
        source_count = len(evidence)
        domains = {e.domain for e in evidence}
        sectors = {e.sector for e in evidence}
        stages = {e.signal_stage for e in evidence}
        scales = {e.scale_class for e in evidence}
        benchmarks = sum(e.panel_type == "benchmark" for e in evidence)
        discoveries = sum(e.panel_type == "discovery" for e in evidence)
        platforms = Counter(source_platform.get(e.source_id, e.source_id) for e in evidence)
        top_platform = max(platforms.values(), default=0) / source_count
        quality = sum(e.evidence_confidence for e in evidence) / source_count
        candidate = Candidate(
            hex=hex_value,
            oklab=canonical_lab,
            oklch=lch,
            family_label=family,
            creative_name=creative_name(family, hex_value, run_date, dominant_domain),
            evidence=evidence,
            source_count=source_count,
            domain_count=len(domains),
            sector_count=len(sectors),
            stage_count=len(stages),
            scale_count=len(scales),
            benchmark_count=benchmarks,
            discovery_count=discoveries,
            current_usage_score=100.0 * _balanced_usage(evidence, settings),
            emergence_score=0.0,
            undercurrent_score=_undercurrent_score(evidence),
            mainstream_score=_mainstream_score(evidence),
            novelty=0.0,
            adoption_velocity=0.0,
            cross_domain_spread=min(
                1.0,
                len(domains) / max(1, int(settings.get("scoring", {}).get("target_domains", 6))),
            ),
            cross_stage_convergence=min(1.0, len(stages) / 3.0),
            small_large_diversity=_small_large_diversity(evidence),
            evidence_quality=quality,
            top_source_weight=1.0 / source_count,
            top_domain_weight=max(domain_counts.values()) / source_count,
            top_platform_weight=top_platform,
            trend_state=TrendState.CALIBRATION,
            uncertainty=1.0 / (source_count**0.5),
            display_hex_source_id=representative_obs.source_id,
            color_integrity={
                "display_hex_is_observed": hex_value in {e.local_hex for e in evidence},
                "all_local_hex_observed": all(e.observed_pixel for e in evidence),
                "cluster_diameter": round(_cluster_diameter(evidence), 6),
                "mean_component_share": round(
                    sum(e.largest_component_share for e in evidence) / source_count,
                    6,
                ),
                "minimum_component_share": round(
                    min(e.largest_component_share for e in evidence),
                    6,
                ),
                "mean_spatial_coverage": round(
                    sum(e.spatial_coverage for e in evidence) / source_count,
                    6,
                ),
                "representative_source_id": representative_obs.source_id,
            },
        )
        candidates.append(candidate)
    return _remove_near_duplicate_candidates(candidates, settings)


def _medoid_index(labs: list[tuple[float, float, float]]) -> int:
    if len(labs) <= 1:
        return 0
    arr = np.asarray(labs, dtype=float)
    distances = np.linalg.norm(arr[:, None, :] - arr[None, :, :], axis=2)
    return int(np.argmin(distances.sum(axis=1)))


def _cluster_diameter(evidence: list[CandidateEvidence]) -> float:
    if len(evidence) <= 1:
        return 0.0
    return max(
        distance(a.local_oklab, b.local_oklab)
        for i, a in enumerate(evidence)
        for b in evidence[i + 1 :]
    )


def _balanced_usage(evidence: list[CandidateEvidence], settings: dict) -> float:
    if not evidence:
        return 0.0
    domain = Counter(e.domain for e in evidence)
    stage = Counter(e.signal_stage for e in evidence)
    panel = Counter(e.panel_type for e in evidence)
    total = len(evidence)
    breadth = min(
        1.0,
        len(domain) / max(1, int(settings.get("scoring", {}).get("target_domains", 6))),
    )
    stage_breadth = min(1.0, len(stage) / 3.0)
    panel_balance = 1.0 if len(panel) >= 2 else 0.65
    local = sum(min(e.local_share, 0.35) / 0.35 for e in evidence) / total
    component = sum(min(e.largest_component_share, 0.20) / 0.20 for e in evidence) / total
    return (
        0.35 * min(1.0, total / 10.0)
        + 0.25 * breadth
        + 0.15 * stage_breadth
        + 0.10 * panel_balance
        + 0.08 * local
        + 0.07 * component
    )


def _undercurrent_score(evidence: list[CandidateEvidence]) -> float:
    if not evidence:
        return 0.0
    early = sum(
        e.panel_type == "discovery" or e.scale_class in {"independent", "grassroots"}
        for e in evidence
    ) / len(evidence)
    domains = len({e.domain for e in evidence})
    return 100 * (0.70 * early + 0.30 * min(1.0, domains / 4.0))


def _mainstream_score(evidence: list[CandidateEvidence]) -> float:
    if not evidence:
        return 0.0
    mainstream = sum(
        e.panel_type == "benchmark" or e.scale_class in {"institutional", "large_commercial"}
        for e in evidence
    ) / len(evidence)
    return 100 * (0.75 * mainstream + 0.25 * min(1.0, len(evidence) / 12.0))


def _small_large_diversity(evidence: list[CandidateEvidence]) -> float:
    small = any(e.scale_class in {"independent", "grassroots"} for e in evidence)
    large = any(e.scale_class in {"institutional", "large_commercial"} for e in evidence)
    middle = any(e.scale_class == "mid_size" for e in evidence)
    return min(1.0, (int(small) + int(large) + 0.5 * int(middle)) / 2.0)


def _remove_near_duplicate_candidates(candidates: list[Candidate], settings: dict) -> list[Candidate]:
    threshold = float(settings.get("clustering", {}).get("candidate_distinctness", 0.040))
    candidates = sorted(
        candidates,
        key=lambda c: (c.source_count, c.current_usage_score, c.evidence_quality),
        reverse=True,
    )
    accepted: list[Candidate] = []
    for candidate in candidates:
        if any(distance(candidate.oklab, existing.oklab) < threshold for existing in accepted):
            continue
        accepted.append(candidate)
    return accepted
