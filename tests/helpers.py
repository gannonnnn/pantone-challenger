from __future__ import annotations

from pathlib import Path

from PIL import Image

from challenger.colors import oklab_from_hex, oklab_to_oklch
from challenger.models import (
    Candidate,
    CandidateEvidence,
    RegionObservation,
    SourceObservation,
    Swatch,
)


def swatch(value: str, share: float, adjusted: float | None = None) -> Swatch:
    lab = oklab_from_hex(value)
    return Swatch(
        hex=value.upper(),
        oklab=lab,
        oklch=oklab_to_oklch(lab),
        share=share,
        adjusted_share=share if adjusted is None else adjusted,
    )


def make_region_image(path: Path, value: str, accent: str = "#E8E3D8") -> Path:
    image = Image.new("RGB", (420, 260), value)
    for x in range(0, 80):
        for y in range(0, 260):
            image.putpixel((x, y), tuple(int(accent[i:i + 2], 16) for i in (1, 3, 5)))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def observation(
    source_id: str,
    sector: str,
    value: str,
    *,
    share: float = 0.55,
    region_confidence: float = 0.82,
    region_path: Path | None = None,
    second: str = "#D8C6A1",
) -> SourceObservation:
    region_path = region_path or Path(f"/tmp/{source_id}-region.png")
    primary = swatch(value, share)
    secondary = swatch(second, 1.0 - share)
    region = RegionObservation(
        region_id=f"{source_id}-r1",
        screenshot_path=str(region_path),
        sha256=f"hash-{source_id}",
        region_type="hero",
        confidence=region_confidence,
        viewport_area_ratio=0.30,
        image_area_ratio=0.85,
        swatches=[primary, secondary],
    )
    return SourceObservation(
        source_id=source_id,
        source_name=source_id.replace("-", " ").title(),
        sector=sector,
        url=f"https://example.com/{source_id}",
        captured_at="2026-08-30T20:00:00-04:00",
        screenshot_hashes=[f"hash-{source_id}"],
        swatches=[primary, secondary],
        page_title=f"{source_id} marketing",
        regions=[region],
    )


def candidate(
    value: str,
    *,
    score: float = 80.0,
    source_count: int = 8,
    sectors: list[str] | None = None,
    with_evidence: bool = True,
) -> Candidate:
    sectors = sectors or ["technology", "retail", "beauty", "travel"]
    labs = oklab_from_hex(value)
    evidence: list[CandidateEvidence] = []
    source_ids = [f"fictional-{index}" for index in range(source_count)]
    source_names = [f"Fictional Brand {index}" for index in range(source_count)]
    source_sectors = [sectors[index % len(sectors)] for index in range(source_count)]
    if with_evidence:
        for index, source_id in enumerate(source_ids):
            evidence.append(
                CandidateEvidence(
                    source_id=source_id,
                    source_name=source_names[index],
                    sector=source_sectors[index],
                    region_id=f"{source_id}-r1",
                    region_path="",
                    local_hex=value,
                    local_oklab=labs,
                    distance_to_candidate=0.0,
                    local_share=0.35,
                    source_weight=1.0 / source_count,
                    region_confidence=0.82,
                    page_title="Fictional marketing page",
                    source_url=f"https://example.com/{source_id}",
                )
            )
    return Candidate(
        hex=value.upper(),
        oklab=labs,
        oklch=oklab_to_oklch(labs),
        score=score,
        source_count=source_count,
        sector_count=len(set(source_sectors)),
        source_ids=source_ids,
        source_names=source_names,
        sectors=sorted(set(source_sectors)),
        prevalence=0.35,
        sector_breadth=0.50,
        mean_salience=0.25,
        momentum=0.72,
        baseline_prevalence=0.12,
        neutral_penalty=0.0,
        concentration_penalty=0.0,
        components={"source_breadth": 20.0},
        source_sectors=source_sectors,
        source_salience=[0.25 for _ in range(source_count)],
        evidence=evidence,
        family_label="Green",
        creative_name="Fictional Campaign",
        confidence="Calibration",
        top_source_weight=1.0 / source_count,
        top_sector_weight=max(source_sectors.count(item) for item in set(source_sectors)) / source_count,
        score_margin_to_next=8.0,
        evidence_region_count=len(evidence),
        mean_evidence_confidence=0.82 if evidence else 0.0,
        mean_evidence_distance=0.0,
        max_evidence_distance=0.0,
    )
