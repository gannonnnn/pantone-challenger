from __future__ import annotations

from pathlib import Path

import httpx

from challenger.capture.items import download_item_image, evidence_region_from_item
from challenger.sources.base import CollectionResult, SourceAdapter


class ITunesSearchAdapter(SourceAdapter):
    API = "https://itunes.apple.com/search"

    def collect(self, source, run_date):
        result = CollectionResult(source=source, report={"adapter": "itunes_search"})
        client = httpx.Client(headers={"User-Agent": "PantoneChallenger/1.5"}, timeout=30)
        params = {
            "term": source.query or "new",
            "media": source.options.get("media", "music"),
            "entity": source.options.get("entity", "album"),
            "country": source.options.get("country", "US"),
            "limit": source.max_items,
        }
        try:
            response = client.get(self.API, params=params)
            response.raise_for_status()
            data = response.json().get("results", [])
        except Exception as exc:  # noqa: BLE001
            result.report.update(status="error", error=f"{type(exc).__name__}: {exc}")
            return result
        for index, item in enumerate(data, start=1):
            image_url = item.get("artworkUrl100")
            if not image_url:
                continue
            image_url = image_url.replace("100x100bb", "600x600bb")
            path = self.workdir / "captures" / run_date / source.id / f"itunes-{index:03d}.jpg"
            ok, _ = download_item_image(client, image_url, path)
            if not ok:
                continue
            normalized = {
                "title": item.get("collectionName") or item.get("trackName") or "",
                "url": item.get("collectionViewUrl") or item.get("trackViewUrl") or "",
                "published_at": item.get("releaseDate", ""),
            }
            region = evidence_region_from_item(source, normalized, path, index)
            if region:
                result.regions.append(region)
        result.report["eligible_region_count"] = len(result.regions)
        result.report["status"] = "captured" if result.regions else "no_eligible_region"
        return result
