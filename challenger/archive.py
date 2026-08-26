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
    return payload

def write_analysis_archive(
    archive_root: Path,
    result: DailyResult,
    observations: list[SourceObservation],
    captures: list[CaptureRecord],
) -> Path:
    day_dir = archive_root / result.date
    day_dir.mkdir(parents=True, exist_ok=True)
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
        "caption_file": "caption.txt" if (day_dir / "caption.txt").exists() else None,
        "feed_asset": "feed-post.png" if (day_dir / "feed-post.png").exists() else None,
        "story_assets": sorted(
            name for name in asset_names if name.startswith("story-")
        ),
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
        for path in sorted(day_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    ]
    payload = {
        "files": [
            {
                "name": path.name,
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
