from __future__ import annotations

from pathlib import Path

import httpx

from challenger.capture.items import download_item_image, evidence_region_from_item
from challenger.sources.base import CollectionResult, SourceAdapter


class ArtInstituteChicagoAdapter(SourceAdapter):
    SEARCH = "https://api.artic.edu/api/v1/artworks/search"

    def collect(self, source, run_date):
        result = CollectionResult(source=source, report={"adapter": "artic_open_access"})
        client = httpx.Client(headers={"User-Agent": "PantoneChallenger/1.5"}, timeout=30)
        fields = "id,title,image_id,is_public_domain,date_display,artist_display"
        try:
            response = client.get(
                self.SEARCH,
                params={"q": source.query or "contemporary", "limit": max(source.max_items * 3, 20), "fields": fields},
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            result.report.update(status="error", error=f"{type(exc).__name__}: {exc}")
            return result
        iiif = payload.get("config", {}).get("iiif_url", "https://www.artic.edu/iiif/2")
        index = 0
        for item in payload.get("data", []):
            if not item.get("is_public_domain") or not item.get("image_id"):
                continue
            index += 1
            image_url = f"{iiif}/{item['image_id']}/full/843,/0/default.jpg"
            path = self.workdir / "captures" / run_date / source.id / f"artic-{item['id']}.jpg"
            ok, _ = download_item_image(client, image_url, path)
            if not ok:
                continue
            normalized = {
                "title": item.get("title", ""),
                "url": f"https://www.artic.edu/artworks/{item['id']}",
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
