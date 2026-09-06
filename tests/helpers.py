from __future__ import annotations

from pathlib import Path

from PIL import Image

from challenger.color import hex_to_oklab, oklab_to_oklch
from challenger.models import (
    Candidate,
    CandidateEvidence,
    Domain,
    EvidenceRegion,
    Observation,
    PanelType,
    PublicationState,
    RightsMode,
    ScaleClass,
    SignalStage,
    Swatch,
    TrendState,
)


def make_image(path: Path, color: str, size=(600, 400)) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def observation(
    tmp_path: Path,
    source_id: str,
    color: str,
    *,
    domain: Domain = Domain.ART,
    sector: str = "art",
    stage: SignalStage = SignalStage.CREATION,
    scale: ScaleClass = ScaleClass.INDEPENDENT,
    panel: PanelType = PanelType.DISCOVERY,
    share: float = 0.40,
    confidence: float = 0.90,
) -> Observation:
    path = make_image(tmp_path / f"{source_id}.png", color)
    lab = hex_to_oklab(color)
    lch = oklab_to_oklch(lab)
    region = EvidenceRegion(
        source_id=source_id,
        frame_id=f"{source_id}-frame",
        region_id=f"{source_id}-region",
        selector_hint="test",
        region_type="image",
        screenshot_path=str(path),
        bbox=(0, 0, 600, 400),
        viewport_area_ratio=0.5,
        image_area_ratio=1.0,
        text_density=0.0,
        entropy=0.5,
        edge_density=0.2,
        confidence=confidence,
        eligible=True,
        page_url=f"https://example.test/{source_id}",
        page_title=source_id.title(),
        rights_mode="analyze_only",
        content_hash=source_id,
        perceptual_hash=f"{int.from_bytes(source_id.encode(), 'little') % (1<<64):016x}",
    )
    return Observation(
        source_id=source_id,
        source_name=source_id.title(),
        domain=domain,
        sector=sector,
        signal_stage=stage,
        scale_class=scale,
        panel_type=panel,
        event_type="newly_created",
        geography="global",
        rights_mode=RightsMode.ANALYZE_ONLY,
        platform=source_id,
        creator_id=source_id,
        captured_at="2026-09-05T00:00:00Z",
        region=region,
        swatches=[
            Swatch(
                hex=color,
                oklab=lab,
                oklch=lch,
                share=share,
                salience=share,
                is_neutral=lch[1] < 0.035,
                adjusted_share=share,
                largest_component_share=share,
                spatial_coverage=0.5,
                border_share=0.0,
                observed_pixel=True,
                structural_background=False,
                sampled_pixels=1000,
            )
        ],
        metadata={"registry_source_id": source_id},
    )


def candidate(color="#A5C84A", source_count=8, domains=6, stages=3, score=72.0, state=TrendState.SPREADING):
    lab = hex_to_oklab(color)
    lch = oklab_to_oklch(lab)
    evidence = []
    domain_names = ["art", "fashion", "marketplace", "advertising", "creator_indie", "technology"]
    stage_names = ["creation", "distribution", "attention"]
    for i in range(source_count):
        evidence.append(
            CandidateEvidence(
                source_id=f"source-{i}",
                source_name=f"Source {i}",
                domain=domain_names[i % max(1, min(domains, len(domain_names)))],
                sector=f"sector-{i%4}",
                signal_stage=stage_names[i % max(1, min(stages, len(stage_names)))],
                scale_class="independent" if i % 2 else "large_commercial",
                panel_type="discovery" if i % 2 else "benchmark",
                region_id=f"region-{i}",
                region_path="private",
                local_hex=color,
                local_oklab=lab,
                distance_to_candidate=0.01,
                local_share=0.2,
                source_vote=1.0,
                evidence_confidence=0.9,
                page_title=f"Source {i}",
                source_url=f"https://example.test/{i}",
                rights_mode="analyze_only",
                largest_component_share=0.20,
                spatial_coverage=0.50,
                observed_pixel=True,
            )
        )
    return Candidate(
        hex=color,
        oklab=lab,
        oklch=lch,
        family_label="Chartreuse",
        creative_name="NIGHT MARKET CHARTREUSE",
        evidence=evidence,
        source_count=source_count,
        domain_count=domains,
        sector_count=4,
        stage_count=stages,
        scale_count=2,
        benchmark_count=source_count // 2,
        discovery_count=source_count - source_count // 2,
        current_usage_score=68.0,
        emergence_score=score,
        undercurrent_score=75.0,
        mainstream_score=60.0,
        novelty=0.7,
        adoption_velocity=0.65,
        cross_domain_spread=0.9,
        cross_stage_convergence=1.0,
        small_large_diversity=1.0,
        evidence_quality=0.9,
        top_source_weight=1/source_count,
        top_domain_weight=0.25,
        top_platform_weight=0.20,
        score_margin=5.0,
        trend_state=state,
        uncertainty=0.2,
        historical_days=14,
        display_hex_source_id="source-0",
        color_integrity={
            "display_hex_is_observed": True,
            "all_local_hex_observed": True,
            "cluster_diameter": 0.0,
            "mean_component_share": 0.20,
            "minimum_component_share": 0.20,
            "mean_spatial_coverage": 0.50,
            "representative_source_id": "source-0",
        },
    )
