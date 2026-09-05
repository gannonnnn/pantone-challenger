import pytest

from challenger.colors import oklab_from_hex, oklab_to_oklch
from challenger.config import Settings
from challenger.integrity import IntegrityError, validate_result_integrity
from challenger.models import Candidate, CandidateEvidence, DailyResult, QualityGate, Source


def make_result(*, evidence_sector: str = "technology") -> tuple[DailyResult, list[Source]]:
    lab = oklab_from_hex("#4799A2")
    evidence = CandidateEvidence(
        source_id="apple",
        source_name="Apple",
        sector=evidence_sector,
        region_id="apple-r01",
        region_path="/tmp/apple-r01.png",
        local_hex="#4799A2",
        local_oklab=lab,
        distance_to_candidate=0.0,
        local_share=0.4,
        source_weight=1.0,
        region_confidence=0.9,
        page_title="Apple",
        source_url="https://www.apple.com/",
    )
    candidate = Candidate(
        hex="#4799A2",
        oklab=lab,
        oklch=oklab_to_oklch(lab),
        score=80,
        source_count=1,
        sector_count=1,
        source_ids=["apple"],
        source_names=["Apple"],
        sectors=[evidence_sector],
        prevalence=0.2,
        sector_breadth=0.5,
        mean_salience=0.4,
        momentum=0.5,
        baseline_prevalence=0.1,
        neutral_penalty=0,
        concentration_penalty=0,
        components={},
        source_sectors=[evidence_sector],
        source_salience=[0.4],
        evidence=[evidence],
        family_label="Slate Teal",
        creative_name="Pool Tile",
        evidence_region_count=1,
        mean_evidence_confidence=0.9,
        mean_evidence_distance=0.0,
    )
    result = DailyResult(
        date="2026-08-30",
        generated_at="now",
        project="Pantone Challenger",
        methodology_version="1.3.0",
        registry_version="1.3",
        panel_size=1,
        captured_sources=1,
        captured_sectors=1,
        baseline_days=7,
        calibration_day=0,
        status="ready",
        confidence_label="Moderate",
        quality_gate=QualityGate(True, [], 1, 1, 1, 1, state="ready"),
        winner=candidate,
        winner_name="Pool Tile Slate Teal",
        runners_up=[],
        source_failures=[],
        disclaimer="Independent",
    )
    sources = [
        Source(
            id="apple",
            name="Apple",
            sector="technology",
            url="https://www.apple.com/",
        )
    ]
    return result, sources


def test_registry_sector_mismatch_is_a_hard_failure():
    result, sources = make_result(evidence_sector="beauty")
    with pytest.raises(IntegrityError, match="Sector mismatch"):
        validate_result_integrity(result, sources, Settings())


def test_unapproved_logo_can_never_enter_public_output():
    result, sources = make_result()
    result.source_logos = {"apple": "brand-marks/apple.png"}
    with pytest.raises(IntegrityError, match="Unapproved brand mark"):
        validate_result_integrity(result, sources, Settings())


def test_traceable_result_passes_integrity_validation():
    result, sources = make_result()
    validate_result_integrity(result, sources, Settings())
