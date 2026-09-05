from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    sector: str
    url: str
    enabled: bool = True
    weight: float = 1.0
    region: str = "US"
    frames: int = 2
    notes: str = ""
    brand_mark_path: str = ""
    brand_mark_status: str = "text_only"
    brand_mark_fit: str = "contain"
    include_selectors: list[str] = field(default_factory=list)
    exclude_selectors: list[str] = field(default_factory=list)
    known_house_colors: list[str] = field(default_factory=list)


@dataclass
class CaptureFrame:
    path: str
    scroll_y: int
    sha256: str


@dataclass
class EvidenceRegion:
    source_id: str
    frame_id: str
    region_id: str
    selector_hint: str
    region_type: str
    path: str
    sha256: str
    bbox: tuple[int, int, int, int]
    viewport_area_ratio: float
    image_area_ratio: float
    text_density: float
    confidence: float
    eligible: bool = True
    rejection_reason: str = ""

    def to_dict(self, *, public: bool = False) -> dict[str, Any]:
        data = asdict(self)
        data["bbox"] = list(self.bbox)
        if public and data.get("path"):
            data["path"] = f"{self.source_id}/{Path(self.path).name}"
        return data


@dataclass
class CaptureRecord:
    source_id: str
    source_name: str
    sector: str
    url: str
    final_url: str = ""
    title: str = ""
    captured_at: str = ""
    success: bool = False
    blocked: bool = False
    error: str = ""
    frames: list[CaptureFrame] = field(default_factory=list)
    regions: list[EvidenceRegion] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "sector": self.sector,
            "url": self.url,
            "final_url": self.final_url,
            "title": self.title,
            "captured_at": self.captured_at,
            "success": self.success,
            "blocked": self.blocked,
            "error": self.error,
            "frames": [asdict(frame) for frame in self.frames],
            "regions": [region.to_dict() for region in self.regions],
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class Swatch:
    hex: str
    oklab: tuple[float, float, float]
    oklch: tuple[float, float, float]
    share: float
    adjusted_share: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "hex": self.hex,
            "oklab": list(self.oklab),
            "oklch": list(self.oklch),
            "share": self.share,
            "adjusted_share": self.adjusted_share,
        }


@dataclass
class RegionObservation:
    region_id: str
    screenshot_path: str
    sha256: str
    region_type: str
    confidence: float
    viewport_area_ratio: float
    image_area_ratio: float
    swatches: list[Swatch]

    def to_dict(self) -> dict[str, Any]:
        path = Path(self.screenshot_path)
        return {
            "region_id": self.region_id,
            "screenshot_path": f"{path.parent.name}/{path.name}" if self.screenshot_path else "",
            "sha256": self.sha256,
            "region_type": self.region_type,
            "confidence": self.confidence,
            "viewport_area_ratio": self.viewport_area_ratio,
            "image_area_ratio": self.image_area_ratio,
            "swatches": [swatch.to_dict() for swatch in self.swatches],
        }


@dataclass
class SourceObservation:
    source_id: str
    source_name: str
    sector: str
    url: str
    captured_at: str
    screenshot_hashes: list[str]
    swatches: list[Swatch]
    page_title: str = ""
    regions: list[RegionObservation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "sector": self.sector,
            "url": self.url,
            "captured_at": self.captured_at,
            "page_title": self.page_title,
            "screenshot_hashes": self.screenshot_hashes,
            "swatches": [swatch.to_dict() for swatch in self.swatches],
            "regions": [region.to_dict() for region in self.regions],
        }


