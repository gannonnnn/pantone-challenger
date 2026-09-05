from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .models import Source


ALLOWED_SECTORS = {
    "technology",
    "retail",
    "food_beverage",
    "entertainment",
    "beauty",
    "travel",
    "finance",
    "automotive",
    "sports",
    "home",
    "fashion",
    "gaming",
}
ALLOWED_BRAND_MARK_STATUSES = {"approved", "text_only"}
ALLOWED_BRAND_MARK_FITS = {"contain"}


@dataclass(frozen=True)
class Settings:
    project_name: str = "Pantone Challenger"
    methodology_version: str = "1.3.0"
    timezone: str = "America/New_York"
    rollover_hour: int = 4
    viewport_width: int = 1440
    viewport_height: int = 1200
    frames_per_source: int = 2
    second_frame_scroll_y: int = 900
    navigation_timeout_ms: int = 45000
    post_load_wait_ms: int = 3500
    concurrency: int = 3
    request_delay_seconds: float = 1.0

    max_regions_per_source: int = 3
    max_region_candidates_per_frame: int = 8
    min_region_width: int = 280
    min_region_height: int = 180
    min_region_viewport_area: float = 0.04
    min_region_confidence: float = 0.65

    cluster_distance: float = 0.055
    source_cluster_distance: float = 0.045
    recurrence_distance: float = 0.055
    runner_distinct_distance: float = 0.040
    evidence_max_distance: float = 0.055

    baseline_lookback_days: int = 30
    baseline_warmup_days: int = 7
    calibration_days: int = 7
    baseline_suppression: float = 0.75
    unchanged_page_factor: float = 0.35

    display_min_chroma: float = 0.040
    neutral_warmup_days: int = 14
    neutral_min_momentum_ratio: float = 2.0
    neutral_min_sources: int = 10
    neutral_min_sectors: int = 6

    min_review_sources: int = 20
    min_review_sectors: int = 7
    min_review_region_coverage_ratio: float = 0.40
    min_ready_sources: int = 30
    min_ready_sectors: int = 9
    min_ready_region_coverage_ratio: float = 0.60

    min_winner_sources: int = 6
    min_winner_sectors: int = 4
    min_winner_evidence_regions: int = 4
    min_mean_evidence_confidence: float = 0.68
    max_mean_evidence_distance: float = 0.045
    max_evidence_distance: float = 0.055
    max_source_weight: float = 0.30
    max_sector_weight: float = 0.50
    min_score_margin: float = 2.5

    min_runner_sources: int = 5
    min_runner_sectors: int = 3
    min_candidates: int = 1
    raw_capture_retention_days: int = 14


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return data


def load_settings(config_dir: Path | str = "config") -> Settings:
    config_dir = Path(config_dir)
    data = load_yaml(config_dir / "settings.yml")
    known = Settings.__dataclass_fields__.keys()
    clean = {key: value for key, value in data.items() if key in known}
    return Settings(**clean)


def load_source_panel(config_dir: Path | str = "config") -> tuple[str, list[Source]]:
    config_dir = Path(config_dir)
    data = load_yaml(config_dir / "sources.yml")
    raw_sources = data.get("sources", [])
    if not isinstance(raw_sources, list):
        raise ValueError("sources.yml must contain a 'sources' list")
    sources = [Source(**item) for item in raw_sources]
    validate_sources(sources, project_root=config_dir.parent)
    version = str(data.get("panel_version", "unknown"))
    return version, [source for source in sources if source.enabled]


def load_sources(config_dir: Path | str = "config") -> list[Source]:
    return load_source_panel(config_dir)[1]


def validate_sources(sources: list[Source], *, project_root: Path | None = None) -> None:
    if not sources:
        raise ValueError("The source panel is empty")
    ids = [source.id for source in sources]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        raise ValueError(f"Duplicate source ids: {', '.join(duplicates)}")

    root = project_root or Path(".")
    for source in sources:
        if not source.url.startswith(("https://", "http://")):
            raise ValueError(f"Source {source.id} has an invalid URL")
        if source.weight <= 0:
            raise ValueError(f"Source {source.id} must have a positive weight")
        if source.sector not in ALLOWED_SECTORS:
            raise ValueError(
                f"Source {source.id} has unsupported sector {source.sector!r}; "
                f"expected one of {', '.join(sorted(ALLOWED_SECTORS))}"
            )
        if source.brand_mark_status not in ALLOWED_BRAND_MARK_STATUSES:
            raise ValueError(
                f"Source {source.id} has unsupported brand_mark_status "
                f"{source.brand_mark_status!r}"
            )
        if source.brand_mark_fit not in ALLOWED_BRAND_MARK_FITS:
            raise ValueError(
                f"Source {source.id} has unsupported brand_mark_fit {source.brand_mark_fit!r}"
            )
        if source.brand_mark_status == "approved":
            if not source.brand_mark_path:
                raise ValueError(
                    f"Source {source.id} is marked approved but has no brand_mark_path"
                )
            mark = root / source.brand_mark_path
            if not mark.exists() or not mark.is_file():
                raise ValueError(
                    f"Source {source.id} references a missing approved brand mark: {mark}"
                )


def panel_summary(sources: list[Source]) -> dict[str, Any]:
    sectors: dict[str, int] = {}
    approved_marks = 0
    for source in sources:
        sectors[source.sector] = sectors.get(source.sector, 0) + 1
        if source.brand_mark_status == "approved":
            approved_marks += 1
    return {
        "sources": len(sources),
        "sectors": len(sectors),
        "approved_brand_marks": approved_marks,
        "text_only_sources": len(sources) - approved_marks,
        "sector_counts": dict(sorted(sectors.items())),
    }
