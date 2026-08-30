from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .models import Source


@dataclass(frozen=True)
class Settings:
    project_name: str = "Pantone Challenger"
    methodology_version: str = "1.2"
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
    cluster_distance: float = 0.055
    source_cluster_distance: float = 0.045
    recurrence_distance: float = 0.055
    baseline_lookback_days: int = 30
    baseline_warmup_days: int = 7
    baseline_suppression: float = 0.75
    unchanged_page_factor: float = 0.35
    min_usable_sources: int = 20
    min_usable_sectors: int = 8
    min_winner_sources: int = 5
    min_winner_sectors: int = 3
    min_candidates: int = 3
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


def load_sources(config_dir: Path | str = "config") -> list[Source]:
    config_dir = Path(config_dir)
    data = load_yaml(config_dir / "sources.yml")
    raw_sources = data.get("sources", [])
    if not isinstance(raw_sources, list):
        raise ValueError("sources.yml must contain a 'sources' list")
    sources = [Source(**item) for item in raw_sources]
    validate_sources(sources)
    return [source for source in sources if source.enabled]


def validate_sources(sources: list[Source]) -> None:
    if not sources:
        raise ValueError("The source panel is empty")
    ids = [s.id for s in sources]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        raise ValueError(f"Duplicate source ids: {', '.join(duplicates)}")
    for source in sources:
        if not source.url.startswith(("https://", "http://")):
            raise ValueError(f"Source {source.id} has an invalid URL")
        if source.weight <= 0:
            raise ValueError(f"Source {source.id} must have a positive weight")
        if not source.sector.strip():
            raise ValueError(f"Source {source.id} has no sector")


def panel_summary(sources: list[Source]) -> dict[str, Any]:
    sectors: dict[str, int] = {}
    for source in sources:
        sectors[source.sector] = sectors.get(source.sector, 0) + 1
    return {
        "sources": len(sources),
        "sectors": len(sectors),
        "sector_counts": dict(sorted(sectors.items())),
    }