@dataclass
class CandidateEvidence:
    source_id: str
    source_name: str
    sector: str
    region_id: str
    region_path: str
    local_hex: str
    local_oklab: tuple[float, float, float]
    distance_to_candidate: float
    local_share: float
    source_weight: float
    region_confidence: float
    page_title: str = ""
    source_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        path = Path(self.region_path)
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "sector": self.sector,
            "region_id": self.region_id,
            "region_path": f"{self.source_id}/{path.name}" if self.region_path else "",
            "local_hex": self.local_hex,
            "local_oklab": list(self.local_oklab),
            "distance_to_candidate": self.distance_to_candidate,
            "local_share": self.local_share,
            "source_weight": self.source_weight,
            "region_confidence": self.region_confidence,
            "page_title": self.page_title,
            "source_url": self.source_url,
        }


@dataclass
class Candidate:
    hex: str
    oklab: tuple[float, float, float]
    oklch: tuple[float, float, float]
    score: float
    source_count: int
    sector_count: int
    source_ids: list[str]
    source_names: list[str]
    sectors: list[str]
    prevalence: float
    sector_breadth: float
    mean_salience: float
    momentum: float
    baseline_prevalence: float
    neutral_penalty: float
    concentration_penalty: float
    components: dict[str, float]
    source_sectors: list[str] = field(default_factory=list)
    source_salience: list[float] = field(default_factory=list)
    evidence: list[CandidateEvidence] = field(default_factory=list)
    family_label: str = ""
    creative_name: str = ""
    confidence: str = "Calibration"
    top_source_weight: float = 0.0
    top_sector_weight: float = 0.0
    score_margin_to_next: float = 0.0
    evidence_region_count: int = 0
    mean_evidence_confidence: float = 0.0
    mean_evidence_distance: float = 0.0
    max_evidence_distance: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "hex": self.hex,
            "oklab": list(self.oklab),
            "oklch": list(self.oklch),
            "score": self.score,
            "source_count": self.source_count,
            "sector_count": self.sector_count,
            "source_ids": self.source_ids,
            "source_names": self.source_names,
            "sectors": self.sectors,
            "prevalence": self.prevalence,
            "sector_breadth": self.sector_breadth,
            "mean_salience": self.mean_salience,
            "momentum": self.momentum,
            "baseline_prevalence": self.baseline_prevalence,
            "neutral_penalty": self.neutral_penalty,
            "concentration_penalty": self.concentration_penalty,
            "components": self.components,
            "source_sectors": self.source_sectors,
            "source_salience": self.source_salience,
            "evidence": [item.to_dict() for item in self.evidence],
            "family_label": self.family_label,
            "creative_name": self.creative_name,
            "confidence": self.confidence,
            "top_source_weight": self.top_source_weight,
            "top_sector_weight": self.top_sector_weight,
            "score_margin_to_next": self.score_margin_to_next,
            "evidence_region_count": self.evidence_region_count,
            "mean_evidence_confidence": self.mean_evidence_confidence,
            "mean_evidence_distance": self.mean_evidence_distance,
            "max_evidence_distance": self.max_evidence_distance,
        }


