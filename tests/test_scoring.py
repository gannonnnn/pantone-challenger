from dataclasses import replace

import pytest

from challenger.colors import oklab_from_hex, oklab_to_oklch
from challenger.config import Settings
from challenger.models import RegionObservation, Source, SourceObservation, Swatch
from challenger.scoring import (
    apply_source_baselines,
    candidate_is_display_eligible,
    evaluate_quality,
    publication_state,
    score_candidates,
    select_daily_candidates,
)


def swatch(value: str, share: float) -> Swatch:
    lab = oklab_from_hex(value)
    return Swatch(
        hex=value,
        oklab=lab,
        oklch=oklab_to_oklch(lab),
        share=share,
    )


def observation(
    source_id: str,
    sector: str,
    items: list[Swatch],
    *,
    region_items: list[Swatch] | None = None,
) -> SourceObservation:
    region_items = region_items if region_items is not None else items
    return SourceObservation(
        source_id=source_id,
        source_name=source_id.title(),
        sector=sector,
        url=f"https://example.com/{source_id}",
        captured_at="2026-08-25T22:00:00-04:00",
        screenshot_hashes=[source_id],
        swatches=items,
        regions=[
            RegionObservation(
                region_id=f"{source_id}-r01",
                region_type="hero",
                screenshot_path=f"/tmp/{source_id}-region.png",
                sha256=source_id,
                confidence=0.88,
                viewport_area_ratio=0.22,
                image_area_ratio=0.92,
                swatches=region_items,
            )
        ],
    )


def test_persistent_brand_color_is_suppressed():
    settings = Settings(baseline_warmup_days=7, baseline_suppression=0.75)
    current = [
        observation(
            "brand",
            "retail",
            [swatch("#D72B34", 0.60), swatch("#6D8E62", 0.40)],
        )
    ]
    current[0].screenshot_hashes = ["brand-current"]
    history = [
        [
            observation(
                "brand",
                "retail",
                [swatch("#D72B34", 0.60), swatch("#E9E5DD", 0.40)],
            )
        ]
        for _ in range(7)
    ]
    apply_source_baselines(current, history, settings)
    red, green = current[0].swatches
    assert red.adjusted_share < red.share
    assert green.adjusted_share == pytest.approx(green.share)
    assert green.adjusted_share > red.adjusted_share


def test_unchanged_page_factor_applies_to_all_swatches():
    settings = Settings(baseline_warmup_days=1, unchanged_page_factor=0.35)
    current = [observation("brand", "retail", [swatch("#6D8E62", 0.40)])]
    history = [[observation("brand", "retail", [swatch("#D72B34", 0.60)])]]

    apply_source_baselines(current, history, settings)

    assert current[0].swatches[0].adjusted_share == pytest.approx(0.40 * 0.35)


def test_cross_sector_candidate_has_traceable_region_evidence():
    sectors = ["retail", "beauty", "travel", "technology"]
    sources: list[Source] = []
    observations: list[SourceObservation] = []
    for index in range(8):
        sector = sectors[index % len(sectors)]
        source = Source(
            id=f"s{index}",
            name=f"Source {index}",
            sector=sector,
            url=f"https://example.com/{index}",
        )
        sources.append(source)
        observations.append(
            observation(
                source.id,
                sector,
                [
                    swatch("#4E95A2", 0.55),
                    swatch("#D8B787", 0.25),
                    swatch("#333333", 0.20),
                ],
            )
        )

    settings = replace(
        Settings(),
        min_review_sources=6,
        min_review_sectors=3,
        min_ready_sources=6,
        min_ready_sectors=3,
        min_review_region_coverage_ratio=0.50,
        min_ready_region_coverage_ratio=0.50,
        min_winner_sources=5,
        min_winner_sectors=3,
        min_winner_evidence_regions=5,
        min_candidates=1,
    )
    candidates = score_candidates(observations, sources, [], settings)
    selected = select_daily_candidates(candidates, history_days=0, settings=settings)
    gate = evaluate_quality(selected, observations, sources, settings)

    assert selected
    assert selected[0].source_count == 8
    assert selected[0].sector_count == 4
    assert len(selected[0].evidence) == 8
    assert selected[0].source_ids == [item.source_id for item in selected[0].evidence]
    assert all(item.region_id.endswith("-r01") for item in selected[0].evidence)
    assert gate.passed
    assert publication_state(gate, history_days=0, settings=settings) == "review_only"


def test_aggregate_color_without_local_region_match_does_not_count_as_evidence():
    sources = [
        Source(id="a", name="A", sector="retail", url="https://a.example"),
        Source(id="b", name="B", sector="beauty", url="https://b.example"),
    ]
    observations = [
        observation(
            "a",
            "retail",
            [swatch("#4E95A2", 0.8)],
            region_items=[swatch("#D72B34", 1.0)],
        ),
        observation(
            "b",
            "beauty",
            [swatch("#4E95A2", 0.8)],
            region_items=[swatch("#D72B34", 1.0)],
        ),
    ]
    candidates = score_candidates(observations, sources, [], Settings())
    assert not any(candidate.hex.upper() == "#4E95A2" for candidate in candidates)


def _candidate(
    value: str,
    score: float,
    *,
    prevalence: float = 0.30,
    baseline: float = 0.10,
    sources: int = 10,
    sectors: int = 5,
):
    from challenger.models import Candidate

    lab = oklab_from_hex(value)
    return Candidate(
        hex=value,
        oklab=lab,
        oklch=oklab_to_oklch(lab),
        score=score,
        source_count=sources,
        sector_count=sectors,
        source_ids=[f"s{i}" for i in range(sources)],
        source_names=[f"Source {i}" for i in range(sources)],
        sectors=[f"sector-{i}" for i in range(sectors)],
        prevalence=prevalence,
        sector_breadth=0.5,
        mean_salience=0.2,
        momentum=0.5,
        baseline_prevalence=baseline,
        neutral_penalty=0,
        concentration_penalty=0,
        components={},
        mean_evidence_confidence=0.85,
        top_source_weight=0.10,
        top_sector_weight=0.25,
    )


def test_cold_start_daily_selection_excludes_page_infrastructure_neutrals():
    settings = Settings(display_min_chroma=0.035, neutral_warmup_days=14)
    ranked = [
        _candidate("#141416", 90),
        _candidate("#EEEEED", 88),
        _candidate("#7A7670", 84),
        _candidate("#A5C84A", 80),
        _candidate("#4799A2", 75),
    ]
    selected = select_daily_candidates(ranked, history_days=0, settings=settings)

    assert [item.hex for item in selected[:2]] == ["#A5C84A", "#4799A2"]
    assert all(item.oklch[1] >= settings.display_min_chroma for item in selected)


def test_neutral_can_qualify_after_warmup_only_with_exceptional_momentum():
    settings = Settings(
        display_min_chroma=0.035,
        neutral_warmup_days=14,
        neutral_min_momentum_ratio=2.0,
        neutral_min_sources=8,
        neutral_min_sectors=5,
    )
    ordinary_black = _candidate(
        "#141416", 90, prevalence=0.40, baseline=0.38, sources=13, sectors=7
    )
    emerging_black = _candidate(
        "#141416", 90, prevalence=0.40, baseline=0.05, sources=13, sectors=7
    )

    assert not candidate_is_display_eligible(ordinary_black, 30, settings)
    assert candidate_is_display_eligible(emerging_black, 30, settings)
