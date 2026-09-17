from __future__ import annotations

from dataclasses import replace

from challenger.baseline import panel_candidate_history, source_color_history
from challenger.models import Candidate, TrendState


EMERGING_STATES = {TrendState.NEW, TrendState.RISING, TrendState.SPREADING, TrendState.SURGING}


def score_emergence(candidates: list[Candidate], history: list[dict], settings: dict,
                    current_observations: list[dict] | None = None) -> list[Candidate]:
    weights = settings.get("scoring", {}).get("emergence_weights", {})
    baseline_cfg = settings.get("baseline", {})
    min_history = int(baseline_cfg.get("min_days_for_trend", 7))
    min_source_days = int(baseline_cfg.get("min_source_days", 5))
    identity_frequency = float(baseline_cfg.get("identity_frequency", 0.70))
    min_change = float(baseline_cfg.get("min_change_percentage_points", 5.0))
    scored = []
    for c in candidates:
        previous = source_color_history(history, c.oklab)
        comparison = panel_candidate_history(
            history, c.oklab, current_observations=current_observations,
            min_source_days=min_source_days,
            min_cohort_sources=int(baseline_cfg.get("min_cohort_sources", 6)),
            min_comparable_days=int(baseline_cfg.get("min_comparable_days", 5)),
            min_cohort_coverage=float(baseline_cfg.get("min_cohort_coverage", .5)),
        )
        known = [e for e in c.evidence if previous.get(e.source_id, {}).get("days", 0) >= min_source_days]
        confirmed_new = sum(previous[e.source_id]["present_days"] == 0 for e in known)
        identity = sum(previous[e.source_id]["frequency"] >= identity_frequency for e in known)
        new_ratio = confirmed_new / len(known) if known else 0.0
        identity_ratio = identity / len(known) if known else 0.0
        delta = (comparison["change_percentage_points"] or 0.0) / 100.0
        novelty = min(1.0, max(0.0, delta) * 2 + 0.5 * new_ratio) if comparison["valid"] else 0.0
        velocity = min(1.0, max(0.0, delta) * 4) if comparison["valid"] else 0.0
        score = 100 * (
            float(weights.get("novelty", .25)) * novelty
            + float(weights.get("velocity", .15)) * velocity
            + float(weights.get("cross_domain", .25)) * c.cross_domain_spread
            + float(weights.get("cross_stage", .20)) * c.cross_stage_convergence
            + float(weights.get("small_large", .10)) * c.small_large_diversity
            + float(weights.get("quality", .05)) * c.evidence_quality
        )
        if len(history) < min_history:
            state = TrendState.CALIBRATION
        elif not comparison["valid"]:
            state = TrendState.OBSERVED
        elif delta * 100 <= -min_change:
            state = TrendState.COOLING
        elif delta * 100 < min_change:
            state = TrendState.IDENTITY if identity_ratio >= .7 else TrendState.STABLE
        elif delta >= .20 and score >= 75:
            state = TrendState.SURGING
        elif c.domain_count >= 4 and c.stage_count >= 2:
            state = TrendState.SPREADING
        else:
            state = TrendState.RISING
        scored.append(replace(c, emergence_score=round(score, 2), novelty=round(novelty, 4),
                              adoption_velocity=round(velocity, 4), trend_state=state,
                              historical_days=len(history), comparison=comparison))
    return sorted(scored, key=lambda c: (c.emergence_score, c.source_count, c.current_usage_score), reverse=True)


