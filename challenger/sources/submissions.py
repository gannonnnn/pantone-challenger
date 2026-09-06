from __future__ import annotations

import csv
from pathlib import Path

import httpx

from challenger.capture.items import download_item_image, evidence_region_from_item
from challenger.sources.base import CollectionResult, SourceAdapter


class SubmissionInboxAdapter(SourceAdapter):
    """Reads moderator-approved public submissions from a local CSV.

    The inbox is intentionally opt-in and never crawls arbitrary user URLs. Each row must
    include an approved direct image URL plus provenance and rights classification.
    """

    def collect(self, source, run_date):
        result = CollectionResult(source=source, report={"adapter": "approved_submission_inbox"})
        csv_path = Path(source.options.get("path", "data/inbox/approved-submissions.csv"))
        if not csv_path.is_absolute():
            csv_path = Path.cwd() / csv_path
        if not csv_path.exists():
            result.report.update(status="skipped_missing_inbox", path=str(csv_path))
            return result
        client = httpx.Client(headers={"User-Agent": "PantoneChallenger/1.5"}, timeout=30)
        with csv_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        approved = [r for r in rows if r.get("approved", "").lower() in {"true", "yes", "1"}]
        for index, row in enumerate(approved[: source.max_items], start=1):
            image_url = row.get("image_url", "")
            if not image_url:
                continue
            suffix = Path(image_url.split("?")[0]).suffix or ".jpg"
            path = self.workdir / "captures" / run_date / source.id / f"submission-{index:03d}{suffix}"
            ok, reason = download_item_image(client, image_url, path)
            if not ok:
                result.report.setdefault("rejections", []).append({"row": index, "reason": reason})
                continue
            item = {
                "title": row.get("title", ""),
                "url": row.get("source_url", ""),
                "published_at": row.get("published_at", ""),
            }
            region = evidence_region_from_item(source, item, path, index)
            if region:
                result.regions.append(region)
        result.report["eligible_region_count"] = len(result.regions)
        result.report["status"] = "captured" if result.regions else "no_eligible_region"
        return result
