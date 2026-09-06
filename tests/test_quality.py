from challenger.models import PublicationState
from challenger.quality import decide_state
from tests.helpers import candidate


SETTINGS = {"quality": {"min_coverage_block": .3, "min_coverage_ready": .55, "min_evidence_sources_block": 8, "min_evidence_sources_ready": 18, "min_domains_block": 4, "min_domains_ready": 6, "min_stages_block": 2, "min_stages_ready": 3, "min_score_margin": 3}, "baseline": {"calibration_days": 7}}


def decide(**overrides):
    values = dict(active_sources=40, attempted_sources=40, captured_sources=35, evidence_sources=30, domains=8, stages=3, challenger=[candidate()], observations=[], baseline_days=14, settings=SETTINGS)
    values.update(overrides)
    return decide_state(**values)


def test_low_coverage_is_blocked():
    state, reasons, _ = decide(evidence_sources=6)
    assert state == PublicationState.BLOCKED
    assert reasons


def test_calibration_is_review_only():
    state, _, reasons = decide(baseline_days=2)
    assert state == PublicationState.REVIEW_ONLY
    assert any("baseline" in r.lower() for r in reasons)


def test_no_emergence_after_warmup_is_baseline_only():
    state, _, _ = decide(challenger=[], baseline_days=14)
    assert state == PublicationState.BASELINE_ONLY


def test_ready_when_all_gates_pass():
    state, blocked, review = decide()
    assert state == PublicationState.READY
    assert not blocked and not review
