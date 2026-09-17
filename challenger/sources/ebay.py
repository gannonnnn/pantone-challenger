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
            result.report.update(
                status="skipped_unconfigured",
                missing_env=source.token_env or "EBAY_OAUTH_TOKEN",
            )
            return self.finalize_result(result)

        with httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                "User-Agent": "PantoneChallenger/1.6.0",
            },
            timeout=self.http_timeout_s,
            follow_redirects=True,
        ) as client:
            try:
                response = client.get(
                    self.API,
                    params={
                        "q": source.query or "design art fashion",
                        "sort": "newlyListed",
                        "limit": source.max_items,
                    },
                    timeout=self.request_timeout(),
                )
                response.raise_for_status()
                data = response.json().get("itemSummaries", [])
            except Exception as exc:  # noqa: BLE001
                result.report.update(status="error", error=f"{type(exc).__name__}: {exc}")
                return self.finalize_result(result)

            for index, item in enumerate(data, start=1):
                if self.expired(reserve_seconds=1.0):
                    break
                image_url = (item.get("image") or {}).get("imageUrl")
                if not image_url:
                    continue
                path = self.workdir / "captures" / run_date / source.id / f"ebay-{index:03d}.jpg"
                ok, _ = download_item_image(
                    client,
                    image_url,
                    path,
                    timeout_s=self.request_timeout(),
                )
                if not ok:
                    continue
                normalized = {
                    "title": item.get("title", ""),
                    "item_id": item.get("itemId", ""), "creator_id": (item.get("seller") or {}).get("username", ""),
                    "identity_verified": bool((item.get("seller") or {}).get("username")),
                    "url": item.get("itemWebUrl", ""),
                    "published_at": item.get("itemCreationDate", ""),
                }
                region = evidence_region_from_item(source, normalized, path, index)
                if region:
                    result.regions.append(region)

        result.report["eligible_region_count"] = len(result.regions)
        result.report["status"] = "captured" if result.regions else "no_eligible_region"
        return self.finalize_result(result)