def select_leaders(candidates: list[Candidate], settings: dict, baseline_days: int):
    if not candidates:
        return [], None, None, None, []
    usage_leader = max(candidates, key=lambda c: c.current_usage_score)
    undercurrent = max(candidates, key=lambda c: c.undercurrent_score)
    mainstream = max(candidates, key=lambda c: c.mainstream_score)
    min_score = float(settings.get("quality", {}).get("min_emergence_score", 55.0))
    min_sources = int(settings.get("quality", {}).get("min_supporting_sources", 6))
    min_domains = int(settings.get("quality", {}).get("min_supporting_domains", 4))
    emerging = [
        c
        for c in candidates
        if c.emergence_score >= min_score
        and c.source_count >= min_sources
        and c.domain_count >= min_domains
        and (baseline_days < int(settings.get("baseline", {}).get("min_days_for_trend", 7)) or c.trend_state in EMERGING_STATES)
        and _concentration_ok(c, settings)
        and _neutral_ok(c, settings, baseline_days)
        and _color_integrity_ok(c, settings)
    ]
    # Margin must compare eligible candidates, never an excluded neutral or stale item.
    emerging.sort(key=lambda c: c.emergence_score, reverse=True)
    emerging = [replace(c, score_margin=round(c.emergence_score - emerging[i + 1].emergence_score, 2)
                        if i + 1 < len(emerging) else 100.0) for i, c in enumerate(emerging)]
    challenger = _ties(emerging, settings)
    challenger_ids = {c.hex for c in challenger}
    runners = [c for c in candidates if c.hex not in challenger_ids and _runner_ok(c, settings)][:3]
    return challenger, undercurrent, mainstream, usage_leader, runners


def _concentration_ok(candidate: Candidate, settings: dict) -> bool:
    q = settings.get("quality", {})
    return (
        candidate.top_source_weight <= float(q.get("max_top_source_weight", 0.25))
        and candidate.top_domain_weight <= float(q.get("max_top_domain_weight", 0.45))
        and candidate.top_platform_weight <= float(q.get("max_top_platform_weight", 0.40))
    )


def _neutral_ok(candidate: Candidate, settings: dict, baseline_days: int) -> bool:
    if candidate.family_label not in {"Black", "Charcoal", "Gray", "Light Gray", "White"}:
        return True
    gate = settings.get("neutral_gate", {})
    return (
        baseline_days >= int(gate.get("min_baseline_days", 14))
        and candidate.adoption_velocity >= float(gate.get("min_velocity", 0.70))
        and candidate.source_count >= int(gate.get("min_sources", 10))
        and candidate.domain_count >= int(gate.get("min_domains", 6))
        and candidate.top_source_weight <= float(gate.get("max_top_source_weight", 0.20))
    )


def _runner_ok(candidate: Candidate, settings: dict) -> bool:
    q = settings.get("quality", {})
    return (
        candidate.source_count >= int(q.get("min_runner_sources", 4))
        and candidate.domain_count >= int(q.get("min_runner_domains", 3))
        and candidate.family_label not in {"Black", "Charcoal", "Gray", "Light Gray", "White"}
        and _color_integrity_ok(candidate, settings)
    )


def _color_integrity_ok(candidate: Candidate, settings: dict) -> bool:
    q = settings.get("quality", {})
    integrity = candidate.color_integrity or {}
    if bool(q.get("require_observed_display_hex", True)) and not integrity.get(
        "display_hex_is_observed", False
    ):
        return False
    if bool(q.get("require_observed_local_hex", True)) and not integrity.get(
        "all_local_hex_observed", False
    ):
        return False
    if float(integrity.get("cluster_diameter", 1.0)) > float(
        q.get("max_cluster_diameter", 0.050)
    ):
        return False
    if float(integrity.get("mean_component_share", 0.0)) < float(
        q.get("min_mean_component_share", 0.006)
    ):
        return False
    return True


def _ties(candidates: list[Candidate], settings: dict) -> list[Candidate]:
    if not candidates:
        return []
    candidates = sorted(candidates, key=lambda c: c.emergence_score, reverse=True)
    top = candidates[0]
    ties = [top]
    threshold = float(settings.get("ties", {}).get("score_difference", 2.5))
    max_ties = int(settings.get("ties", {}).get("max_co_challengers", 2))
    for candidate in candidates[1:]:
        if len(ties) >= max_ties:
            break
        intervals_overlap = abs(top.emergence_score - candidate.emergence_score) <= (
            top.uncertainty + candidate.uncertainty
        ) * 10
        if top.emergence_score - candidate.emergence_score <= threshold and intervals_overlap:
            ties.append(candidate)
    return ties
