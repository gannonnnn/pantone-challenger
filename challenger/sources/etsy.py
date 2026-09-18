from __future__ import annotations

import os
from pathlib import Path

import httpx

from challenger.capture.items import download_item_image, evidence_region_from_item
from challenger.sources.base import CollectionResult, SourceAdapter


class EtsyAdapter(SourceAdapter):
    API = "https://openapi.etsy.com/v3/application/listings/active"

    def collect(self, source, run_date):
        result = CollectionResult(source=source, report={"adapter": "etsy_official_api"})
        key = os.getenv(source.api_key_env or "ETSY_API_KEY")
        if not key:
            result.report.update(
                status="skipped_unconfigured",
                missing_env=source.api_key_env or "ETSY_API_KEY",
            )
            return self.finalize_result(result)

        with httpx.Client(
            headers={"x-api-key": key, "User-Agent": "PantoneChallenger/1.6.1"},
            timeout=self.http_timeout_s,
            follow_redirects=True,
        ) as client:
            params = {"limit": source.max_items, "keywords": source.query or "art design fashion"}
            try:
                response = client.get(self.API, params=params, timeout=self.request_timeout())
                response.raise_for_status()
                data = response.json().get("results", [])
            except Exception as exc:  # noqa: BLE001
                result.report.update(status="error", error=f"{type(exc).__name__}: {exc}")
                return self.finalize_result(result)

            for index, listing in enumerate(data, start=1):
                if self.expired(reserve_seconds=1.0):
                    break
                listing_id = listing.get("listing_id")
                if not listing_id:
                    continue
                image_endpoint = f"https://openapi.etsy.com/v3/application/listings/{listing_id}/images"
                try:
                    response = client.get(image_endpoint, timeout=self.request_timeout())
                    response.raise_for_status()
                    images = response.json().get("results", [])
                except Exception:  # noqa: BLE001
                    continue
                if not images:
                    continue
                image_url = images[0].get("url_570xN") or images[0].get("url_fullxfull")
                if not image_url:
                    continue
                path = self.workdir / "captures" / run_date / source.id / f"etsy-{listing_id}.jpg"
                ok, _ = download_item_image(
                    client,
                    image_url,
                    path,
                    timeout_s=self.request_timeout(),
                )
                if not ok:
                    continue
                item = {
                    "title": listing.get("title", ""),
                    "item_id": str(listing_id), "creator_id": str(listing.get("shop_id") or listing.get("user_id") or ""),
                    "identity_verified": bool(listing.get("shop_id") or listing.get("user_id")),
                    "url": f"https://www.etsy.com/listing/{listing_id}",
                    "published_at": str(listing.get("original_creation_timestamp", "")),
                }
                region = evidence_region_from_item(source, item, path, index)
                if region:
                    result.regions.append(region)

        result.report["eligible_region_count"] = len(result.regions)
        result.report["status"] = "captured" if result.regions else "no_eligible_region"
        return self.finalize_result(result)
