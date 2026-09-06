from __future__ import annotations

from pathlib import Path

import httpx

from challenger.capture.items import download_item_image, evidence_region_from_item
from challenger.sources.base import CollectionResult, SourceAdapter


class ClevelandAdapter(SourceAdapter):
    API = "https://openaccess-api.clevelandart.org/api/artworks/"

    def collect(self, source, run_date):
        result = CollectionResult(source=source, report={"adapter": "cleveland_open_access"})
        client = httpx.Client(headers={"User-Agent": "PantoneChallenger/1.5"}, timeout=30)
        try:
            response = client.get(
                self.API,
                params={"q": source.query or "modern", "has_image": 1, "cc0": 1, "limit": max(source.max_items * 3, 20)},
            )
            response.raise_for_status()
            data = response.json().get("data", [])
        except Exception as exc:  # noqa: BLE001
            result.report.update(status="error", error=f"{type(exc).__name__}: {exc}")
            return result
        for index, item in enumerate(data, start=1):
            image_url = (item.get("images") or {}).get("web", {}).get("url")
            if not image_url:
                continue
            path = self.workdir / "captures" / run_date / source.id / f"cleveland-{item.get('id')}.jpg"
            ok, _ = download_item_image(client, image_url, path)
            if not ok:
                continue
            normalized = {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "published_at": "",
            }
            region = evidence_region_from_item(source, normalized, path, index)
            if region:
                result.regions.append(region)
            if len(result.regions) >= source.max_items:
                break
        result.report["eligible_region_count"] = len(result.regions)
        result.report["status"] = "captured" if result.regions else "no_eligible_region"
        return result
