from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class Domain(StrEnum):
    ART = "art"
    FASHION = "fashion"
    MARKETPLACE = "marketplace"
    ADVERTISING = "advertising"
    DESIGN_INTERIORS = "design_interiors"
    ENTERTAINMENT = "entertainment"
    TECHNOLOGY = "technology"
    CREATOR_INDIE = "creator_indie"
    AUDIENCE_INTENT = "audience_intent"
    MATERIALS_PRODUCTION = "materials_production"
    PUBLIC_VISUAL_FIELD = "public_visual_field"
    FOOD_BEAUTY_LIFESTYLE = "food_beauty_lifestyle"


class SignalStage(StrEnum):
    CREATION = "creation"
    DISTRIBUTION = "distribution"
    ATTENTION = "attention"


class ScaleClass(StrEnum):
    INSTITUTIONAL = "institutional"
    LARGE_COMMERCIAL = "large_commercial"
    MID_SIZE = "mid_size"
    INDEPENDENT = "independent"
    GRASSROOTS = "grassroots"


class PanelType(StrEnum):
    BENCHMARK = "benchmark"
    DISCOVERY = "discovery"


class RightsMode(StrEnum):
    PUBLIC_DOMAIN = "public_domain"
    LICENSED = "licensed"
    ATTRIBUTION = "attribution"
    FIRST_PARTY = "first_party"
    ANALYZE_ONLY = "analyze_only"


class PublicationState(StrEnum):
    READY = "ready"
    REVIEW_ONLY = "review_only"
    BASELINE_ONLY = "baseline_only"
    BLOCKED = "blocked"


class TrendState(StrEnum):
    NEW = "new"
    RISING = "rising"
    SPREADING = "spreading"
    SURGING = "surging"
    STABLE = "stable"
    IDENTITY = "identity"
    COOLING = "cooling"
    CALIBRATION = "calibration"


@dataclass(slots=True)
class SourceSpec:
    id: str
    name: str
    enabled: bool
    adapter: str
    domain: Domain
    sector: str
    signal_stage: SignalStage
    scale_class: ScaleClass
    panel_type: PanelType
    event_type: str
    geography: str
    rights_mode: RightsMode
    url: str = ""
    api_url: str = ""
    platform: str = ""
    creator_id: str = ""
    weight: float = 1.0
    max_items: int = 8
    allowed_hosts: list[str] = field(default_factory=list)
    fallback_urls: list[str] = field(default_factory=list)
    include_selectors: list[str] = field(default_factory=list)
    exclude_selectors: list[str] = field(default_factory=list)
    known_house_colors: list[str] = field(default_factory=list)
    brand_mark_path: str = ""
    brand_mark_status: str = "none"
    query: str = ""
    token_env: str = ""
    api_key_env: str = ""
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvidenceRegion:
    source_id: str
    frame_id: str
    region_id: str
    selector_hint: str
    region_type: str
    screenshot_path: str
    bbox: tuple[int, int, int, int]
    viewport_area_ratio: float
    image_area_ratio: float
    text_density: float
    entropy: float
    edge_density: float
    confidence: float
    eligible: bool
    rejection_reason: str = ""
    page_url: str = ""
    page_title: str = ""
    published_at: str = ""
    rights_mode: str = "analyze_only"
    content_hash: str = ""
    perceptual_hash: str = ""


@dataclass(slots=True)
class Swatch:
    hex: str
    oklab: tuple[float, float, float]
    oklch: tuple[float, float, float]
    share: float
    salience: float
    is_neutral: bool
    adjusted_share: float | None = None
    largest_component_share: float = 0.0
    spatial_coverage: float = 0.0
    border_share: float = 0.0
    observed_pixel: bool = False
    structural_background: bool = False
    sampled_pixels: int = 0


@dataclass(slots=True)
class Observation:
    source_id: str
    source_name: str
    domain: Domain
    sector: str
    signal_stage: SignalStage
    scale_class: ScaleClass
    panel_type: PanelType
    event_type: str
    geography: str
    rights_mode: RightsMode
    platform: str
    creator_id: str
    captured_at: str
    region: EvidenceRegion
    swatches: list[Swatch]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CandidateEvidence:
    source_id: str
    source_name: str
    domain: str
    sector: str
    signal_stage: str
    scale_class: str
    panel_type: str
    region_id: str
    region_path: str
    local_hex: str
    local_oklab: tuple[float, float, float]
    distance_to_candidate: float
    local_share: float
    source_vote: float
    evidence_confidence: float
    page_title: str
    source_url: str
    rights_mode: str
    largest_component_share: float = 0.0
    spatial_coverage: float = 0.0
    observed_pixel: bool = False


@dataclass(slots=True)
class Candidate:
    hex: str
    oklab: tuple[float, float, float]
    oklch: tuple[float, float, float]
    family_label: str
    creative_name: str
    evidence: list[CandidateEvidence]
    source_count: int
    domain_count: int
    sector_count: int
    stage_count: int
    scale_count: int
    benchmark_count: int
    discovery_count: int
    current_usage_score: float
    emergence_score: float
    undercurrent_score: float
    mainstream_score: float
    novelty: float
    adoption_velocity: float
    cross_domain_spread: float
    cross_stage_convergence: float
    small_large_diversity: float
    evidence_quality: float
    top_source_weight: float
    top_domain_weight: float
    top_platform_weight: float
    score_margin: float = 0.0
    trend_state: TrendState = TrendState.CALIBRATION
    uncertainty: float = 0.0
    historical_days: int = 0
    matched_dates: list[str] = field(default_factory=list)
    display_hex_source_id: str = ""
    color_integrity: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PaletteRegime:
    neutral_share: float
    median_chroma: float
    mean_lightness: float
    warm_share: float
    cool_share: float
    mean_contrast: float
    mean_palette_size: float
    monochrome_share: float
    muted_share: float
    electric_share: float
    dominant_regime: str
    top_pairs: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class DailyResult:
    date: str
    state: PublicationState
    methodology_version: str
    registry_version: str
    panel_declared: int
    sources_attempted: int
    sources_captured: int
    sources_with_eligible_evidence: int
    domains_covered: int
    sectors_covered: int
    stages_covered: int
    benchmark_sources: int
    discovery_sources: int
    challenger: list[Candidate]
    undercurrent: Candidate | None
    mainstream_leader: Candidate | None
    usage_leader: Candidate | None
    runner_ups: list[Candidate]
    palette_regime: PaletteRegime
    palette_pair: dict[str, Any] | None
    blocking_reasons: list[str]
    review_reasons: list[str]
    baseline_days: int
    recurrence: dict[str, Any]
    reports: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


def _serialize(value: Any) -> Any:
    if isinstance(value, (Domain, SignalStage, ScaleClass, PanelType, RightsMode, PublicationState, TrendState)):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    if isinstance(value, tuple):
        return [_serialize(v) for v in value]
    return value
