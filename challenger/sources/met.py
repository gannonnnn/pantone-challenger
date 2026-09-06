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
        client = httpx.Client(headers={"User-Agent": "PantoneChallenger/1.5"}, timeout=30)
        query = source.query or "contemporary art"
        try:
            response = client.get(self.SEARCH, params={"q": query, "hasImages": "true"})
            response.raise_for_status()
            ids = response.json().get("objectIDs") or []
        except Exception as exc:  # noqa: BLE001
            result.report.update(status="error", error=f"{type(exc).__name__}: {exc}")
            return result
        # Deterministic daily rotation avoids always sampling the first objects.
        rng = random.Random(f"{run_date}:{source.id}")
        ids = list(ids)
        rng.shuffle(ids)
        for index, object_id in enumerate(ids[: max(source.max_items * 4, 20)], start=1):
            try:
                obj = client.get(self.OBJECT.format(id=object_id)).json()
            except Exception:  # noqa: BLE001
                continue
            if not obj.get("isPublicDomain") or not obj.get("primaryImageSmall"):
                continue
            path = self.workdir / "captures" / run_date / source.id / f"met-{object_id}.jpg"
            ok, _ = download_item_image(client, obj["primaryImageSmall"], path)
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
        return result
