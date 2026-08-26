from dataclasses import replace

from challenger.colors import oklab_from_hex, oklab_to_oklch
from challenger.config import Settings
from challenger.models import Source, SourceObservation, Swatch
from challenger.scoring import apply_source_baselines, evaluate_quality, score_candidates


def swatch(value: str, share: float) -> Swatch:
    lab = oklab_from_hex(value)
    return Swatch(
        hex=value,
        oklab=lab,
        oklch=oklab_to_oklch(lab),
        share=share,
    )


def observation(source_id: str, sector: str, items: list[Swatch]) -> SourceObservation:
    return SourceObservation(
        source_id=source_id,
        source_name=source_id.title(),
        sector=sector,
        url=f"https://example.com/{source_id}",
        captured_at="2026-08-25T22:00:00-04:00",
        screenshot_hashes=[source_id],
        swatches=items,
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
    history = [
        [observation("brand", "retail", [swatch("#D72B34", 0.60), swatch("#E9E5DD", 0.40)])]
        for _ in range(7)
    ]
    apply_source_baselines(current, history, settings)
    red, green = current[0].swatches
    assert red.adjusted_share < red.share
    assert green.adjusted_share == green.share
    assert green.adjusted_share > red.adjusted_share


def test_cross_sector_candidate_scores_and_passes_small_test_gate():
    sectors = ["retail", "beauty", "travel", "technology"]
    sources = []
    observations = []
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
        min_usable_sources=6,
        min_usable_sectors=3,
        min_winner_sources=5,
        min_winner_sectors=3,
        min_candidates=2,
    )
    candidates = score_candidates(observations, sources, [], settings)
    gate = evaluate_quality(candidates, observations, sources, settings)
    assert candidates
    assert candidates[0].source_count == 8
    assert candidates[0].sector_count == 4
    assert gate.passed
