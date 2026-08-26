from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..archive import latest_ready_date


class PublishError(RuntimeError):
    pass


def load_publish_context(
    archive_root: Path,
    requested_date: str,
) -> tuple[str, Path, dict[str, Any], dict[str, Any]]:
    date_value = requested_date
    if requested_date in ("latest", "auto", ""):
        date_value = latest_ready_date(archive_root) or ""
    if not date_value:
        raise PublishError("No ready daily result exists in the archive")
    day_dir = archive_root / date_value
    result_path = day_dir / "result.json"
    package_path = day_dir / "publish-package.json"
    if not result_path.exists() or not package_path.exists():
        raise PublishError(f"The daily publishing package is incomplete for {date_value}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    package = json.loads(package_path.read_text(encoding="utf-8"))
    if result.get("status") != "ready" or not result.get("quality_gate", {}).get("passed"):
        raise PublishError("The data-quality gate did not approve this daily result")
    if package.get("status") != "ready_for_review":
        raise PublishError("The package is not ready for publication")
    published_path = day_dir / "published.json"
    if published_path.exists():
        raise PublishError(
            f"{date_value} already has a published.json record. Use the explicit force "
            "option only after checking the social account for duplicates."
        )
    return date_value, day_dir, result, package


def require_approval(approved: bool) -> None:
    if not approved:
        raise PublishError(
            "Publishing is approval-gated. Re-run with --approve after reviewing the "
            "daily pull request and generated social assets."
        )
