from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

import feedparser
import httpx
from bs4 import BeautifulSoup

from challenger.capture.items import download_item_image, evidence_region_from_item
from challenger.sources.base import CollectionResult, SourceAdapter


class RSSAdapter(SourceAdapter):
    def collect(self, source, run_date):
        result = CollectionResult(source=source, report={"adapter": "rss"})
        with httpx.Client(
            headers={"User-Agent": "PantoneChallenger/1.6.1"},
            timeout=self.http_timeout_s,
            follow_redirects=True,
        ) as client:
            try:
                response = client.get(source.url, timeout=self.request_timeout())
                response.raise_for_status()
                feed = feedparser.parse(response.content)
            except Exception as exc:  # noqa: BLE001
                result.report.update(status="error", error=f"{type(exc).__name__}: {exc}")
                return self.finalize_result(result)

            result.report["entries"] = len(feed.entries)
            seen: set[str] = set()
            for index, entry in enumerate(feed.entries[: source.max_items], start=1):
                if self.expired(reserve_seconds=1.0):
                    break
                images: list[str] = []
                for enclosure in entry.get("enclosures", []):
                    href = enclosure.get("href") or enclosure.get("url")
                    if href:
                        images.append(href)
                html = entry.get("content", [{}])[0].get("value", "") or entry.get("summary", "")
                soup = BeautifulSoup(html, "html.parser")
                images.extend(img.get("src") for img in soup.find_all("img") if img.get("src"))
                for image_url in images:
                    if self.expired(reserve_seconds=1.0):
                        break
                    image_url = urljoin(entry.get("link", source.url), image_url)
                    if image_url in seen:
                        continue
                    seen.add(image_url)
                    ext = Path(image_url.split("?")[0]).suffix or ".jpg"
                    path = self.workdir / "captures" / run_date / source.id / f"item-{index:03d}{ext}"
                    ok, reason = download_item_image(
                        client,
                        image_url,
                        path,
                        timeout_s=self.request_timeout(),
                    )
                    if not ok:
                        result.report.setdefault("rejections", []).append(
                            {"image": image_url, "reason": reason}
                        )
                        continue
                    item = {
                        "title": entry.get("title", ""),
                        "url": entry.get("link", ""),
                        "published_at": entry.get("published", entry.get("updated", "")),
                    }
                    region = evidence_region_from_item(source, item, path, index)
                    if region:
                        result.regions.append(region)
                        break
                if len(result.regions) >= source.max_items:
                    break

        result.report["eligible_region_count"] = len(result.regions)
        result.report["status"] = "captured" if result.regions else "no_eligible_region"
        return self.finalize_result(result)
