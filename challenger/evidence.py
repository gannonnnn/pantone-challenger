from __future__ import annotations

from pathlib import Path

from .colors import aggregate_region_palettes, delta, extract_palette
from .config import Settings
from .models import (
    CandidateEvidence,
    CaptureRecord,
    RegionObservation,
    SourceObservation,
)


def _region_weight(region: RegionObservation) -> float:
    """Return a conservative confidence weight for one creative region.

    Image-heavy, high-confidence regions receive more influence, while text-heavy
    or weak regions remain measurable without dominating a company's one vote.
    """
    image_factor = 0.55 + 0.45 * max(0.0, min(region.image_area_ratio, 1.0))
    area_factor = 0.70 + 0.30 * min(region.viewport_area_ratio / 0.35, 1.0)
    return max(region.confidence, 0.01) * image_factor * area_factor


def observation_from_capture(
    record: CaptureRecord,
    settings: Settings,
) -> SourceObservation | None:
    """Convert captured creative regions into one normalized company observation.

    Whole-page frames are diagnostics only. Public evidence is generated exclusively
    from eligible creative-region captures.
    """
    if not record.regions:
        return None

    regions: list[RegionObservation] = []
    region_palettes: list[tuple[list, float]] = []
    hashes: list[str] = []
    for captured in record.regions:
        path = Path(captured.path)
        if not captured.eligible or not path.exists() or not path.is_file():
            continue
        try:
            swatches = extract_palette(
                [path],
                clusters_per_frame=9,
                max_swatches=6,
                merge_distance=settings.source_cluster_distance,
                region_mode=True,
            )
        except (OSError, ValueError):
            continue
        if not swatches:
            continue
        region = RegionObservation(
            region_id=captured.region_id,
            region_type=captured.region_type,
            screenshot_path=str(path),
            sha256=captured.sha256,
            confidence=captured.confidence,
            viewport_area_ratio=captured.viewport_area_ratio,
            image_area_ratio=captured.image_area_ratio,
            swatches=swatches,
        )
        regions.append(region)
        region_palettes.append((swatches, _region_weight(region)))
        hashes.append(captured.sha256)

    if not regions:
        return None

    aggregate = aggregate_region_palettes(
        region_palettes,
        merge_distance=settings.source_cluster_distance,
        max_swatches=7,
    )
    if not aggregate:
        return None

    return SourceObservation(
        source_id=record.source_id,
        source_name=record.source_name,
        sector=record.sector,
        url=record.final_url or record.url,
        captured_at=record.captured_at,
        screenshot_hashes=hashes,
        swatches=aggregate,
        regions=regions,
        page_title=record.title,
    )


def best_local_evidence(
    observation: SourceObservation,
    candidate_lab: tuple[float, float, float],
    max_distance: float,
    *,
    source_weight: float = 0.0,
) -> CandidateEvidence | None:
    """Return the strongest traceable region-level match for one company.

    A company is not allowed to support a candidate unless one of its captured
    creative regions contains a swatch within the configured perceptual distance.
    """
    best: tuple[float, RegionObservation, object, float] | None = None
    for region in observation.regions:
        for swatch in region.swatches:
            distance = delta(candidate_lab, swatch.oklab)
            if distance > max_distance:
                continue
            proximity = max(0.05, 1.0 - distance / max(max_distance, 1e-9))
            quality = swatch.share * _region_weight(region) * proximity
            if best is None or quality > best[0]:
                best = (quality, region, swatch, distance)

    if best is None:
        return None

    _, region, swatch, distance = best
    return CandidateEvidence(
        source_id=observation.source_id,
        source_name=observation.source_name,
        sector=observation.sector,
        region_id=region.region_id,
        region_path=region.screenshot_path,
        local_hex=swatch.hex,
        local_oklab=swatch.oklab,
        distance_to_candidate=round(distance, 6),
        local_share=round(swatch.share, 6),
        source_weight=round(max(source_weight, 0.0), 6),
        region_confidence=round(region.confidence, 6),
        page_title=observation.page_title,
        source_url=observation.url,
    )
