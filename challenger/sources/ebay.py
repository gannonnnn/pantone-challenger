from __future__ import annotations

import os
from pathlib import Path

import httpx

from challenger.capture.items import download_item_image, evidence_region_from_item
from challenger.sources.base import CollectionResult, SourceAdapter


class EbayBrowseAdapter(SourceAdapter):
    API = "https://api.ebay.com/buy/browse/v1/item_summary/search"

    def collect(self, source, run_date):
        result = CollectionResult(source=source, report={"adapter": "ebay_browse_api"})
        token = os.getenv(source.token_env or "EBAY_OAUTH_TOKEN")
        if not token:
            result.report.update(status="skipped_unconfigured", missing_env=source.token_env or "EBAY_OAUTH_TOKEN")
            return result
        client = httpx.Client(
            headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}, timeout=30
        )
        try:
            response = client.get(
                self.API,
                params={"q": source.query or "design art fashion", "sort": "newlyListed", "limit": source.max_items},
            )
            response.raise_for_status()
            data = response.json().get("itemSummaries", [])
        except Exception as exc:  # noqa: BLE001
            result.report.update(status="error", error=f"{type(exc).__name__}: {exc}")
            return result
        for index, item in enumerate(data, start=1):
            image_url = (item.get("image") or {}).get("imageUrl")
            if not image_url:
                continue
            path = self.workdir / "captures" / run_date / source.id / f"ebay-{index:03d}.jpg"
            ok, _ = download_item_image(client, image_url, path)
            if not ok:
                continue
            normalized = {
                "title": item.get("title", ""),
                "url": item.get("itemWebUrl", ""),
                "published_at": item.get("itemCreationDate", ""),
            }
            region = evidence_region_from_item(source, normalized, path, index)
            if region:
                result.regions.append(region)
        result.report["eligible_region_count"] = len(result.regions)
        result.report["status"] = "captured" if result.regions else "no_eligible_region"
        return result
