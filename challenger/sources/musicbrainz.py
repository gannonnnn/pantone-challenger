from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import httpx

from challenger.capture.items import download_item_image, evidence_region_from_item
from challenger.sources.base import CollectionResult, SourceAdapter


class MusicBrainzAdapter(SourceAdapter):
    API = "https://musicbrainz.org/ws/2/release-group"

    def collect(self, source, run_date):
        result = CollectionResult(source=source, report={"adapter": "musicbrainz_cover_art"})
        day = date.fromisoformat(run_date)
        start = day - timedelta(days=int(source.options.get("lookback_days", 14)))
        query = f"firstreleasedate:[{start.isoformat()} TO {day.isoformat()}] AND primarytype:Album"
        with httpx.Client(
            headers={"User-Agent": "PantoneChallenger/1.6.0 (open cultural color research)"},
            timeout=self.http_timeout_s,
            follow_redirects=True,
        ) as client:
            try:
                response = client.get(
                    self.API,
                    params={"query": query, "fmt": "json", "limit": source.max_items * 2},
                    timeout=self.request_timeout(),
                )
                response.raise_for_status()
                groups = response.json().get("release-groups", [])
            except Exception as exc:  # noqa: BLE001
                result.report.update(status="error", error=f"{type(exc).__name__}: {exc}")
                return self.finalize_result(result)

            for index, group in enumerate(groups, start=1):
                if self.expired(reserve_seconds=1.0):
                    break
                gid = group.get("id")
                if not gid:
                    continue
                image_url = f"https://coverartarchive.org/release-group/{gid}/front-500"
                path = self.workdir / "captures" / run_date / source.id / f"cover-{gid}.jpg"
                ok, _ = download_item_image(
                    client,
                    image_url,
                    path,
                    allowed_hosts=["coverartarchive.org", "archive.org"],
                    timeout_s=self.request_timeout(),
                )
                if not ok:
                    continue
                item = {
                    "title": group.get("title", ""),
                    "url": f"https://musicbrainz.org/release-group/{gid}",
                    "published_at": group.get("first-release-date", ""),
                }
                region = evidence_region_from_item(source, item, path, index)
                if region:
                    result.regions.append(region)
                if len(result.regions) >= source.max_items:
                    break

        result.report["eligible_region_count"] = len(result.regions)
        result.report["status"] = "captured" if result.regions else "no_eligible_region"
        return self.finalize_result(result)
