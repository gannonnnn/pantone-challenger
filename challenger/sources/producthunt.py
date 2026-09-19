from __future__ import annotations

import os
from pathlib import Path

import httpx

from challenger.capture.items import download_item_image, evidence_region_from_item
from challenger.sources.base import CollectionResult, SourceAdapter


class ProductHuntAdapter(SourceAdapter):
    API = "https://api.producthunt.com/v2/api/graphql"

    def collect(self, source, run_date):
        result = CollectionResult(source=source, report={"adapter": "product_hunt_graphql"})
        token = os.getenv(source.token_env or "PRODUCT_HUNT_TOKEN")
        if not token:
            result.report.update(
                status="skipped_unconfigured",
                missing_env=source.token_env or "PRODUCT_HUNT_TOKEN",
            )
            return self.finalize_result(result)
        query = """
        query Posts($first: Int!) {
          posts(first: $first, order: NEWEST) {
            edges { node { id name tagline url thumbnail { url } createdAt } }
          }
        }
        """
        with httpx.Client(
            headers={"Authorization": f"Bearer {token}", "User-Agent": "PantoneChallenger/1.6.1"},
            timeout=self.http_timeout_s,
            follow_redirects=True,
        ) as client:
            try:
                response = client.post(
                    self.API,
                    json={"query": query, "variables": {"first": source.max_items}},
                    timeout=self.request_timeout(),
                )
                response.raise_for_status()
                edges = response.json().get("data", {}).get("posts", {}).get("edges", [])
            except Exception as exc:  # noqa: BLE001
                result.report.update(status="error", error=f"{type(exc).__name__}: {exc}")
                return self.finalize_result(result)

            for index, edge in enumerate(edges, start=1):
                if self.expired(reserve_seconds=1.0):
                    break
                item = edge.get("node", {})
                image_url = (item.get("thumbnail") or {}).get("url")
                if not image_url:
                    continue
                path = self.workdir / "captures" / run_date / source.id / f"producthunt-{item.get('id', index)}.jpg"
                ok, _ = download_item_image(
                    client,
                    image_url,
                    path,
                    timeout_s=self.request_timeout(),
                )
                if not ok:
                    continue
                normalized = {
                    "title": item.get("name", ""),
                    "url": item.get("url", ""),
                    "published_at": item.get("createdAt", ""),
                }
                region = evidence_region_from_item(source, normalized, path, index)
                if region:
                    result.regions.append(region)

        result.report["eligible_region_count"] = len(result.regions)
        result.report["status"] = "captured" if result.regions else "no_eligible_region"
        return self.finalize_result(result)
