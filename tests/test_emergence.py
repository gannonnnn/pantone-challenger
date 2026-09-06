from dataclasses import replace

from challenger.emergence import score_emergence, select_leaders
from challenger.models import TrendState
from tests.helpers import candidate


SETTINGS = {
    "baseline": {"min_days_for_trend": 7, "identity_frequency": 0.7},
    "scoring": {"emergence_weights": {"novelty": .25, "cross_domain": .25, "cross_stage": .2, "velocity": .15, "small_large": .1, "quality": .05}},
    "quality": {"min_emergence_score": 30, "min_supporting_sources": 6, "min_supporting_domains": 4, "max_top_source_weight": .25, "max_top_domain_weight": .45, "max_top_platform_weight": .40, "min_runner_sources": 4, "min_runner_domains": 3},
    "baseline": {"min_days_for_trend": 7, "identity_frequency": .7},
    "neutral_gate": {"min_baseline_days": 14, "min_velocity": .7, "min_sources": 10, "min_domains": 6, "max_top_source_weight": .2},
    "ties": {"score_difference": 2.5, "max_co_challengers": 2},
}


def test_calibration_state_without_history():
    c = score_emergence([candidate()], [], SETTINGS)[0]
    assert c.trend_state == TrendState.CALIBRATION


def test_ties_are_allowed():
    a = candidate("#A5C84A", score=72.0)
    b = candidate("#4799A2", score=70.4)
    challengers, *_ = select_leaders([a, b], SETTINGS, baseline_days=14)
    assert len(challengers) == 2


def test_stable_identity_can_be_separate_from_usage_leader():
    identity = replace(candidate("#115BB9", score=25), trend_state=TrendState.IDENTITY, current_usage_score=95)
    emerging = replace(candidate("#A5C84A", score=75), trend_state=TrendState.SPREADING, current_usage_score=55)
    challengers, _, mainstream, usage, _ = select_leaders([emerging, identity], SETTINGS, baseline_days=14)
    assert challengers[0].hex == "#A5C84A"
    assert usage.hex == "#115BB9"
