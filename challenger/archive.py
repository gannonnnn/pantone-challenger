from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from .models import CaptureRecord, DailyResult, SourceObservation


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
    payload = record.to_dict()
    for frame in payload.get("frames", []):
        frame["path"] = f"{record.source_id}/{Path(frame['path']).name}"
    if payload.get("logo_path"):
        payload["logo_path"] = f"logos/{record.source_id}.png"
    return payload


def _copy_source_logos(day_dir: Path, captures: list[CaptureRecord]) -> dict[str, str]:
    logos: dict[str, str] = {}
    logo_dir = day_dir / "logos"
    for record in captures:
        if not record.logo_path:
            continue
        source = Path(record.logo_path)
        if not source.exists() or not source.is_file():
            continue
        logo_dir.mkdir(parents=True, exist_ok=True)
        destination = logo_dir / f"{record.source_id}.png"
        shutil.copy2(source, destination)
        logos[record.source_id] = f"logos/{record.source_id}.png"
    return logos


def write_analysis_archive(
    archive_root: Path,
    result: DailyResult,
    observations: list[SourceObservation],
    captures: list[CaptureRecord],
) -> Path:
    day_dir = archive_root / result.date
    day_dir.mkdir(parents=True, exist_ok=True)
    result.source_logos = _copy_source_logos(day_dir, captures)
    _write_json(day_dir / "result.json", result.to_dict())
    _write_json(
        day_dir / "observations.json",
        {
            "date": result.date,
            "methodology_version": result.methodology_version,
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
            "captured_logos": len(result.source_logos),
            "records": [_public_capture_record(item) for item in captures],
        },
    )
    return day_dir


def write_publish_package(day_dir: Path, result: DailyResult, assets: list[Path]) -> Path:
    asset_names = [path.name for path in assets if path.exists()]
    package = {
        "date": result.date,
        "status": "ready_for_review" if result.status == "ready" else "blocked",
        "quality_gate_passed": result.quality_gate.passed,
        "coverage": {
            "reviewed_sources": result.panel_size,
            "usable_sources": result.captured_sources,
            "usable_sectors": result.captured_sectors,
            "winner_supporting_sources": result.winner.source_count if result.winner else 0,
            "winner_supporting_sectors": result.winner.sector_count if result.winner else 0,
        },
        "recurrence": result.recurrence.to_dict() if result.recurrence else None,
        "caption_file": "caption.txt" if (day_dir / "caption.txt").exists() else None,
        "review_file": (
            "review-summary.md" if (day_dir / "review-summary.md").exists() else None
        ),
        "feed_asset": "feed-post.png" if (day_dir / "feed-post.png").exists() else None,
        "story_assets": sorted(
            name for name in asset_names if name.startswith("story-")
        ),
        "logo_directory": "logos" if (day_dir / "logos").exists() else None,
        "public_asset_path": f"assets/{result.date}",
        "approval_model": (
            "Merge the generated daily pull request to approve publication. "
            "Social publishing remains manual unless AUTO_PUBLISH is explicitly enabled."
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
