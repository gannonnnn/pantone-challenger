from pathlib import Path

from PIL import Image

from challenger.colors import oklab_from_hex, oklab_to_oklch
from challenger.models import (
    Candidate,
    CandidateEvidence,
    DailyResult,
    QualityGate,
    RecurrenceSummary,
)
from challenger.render import FEED_SIZE, STORY_SIZE, render_daily


def candidate(value: str, score: float, count: int = 9) -> Candidate:
    lab = oklab_from_hex(value)
    sectors = ["beauty", "finance", "retail", "technology", "travel"]
    evidence: list[CandidateEvidence] = []
    for index in range(count):
        local = value
        evidence.append(
            CandidateEvidence(
                source_id=f"s{index}",
                source_name=f"Source {index}",
                sector=sectors[index % len(sectors)],
                region_id=f"s{index}-r01",
                region_path=f"/tmp/s{index}-region.png",
                local_hex=local,
                local_oklab=lab,
                distance_to_candidate=0.0,
                local_share=max(0.08, 0.24 - index * 0.01),
                source_weight=1 / count,
                region_confidence=0.85,
                page_title="Campaign",
                source_url=f"https://example.com/{index}",
            )
        )
    return Candidate(
        hex=value,
        oklab=lab,
        oklch=oklab_to_oklch(lab),
        score=score,
        source_count=count,
        sector_count=5,
        source_ids=[item.source_id for item in evidence],
        source_names=[item.source_name for item in evidence],
        sectors=sectors,
        prevalence=0.30,
        sector_breadth=0.50,
        mean_salience=0.24,
        momentum=0.80,
        baseline_prevalence=0.12,
        neutral_penalty=0,
        concentration_penalty=0,
        components={"source_breadth": 20},
        source_sectors=[item.sector for item in evidence],
        source_salience=[item.local_share for item in evidence],
        evidence=evidence,
        family_label="Olive Green",
        creative_name="Expensive Olive Oil",
        confidence="High",
        top_source_weight=1 / count,
        top_sector_weight=0.25,
        score_margin_to_next=7.2,
        evidence_region_count=count,
        mean_evidence_confidence=0.85,
        mean_evidence_distance=0.0,
    )


def test_daily_social_package_has_exact_swatches_text_attribution_and_counts(tmp_path):
    winner = candidate("#6F8557", 81.2)
    runners = [
        candidate("#A34D43", 74.0, 7),
        candidate("#4799A2", 71.0, 6),
        candidate("#C5A14A", 68.0, 6),
    ]
    for item, family, creative in zip(
        runners,
        ["Clay Red", "Slate Teal", "Ochre"],
        ["Hotel Lobby", "Pool Tile", "Loyalty Tier"],
    ):
        item.family_label = family
        item.creative_name = creative
        item.confidence = "Moderate"

    result = DailyResult(
        date="2026-08-25",
        generated_at="2026-08-25T23:00:00-04:00",
        project="Pantone Challenger",
        methodology_version="1.3.0",
        registry_version="1.3",
        panel_size=48,
        captured_sources=39,
        captured_sectors=11,
        baseline_days=12,
        calibration_day=0,
        status="ready",
        confidence_label="High",
        quality_gate=QualityGate(
            True,
            [],
            39,
            48,
            11,
            12,
            state="ready",
            region_coverage_ratio=39 / 48,
        ),
        winner=winner,
        winner_name="Expensive Olive Oil Olive Green",
        runners_up=runners,
        source_failures=[],
        disclaimer="Independent project.",
        runner_up_names=[
            "Hotel Lobby Clay Red",
            "Pool Tile Slate Teal",
            "Loyalty Tier Ochre",
        ],
        source_logos={},
        recurrence=RecurrenceSummary(
            year=2026,
            family_name="Olive Green",
            representative_hex="#748553",
            distance_threshold=0.055,
            winning_days=3,
            previous_winning_days=2,
            current_streak=2,
            longest_streak=2,
            first_win_date="2026-08-20",
            latest_win_date="2026-08-25",
            matching_dates=["2026-08-20", "2026-08-24", "2026-08-25"],
            unique_company_count=17,
            unique_company_ids=[f"s{i}" for i in range(17)],
            unique_company_names=[f"Source {i}" for i in range(17)],
            panel_company_count=48,
            supporting_company_days=26,
            average_analyzed_company_pages=39.3,
            sectors=["fashion", "technology", "home", "retail"],
            sector_count=4,
            sector_day_counts={"fashion": 3, "technology": 2, "home": 1, "retail": 1},
            ready_days_in_year=20,
        ),
    )
    outputs = render_daily(result, tmp_path)
    assert len(outputs) == 10

    feed = Image.open(tmp_path / "feed-post.png").convert("RGB")
    assert feed.size == FEED_SIZE
    assert feed.getpixel((900, 500)) == (111, 133, 87)

    evidence = Image.open(tmp_path / "story-02-evidence.png").convert("RGB")
    assert evidence.size == STORY_SIZE
    # First evidence card's local swatch is the evidence, not a logo or favicon.
    assert evidence.getpixel((147, 572)) == (111, 133, 87)

    runners_image = Image.open(tmp_path / "story-04-runners-up.png").convert("RGB")
    assert runners_image.size == STORY_SIZE
    assert runners_image.getpixel((180, 550)) == (163, 77, 67)
    assert runners_image.getpixel((180, 985)) == (71, 153, 162)
    assert runners_image.getpixel((180, 1420)) == (197, 161, 74)

    caption = (tmp_path / "caption.txt").read_text()
    assert "48 company pages monitored" in caption
    assert "39 produced eligible creative evidence" in caption
    assert "3rd day in 2026" in caption
    assert "17 unique companies" in caption

    review = (tmp_path / "review-summary.md").read_text()
    assert "Traceable source evidence" in review
    assert "Local swatch" in review
    assert "Methodology / registry" in review


def test_calibration_assets_are_labeled_not_for_posting(tmp_path):
    winner = candidate("#4799A2", 70.0, 8)
    winner.family_label = "Slate Teal"
    winner.creative_name = "Pool Tile"
    winner.confidence = "Calibration"
    result = DailyResult(
        date="2026-08-30",
        generated_at="2026-08-30T23:00:00-04:00",
        project="Pantone Challenger",
        methodology_version="1.3.0",
        registry_version="1.3",
        panel_size=48,
        captured_sources=32,
        captured_sectors=10,
        baseline_days=0,
        calibration_day=1,
        status="review_only",
        confidence_label="Calibration",
        quality_gate=QualityGate(
            True,
            [],
            32,
            48,
            10,
            12,
            state="review_only",
            region_coverage_ratio=32 / 48,
        ),
        winner=winner,
        winner_name="Pool Tile Slate Teal",
        runners_up=[],
        source_failures=[],
        disclaimer="Independent project.",
    )
    render_daily(result, tmp_path)
    caption = (tmp_path / "caption.txt").read_text()
    assert caption.startswith("INTERNAL CALIBRATION — DO NOT POST")
    assert not result.source_logos
