from __future__ import annotations

import random
from pathlib import Path

import httpx

from challenger.capture.items import download_item_image, evidence_region_from_item
from challenger.sources.base import CollectionResult, SourceAdapter


class MetAdapter(SourceAdapter):
    SEARCH = "https://collectionapi.metmuseum.org/public/collection/v1/search"
    OBJECT = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{id}"

    def collect(self, source, run_date):
        result = CollectionResult(source=source, report={"adapter": "met_open_access"})
        query = source.query or "contemporary art"
        with httpx.Client(
            headers={"User-Agent": "PantoneChallenger/1.6.1"},
            timeout=self.http_timeout_s,
            follow_redirects=True,
        ) as client:
            try:
                response = client.get(
                    self.SEARCH,
                    params={"q": query, "hasImages": "true"},
                    timeout=self.request_timeout(),
                )
                response.raise_for_status()
                ids = response.json().get("objectIDs") or []
            except Exception as exc:  # noqa: BLE001
                result.report.update(status="error", error=f"{type(exc).__name__}: {exc}")
                return self.finalize_result(result)

            rng = random.Random(f"{run_date}:{source.id}")
            ids = list(ids)
            rng.shuffle(ids)
            scan_limit = max(source.max_items * 2, 12)
            for index, object_id in enumerate(ids[:scan_limit], start=1):
                if self.expired(reserve_seconds=1.0):
                    break
                try:
                    response = client.get(
                        self.OBJECT.format(id=object_id),
                        timeout=self.request_timeout(),
                    )
                    response.raise_for_status()
                    obj = response.json()
                except Exception:  # noqa: BLE001
                    continue
                if not obj.get("isPublicDomain") or not obj.get("primaryImageSmall"):
                    continue
                path = self.workdir / "captures" / run_date / source.id / f"met-{object_id}.jpg"
                ok, _ = download_item_image(
                    client,
                    obj["primaryImageSmall"],
                    path,
                    timeout_s=self.request_timeout(),
                )
                if not ok:
                    continue
                item = {
                    "title": obj.get("title", ""),
                    "url": obj.get("objectURL", ""),
                    "published_at": "",
                }
                region = evidence_region_from_item(source, item, path, index)
                if region:
                    result.regions.append(region)
                if len(result.regions) >= source.max_items:
                    break

        result.report["eligible_region_count"] = len(result.regions)
        result.report["status"] = "captured" if result.regions else "no_eligible_region"
        return self.finalize_result(result)
