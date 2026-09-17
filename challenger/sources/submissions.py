from __future__ import annotations

import csv
from pathlib import Path

import httpx

from challenger.capture.items import download_item_image, evidence_region_from_item
from challenger.sources.base import CollectionResult, SourceAdapter


class SubmissionInboxAdapter(SourceAdapter):
    """Read moderator-approved public submissions from a local CSV."""

    def collect(self, source, run_date):
        result = CollectionResult(source=source, report={"adapter": "approved_submission_inbox"})
        csv_path = Path(source.options.get("path", "data/inbox/approved-submissions.csv"))
        if not csv_path.is_absolute():
            csv_path = Path.cwd() / csv_path
        if not csv_path.exists():
            result.report.update(status="skipped_missing_inbox", path=str(csv_path))
            return self.finalize_result(result)

        with csv_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        approved = [row for row in rows if row.get("approved", "").lower() in {"true", "yes", "1"}]
        with httpx.Client(
            headers={"User-Agent": "PantoneChallenger/1.6.0"},
            timeout=self.http_timeout_s,
            follow_redirects=True,
        ) as client:
            for index, row in enumerate(approved[: source.max_items], start=1):
                if self.expired(reserve_seconds=1.0):
                    break
                image_url = row.get("image_url", "")
                if not image_url:
                    continue
                suffix = Path(image_url.split("?")[0]).suffix or ".jpg"
                path = self.workdir / "captures" / run_date / source.id / f"submission-{index:03d}{suffix}"
                ok, reason = download_item_image(
                    client,
                    image_url,
                    path,
                    timeout_s=self.request_timeout(),
                )
                if not ok:
                    result.report.setdefault("rejections", []).append(
                        {"row": index, "reason": reason}
                    )
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
        return self.finalize_result(result)
