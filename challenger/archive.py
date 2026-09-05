from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from .models import CaptureRecord, DailyResult, Source, SourceObservation


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _public_capture_record(record: CaptureRecord) -> dict[str, Any]:
    return {
        "source_id": record.source_id,
        "source_name": record.source_name,
        "sector": record.sector,
        "url": record.url,
        "final_url": record.final_url,
        "title": record.title,
        "captured_at": record.captured_at,
        "success": record.success,
        "blocked": record.blocked,
        "error": record.error,
        "duration_seconds": record.duration_seconds,
        "frames": [
            {
                "path": f"{record.source_id}/{Path(frame.path).name}",
                "scroll_y": frame.scroll_y,
                "sha256": frame.sha256,
            }
            for frame in record.frames
        ],
        "regions": [region.to_dict(public=True) for region in record.regions],
    }


def _copy_curated_brand_marks(
    day_dir: Path,
    sources: list[Source],
    *,
    project_root: Path,
) -> dict[str, str]:
    """Copy only manually approved marks. Runtime favicons are never public assets."""
    marks: dict[str, str] = {}
    destination_dir = day_dir / "brand-marks"
    for source in sources:
        if source.brand_mark_status != "approved" or not source.brand_mark_path:
            continue
        mark = Path(source.brand_mark_path)
        if not mark.is_absolute():
            mark = project_root / mark
        if not mark.exists() or not mark.is_file():
            continue
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / f"{source.id}{mark.suffix.lower()}"
        shutil.copy2(mark, destination)
        marks[source.id] = f"brand-marks/{destination.name}"
    return marks


def write_analysis_archive(
    archive_root: Path,
    result: DailyResult,
    observations: list[SourceObservation],
    captures: list[CaptureRecord],
    *,
    sources: list[Source],
    project_root: Path = Path("."),
) -> Path:
    day_dir = archive_root / result.date
    day_dir.mkdir(parents=True, exist_ok=True)
    result.source_logos = _copy_curated_brand_marks(
        day_dir,
        sources,
        project_root=project_root,
    )
    _write_json(day_dir / "result.json", result.to_dict())
    _write_json(
        day_dir / "observations.json",
        {
            "date": result.date,
            "publication_state": result.status,
            "methodology_version": result.methodology_version,
            "registry_version": result.registry_version,
            "observations": [item.to_dict() for item in observations],
        },
    )
    _write_json(
        day_dir / "capture-report.json",
        {
            "date": result.date,
            "configured_sources": result.panel_size,
            "usable_sources": result.captured_sources,
            "configured_sectors": result.quality_gate.configured_sectors,
            "usable_sectors": result.captured_sectors,
            "eligible_regions": sum(len(item.regions) for item in captures),
            "approved_brand_marks": len(result.source_logos),
            "records": [_public_capture_record(item) for item in captures],
        },
    )
    return day_dir


def write_publish_package(day_dir: Path, result: DailyResult, assets: list[Path]) -> Path:
    asset_names = [path.name for path in assets if path.exists()]
    status_map = {
        "ready": "ready_for_review",
        "review_only": "internal_calibration",
        "blocked": "blocked",
    }
    package = {
        "date": result.date,
        "status": status_map.get(result.status, result.status),
        "public_posting_allowed": result.status == "ready",
        "quality_gate_passed": result.quality_gate.passed,
        "coverage": {
            "monitored_sources": result.panel_size,
            "usable_sources": result.captured_sources,
            "usable_sectors": result.captured_sectors,
            "winner_supporting_sources": result.winner.source_count if result.winner else 0,
            "winner_supporting_sectors": result.winner.sector_count if result.winner else 0,
            "region_coverage_ratio": result.quality_gate.region_coverage_ratio,
        },
        "recurrence": result.recurrence.to_dict() if result.recurrence else None,
        "caption_file": "caption.txt" if (day_dir / "caption.txt").exists() else None,
        "review_file": (
            "review-summary.md" if (day_dir / "review-summary.md").exists() else None
        ),
        "feed_asset": "feed-post.png" if (day_dir / "feed-post.png").exists() else None,
        "story_assets": sorted(name for name in asset_names if name.startswith("story-")),
        "alt_text_files": sorted(
            name for name in asset_names if name.endswith("-alt-text.txt")
        ),
        "brand_mark_directory": (
            "brand-marks" if (day_dir / "brand-marks").exists() else None
        ),
        "public_asset_path": (
            f"assets/{result.date}" if result.status == "ready" else None
        ),
        "approval_model": (
            "Ready results may be approved by merging the generated daily pull request. "
            "Calibration results may be merged to warm baselines but must not be posted."
        ),
    }
    _write_json(day_dir / "publish-package.json", package)
    return day_dir / "publish-package.json"


def write_manifest(day_dir: Path) -> Path:
    files = [
        path
        for path in sorted(day_dir.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    ]
    payload = {
        "files": [
            {
                "name": str(path.relative_to(day_dir)),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in files
        ]
    }
    _write_json(day_dir / "manifest.json", payload)
    return day_dir / "manifest.json"


def latest_ready_date(archive_root: Path) -> str | None:
    ready: list[str] = []
    if not archive_root.exists():
        return None
    for directory in archive_root.iterdir():
        if not directory.is_dir():
            continue
        result_path = directory / "result.json"
        if not result_path.exists():
            continue
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if result.get("status") == "ready":
            ready.append(directory.name)
    return max(ready) if ready else None
