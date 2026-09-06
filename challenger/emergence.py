from __future__ import annotations

from dataclasses import replace

from challenger.baseline import panel_candidate_history, source_color_history
from challenger.models import Candidate, TrendState


EMERGING_STATES = {TrendState.NEW, TrendState.RISING, TrendState.SPREADING, TrendState.SURGING}


def score_emergence(candidates: list[Candidate], history: list[dict], settings: dict) -> list[Candidate]:
    weights = settings.get("scoring", {}).get("emergence_weights", {})
    w_novelty = float(weights.get("novelty", 0.25))
    w_domains = float(weights.get("cross_domain", 0.25))
    w_stages = float(weights.get("cross_stage", 0.20))
    w_velocity = float(weights.get("velocity", 0.15))
    w_scale = float(weights.get("small_large", 0.10))
    w_quality = float(weights.get("quality", 0.05))
    min_history = int(settings.get("baseline", {}).get("min_days_for_trend", 7))
    identity_frequency = float(settings.get("baseline", {}).get("identity_frequency", 0.70))
    scored = []
    for candidate in candidates:
        source_history = source_color_history(history, candidate.oklab)
        panel_history = panel_candidate_history(history, candidate.oklab)
        new_count = 0
        rising_count = 0
        identity_count = 0
        current_shares = {e.source_id: e.local_share for e in candidate.evidence}
        for source_id, share in current_shares.items():
            baseline = source_history.get(source_id, {"days": 0, "present_days": 0, "frequency": 0, "mean_share": 0})
            if baseline["present_days"] == 0:
                new_count += 1
            elif share >= baseline["mean_share"] * 1.35 and share - baseline["mean_share"] >= 0.04:
                rising_count += 1
            if baseline["days"] >= 5 and baseline["frequency"] >= identity_frequency:
                identity_count += 1
        source_count = max(1, candidate.source_count)
        new_ratio = new_count / source_count
        rising_ratio = rising_count / source_count
        identity_ratio = identity_count / source_count
        mean_prior = panel_history["mean_source_count"]
        lift = candidate.source_count / max(1.0, mean_prior)
        acceleration = (candidate.source_count - panel_history["previous_source_count"]) / max(
            1.0, panel_history["previous_source_count"]
        )
        novelty = min(1.0, 0.50 * new_ratio + 0.30 * max(0.0, lift - 1.0) + 0.20 * (1.0 - identity_ratio))
        velocity = min(1.0, 0.55 * rising_ratio + 0.25 * max(0.0, acceleration) + 0.20 * min(1.0, candidate.source_count / 10))
        score = 100 * (
            w_novelty * novelty
            + w_domains * candidate.cross_domain_spread
            + w_stages * candidate.cross_stage_convergence
            + w_velocity * velocity
            + w_scale * candidate.small_large_diversity
            + w_quality * candidate.evidence_quality
        )
        if len(history) < min_history:
            state = TrendState.CALIBRATION
        elif identity_ratio >= 0.70 and lift < 1.4 and rising_ratio < 0.25:
            state = TrendState.IDENTITY
        elif acceleration < -0.25 and new_ratio < 0.15:
            state = TrendState.COOLING
        elif score >= 78 and candidate.stage_count >= 2 and candidate.domain_count >= 4:
            state = TrendState.SURGING
        elif candidate.domain_count >= 4 and candidate.stage_count >= 2:
            state = TrendState.SPREADING
        elif rising_ratio >= 0.30 or lift >= 1.5:
            state = TrendState.RISING
        elif new_ratio >= 0.50:
            state = TrendState.NEW
        else:
            state = TrendState.STABLE
        scored.append(
            replace(
                candidate,
                emergence_score=round(score, 2),
                novelty=round(novelty, 4),
                adoption_velocity=round(velocity, 4),
                trend_state=state,
                historical_days=len(history),
            )
        )
    scored.sort(key=lambda c: (c.emergence_score, c.source_count, c.current_usage_score), reverse=True)
    for i, candidate in enumerate(scored):
        next_score = scored[i + 1].emergence_score if i + 1 < len(scored) else 0.0
        scored[i] = replace(candidate, score_margin=round(candidate.emergence_score - next_score, 2))
    return scored


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
