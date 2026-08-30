from __future__ import annotations

from dataclasses import asdict, dataclass, field
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


@dataclass
class CaptureFrame:
    path: str
    scroll_y: int
    sha256: str


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
    logo_path: str = ""
    logo_source: str = ""
    logo_error: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Swatch:
    hex: str
    oklab: tuple[float, float, float]
    oklch: tuple[float, float, float]
    share: float
    adjusted_share: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["oklab"] = list(self.oklab)
        data["oklch"] = list(self.oklch)
        return data


@dataclass
class SourceObservation:
    source_id: str
    source_name: str
    sector: str
    url: str
    captured_at: str
    screenshot_hashes: list[str]
    swatches: list[Swatch]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "sector": self.sector,
            "url": self.url,
            "captured_at": self.captured_at,
            "screenshot_hashes": self.screenshot_hashes,
            "swatches": [s.to_dict() for s in self.swatches],
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

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["oklab"] = list(self.oklab)
        data["oklch"] = list(self.oklch)
        return data


@dataclass
class QualityGate:
    passed: bool
    reasons: list[str]
    usable_sources: int
    configured_sources: int
    usable_sectors: int
    configured_sectors: int

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
    panel_size: int
    captured_sources: int
    captured_sectors: int
    baseline_days: int
    status: str
    quality_gate: QualityGate
    winner: Candidate | None
    winner_name: str | None
    runners_up: list[Candidate]
    source_failures: list[dict[str, str]]
    disclaimer: str
    runner_up_names: list[str] = field(default_factory=list)
    source_logos: dict[str, str] = field(default_factory=dict)
    recurrence: RecurrenceSummary | None = None

    def review_summary(self) -> dict[str, int]:
        winner_sources = self.winner.source_count if self.winner else 0
        winner_sectors = self.winner.sector_count if self.winner else 0
        return {
            "company_pages_monitored": self.panel_size,
            "company_pages_analyzed": self.captured_sources,
            "company_pages_unavailable": max(self.panel_size - self.captured_sources, 0),
            "brands_supporting_winner": winner_sources,
            "sectors_in_panel": self.quality_gate.configured_sectors,
            "sectors_analyzed": self.captured_sectors,
            "sectors_supporting_winner": winner_sectors,
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
            "panel_size": self.panel_size,
            "captured_sources": self.captured_sources,
            "captured_sectors": self.captured_sectors,
            "baseline_days": self.baseline_days,
            "status": self.status,
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
        hex=data["hex"],
        oklab=tuple(float(value) for value in data["oklab"]),
        oklch=tuple(float(value) for value in data["oklch"]),
        share=float(data["share"]),
        adjusted_share=float(data.get("adjusted_share", 0.0)),
    )


def observation_from_dict(data: dict[str, Any]) -> SourceObservation:
    return SourceObservation(
        source_id=data["source_id"],
        source_name=data["source_name"],
        sector=data["sector"],
        url=data["url"],
        captured_at=data["captured_at"],
        screenshot_hashes=list(data.get("screenshot_hashes", [])),
        swatches=[swatch_from_dict(swatch) for swatch in data["swatches"]],
    )