@dataclass
class QualityGate:
    passed: bool
    reasons: list[str]
    usable_sources: int
    configured_sources: int
    usable_sectors: int
    configured_sectors: int
    state: str = "blocked"
    warnings: list[str] = field(default_factory=list)
    region_coverage_ratio: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RecurrenceSummary:
    year: int
    family_name: str
    representative_hex: str
    distance_threshold: float
    winning_days: int
    previous_winning_days: int
    current_streak: int
    longest_streak: int
    first_win_date: str
    latest_win_date: str
    matching_dates: list[str]
    unique_company_count: int
    unique_company_ids: list[str]
    unique_company_names: list[str]
    panel_company_count: int
    supporting_company_days: int
    average_analyzed_company_pages: float
    sectors: list[str]
    sector_count: int
    sector_day_counts: dict[str, int]
    ready_days_in_year: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DailyResult:
    date: str
    generated_at: str
    project: str
    methodology_version: str
    registry_version: str
    panel_size: int
    captured_sources: int
    captured_sectors: int
    baseline_days: int
    calibration_day: int
    status: str
    confidence_label: str
    quality_gate: QualityGate
    winner: Candidate | None
    winner_name: str | None
    runners_up: list[Candidate]
    source_failures: list[dict[str, str]]
    disclaimer: str
    runner_up_names: list[str] = field(default_factory=list)
    source_logos: dict[str, str] = field(default_factory=dict)
    recurrence: RecurrenceSummary | None = None

    def review_summary(self) -> dict[str, int | float | str]:
        winner_sources = self.winner.source_count if self.winner else 0
        winner_sectors = self.winner.sector_count if self.winner else 0
        return {
            "publication_state": self.status,
            "confidence": self.confidence_label,
            "company_pages_monitored": self.panel_size,
            "company_pages_with_evidence": self.captured_sources,
            "company_pages_analyzed": self.captured_sources,
            "company_pages_unavailable": max(self.panel_size - self.captured_sources, 0),
            "brands_supporting_winner": winner_sources,
            "sectors_in_panel": self.quality_gate.configured_sectors,
            "sectors_with_evidence": self.captured_sectors,
            "sectors_analyzed": self.captured_sectors,
            "sectors_supporting_winner": winner_sectors,
            "region_coverage_ratio": self.quality_gate.region_coverage_ratio,
            "winning_days_this_year": self.recurrence.winning_days if self.recurrence else 0,
            "unique_companies_across_matching_days": (
                self.recurrence.unique_company_count if self.recurrence else 0
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "generated_at": self.generated_at,
            "project": self.project,
            "methodology_version": self.methodology_version,
            "registry_version": self.registry_version,
            "panel_size": self.panel_size,
            "captured_sources": self.captured_sources,
            "captured_sectors": self.captured_sectors,
            "baseline_days": self.baseline_days,
            "calibration_day": self.calibration_day,
            "status": self.status,
            "confidence_label": self.confidence_label,
            "quality_gate": self.quality_gate.to_dict(),
            "review_summary": self.review_summary(),
            "winner": self.winner.to_dict() if self.winner else None,
            "winner_name": self.winner_name,
            "runners_up": [candidate.to_dict() for candidate in self.runners_up],
            "runner_up_names": self.runner_up_names,
            "source_failures": self.source_failures,
            "source_logos": self.source_logos,
            "recurrence": self.recurrence.to_dict() if self.recurrence else None,
            "disclaimer": self.disclaimer,
        }


def swatch_from_dict(data: dict[str, Any]) -> Swatch:
    return Swatch(
        hex=str(data["hex"]),
        oklab=tuple(float(value) for value in data["oklab"]),
        oklch=tuple(float(value) for value in data["oklch"]),
        share=float(data["share"]),
        adjusted_share=float(data.get("adjusted_share", 0.0)),
    )


def region_observation_from_dict(data: dict[str, Any]) -> RegionObservation:
    path = str(data.get("screenshot_path") or data.get("path") or "")
    return RegionObservation(
        region_id=str(data.get("region_id", "")),
        screenshot_path=path,
        sha256=str(data.get("sha256", "")),
        region_type=str(data.get("region_type", "unknown")),
        confidence=float(data.get("confidence", 0.0)),
        viewport_area_ratio=float(data.get("viewport_area_ratio", 0.0)),
        image_area_ratio=float(data.get("image_area_ratio", 0.0)),
        swatches=[swatch_from_dict(item) for item in data.get("swatches", [])],
    )


def observation_from_dict(data: dict[str, Any]) -> SourceObservation:
    return SourceObservation(
        source_id=str(data["source_id"]),
        source_name=str(data["source_name"]),
        sector=str(data["sector"]),
        url=str(data["url"]),
        captured_at=str(data["captured_at"]),
        screenshot_hashes=[str(value) for value in data.get("screenshot_hashes", [])],
        swatches=[swatch_from_dict(item) for item in data.get("swatches", [])],
        page_title=str(data.get("page_title", "")),
        regions=[region_observation_from_dict(item) for item in data.get("regions", [])],
    )
