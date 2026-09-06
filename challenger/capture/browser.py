from __future__ import annotations

import asyncio
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import BrowserContext, Page, async_playwright

from challenger.image_quality import (
    content_hash,
    dedupe_regions,
    image_rejection_reason,
    perceptual_hash,
    region_metrics,
    text_looks_like_overlay,
)
from challenger.models import EvidenceRegion, SourceSpec


COMMON_EXCLUDES = [
    "header",
    "nav",
    "footer",
    "[role='navigation']",
    "[role='banner']",
    "[role='dialog']",
    "[aria-modal='true']",
    "[class*='cookie' i]",
    "[id*='cookie' i]",
    "[class*='consent' i]",
    "[id*='consent' i]",
    "[class*='modal' i]",
    "[class*='overlay' i]",
    "[class*='newsletter' i]",
    "[class*='popup' i]",
    "[class*='chat' i]",
    "[class*='logo' i]",
    "[id*='logo' i]",
    "svg[aria-label*='logo' i]",
    "img[alt*='logo' i]",
    "link[rel*='icon']",
]

COMMON_REGION_SELECTORS = [
    "main section",
    "main article",
    "main picture",
    "main img",
    "main [style*='background-image']",
    "article picture",
    "article img",
    "section picture",
    "section img",
    "video[poster]",
]

DISMISS_TEXT = re.compile(
    r"^(accept( all)?|agree|allow all|reject all|decline|close|continue without accepting|only necessary)$",
    re.I,
)


class BrowserCollector:
    def __init__(self, workdir: str | Path, settings: dict):
        self.workdir = Path(workdir)
        self.settings = settings
        self.viewport = settings.get("capture", {}).get("viewport", {"width": 1440, "height": 1200})
        self.timeout_ms = int(settings.get("capture", {}).get("timeout_ms", 45_000))
        self.max_regions = int(settings.get("capture", {}).get("max_regions_per_source", 3))

    async def collect(self, source: SourceSpec, run_date: str) -> tuple[list[EvidenceRegion], dict]:
        attempts = [source.url, *source.fallback_urls]
        attempt_reports = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    viewport=self.viewport,
                    device_scale_factor=1,
                    color_scheme="light",
                    locale="en-US",
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36 "
                        "PantoneChallenger/1.5 research"
                    ),
                )
                for frame_index, url in enumerate(attempts, start=1):
                    regions, report = await self._collect_url(context, source, url, run_date, frame_index)
                    attempt_reports.append(report)
                    if regions:
                        return regions, {"status": "captured", "attempts": attempt_reports, "used_url": url}
                return [], {"status": "no_eligible_region", "attempts": attempt_reports}
            finally:
                await browser.close()

    async def _collect_url(
        self,
        context: BrowserContext,
        source: SourceSpec,
        url: str,
        run_date: str,
        frame_index: int,
    ) -> tuple[list[EvidenceRegion], dict]:
        page = await context.new_page()
        report: dict = {"url": url, "frame_index": frame_index}
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            try:
                await page.wait_for_load_state("networkidle", timeout=min(self.timeout_ms, 8_000))
            except Exception:  # noqa: BLE001
                pass
            await page.wait_for_timeout(1800)
            final_url = page.url
            report["status_code"] = response.status if response else None
            report["final_url"] = final_url
            if not self._host_allowed(final_url, source):
                report["status"] = "unapproved_redirect"
                return [], report
            await self._dismiss_overlays(page)
            await self._hide_structural_elements(page, source)
            await page.wait_for_timeout(700)
            title = await page.title()
            body_text = " ".join((await page.locator("body").inner_text(timeout=5000)).split())[:3000]
            if text_looks_like_overlay(body_text) and len(body_text) < 1000:
                report["status"] = "challenge_or_overlay_page"
                return [], report
            source_dir = self.workdir / "captures" / run_date / source.id
            source_dir.mkdir(parents=True, exist_ok=True)
            full_path = source_dir / f"page-{frame_index:02d}.png"
            await page.screenshot(path=str(full_path), full_page=False)
            candidates = await self._find_candidate_regions(page, source)
            report["candidate_region_count"] = len(candidates)
            saved: list[dict] = []
            for index, candidate in enumerate(candidates[: max(self.max_regions * 4, 12)], start=1):
                loc = page.locator(candidate["selector"]).nth(candidate["nth"])
                path = source_dir / f"region-{source.id}-f{frame_index:02d}-r{index:02d}.png"
                try:
                    await loc.scroll_into_view_if_needed(timeout=4_000)
                    await self._wait_for_visuals(loc)
                    await page.wait_for_timeout(350)
                    await loc.screenshot(path=str(path), timeout=10_000)
                except Exception as exc:  # noqa: BLE001
                    candidate["save_error"] = type(exc).__name__
                    continue
                rejection = image_rejection_reason(path)
                text = candidate.get("text", "")
                if text_looks_like_overlay(text):
                    rejection = "overlay_or_consent_region"
                metrics = region_metrics(path)
                candidate.update(
                    path=str(path),
                    rejection_reason=rejection,
                    eligible=not rejection,
                    content_hash=content_hash(path),
                    perceptual_hash=perceptual_hash(path),
                    entropy=metrics["entropy"],
                    edge_density=metrics["edge_density"],
                )
                if not rejection:
                    saved.append(candidate)
            saved = dedupe_regions(saved)
            regions = [
                EvidenceRegion(
                    source_id=source.id,
                    frame_id=f"{source.id}-f{frame_index:02d}",
                    region_id=f"{source.id}-f{frame_index:02d}-r{i:02d}",
                    selector_hint=str(item.get("selector", "")),
                    region_type=str(item.get("tag", "element")),
                    screenshot_path=str(item["path"]),
                    bbox=tuple(int(round(v)) for v in item["bbox"]),
                    viewport_area_ratio=float(item["viewport_area_ratio"]),
                    image_area_ratio=float(item.get("image_area_ratio", 0.0)),
                    text_density=float(item.get("text_density", 0.0)),
                    entropy=float(item.get("entropy", 0.0)),
                    edge_density=float(item.get("edge_density", 0.0)),
                    confidence=float(item.get("confidence", 0.0)),
                    eligible=True,
                    page_url=final_url,
                    page_title=title,
                    published_at="",
                    rights_mode=source.rights_mode.value,
                    content_hash=str(item.get("content_hash", "")),
                    perceptual_hash=str(item.get("perceptual_hash", "")),
                )
                for i, item in enumerate(saved[: self.max_regions], start=1)
            ]
            report["status"] = "captured" if regions else "captured_but_no_eligible_region"
            report["eligible_region_count"] = len(regions)
            report["rejections"] = [
                {"selector": c.get("selector"), "reason": c.get("rejection_reason")}
                for c in candidates
                if c.get("rejection_reason")
            ]
            return regions, report
        except Exception as exc:  # noqa: BLE001
            report["status"] = "error"
            report["error_type"] = type(exc).__name__
            report["error"] = str(exc)[:500]
            return [], report
        finally:
            await page.close()

    async def _wait_for_visuals(self, locator) -> None:
        """Wait briefly for lazy images inside a candidate region to decode."""

        try:
            await locator.evaluate(
                """
                async el => {
                  const images = [];
                  if (el.matches && el.matches('img')) images.push(el);
                  images.push(...el.querySelectorAll('img'));
                  await Promise.all(images.slice(0, 20).map(async img => {
                    try {
                      if (!img.complete || !img.naturalWidth) {
                        await Promise.race([
                          img.decode ? img.decode() : Promise.resolve(),
                          new Promise(resolve => setTimeout(resolve, 1800))
                        ]);
                      }
                    } catch (_) {}
                  }));
                }
                """
            )
        except Exception:  # noqa: BLE001
            return


    def _host_allowed(self, url: str, source: SourceSpec) -> bool:
        host = (urlparse(url).hostname or "").lower()
        allowed = source.allowed_hosts or [(urlparse(source.url).hostname or "").lower()]
        return any(host == h or host.endswith(f".{h}") for h in allowed if h)

    async def _dismiss_overlays(self, page: Page) -> None:
        for frame in page.frames:
            try:
                buttons = frame.get_by_role("button")
                count = min(await buttons.count(), 80)
                for i in range(count):
                    button = buttons.nth(i)
                    try:
                        text = " ".join((await button.inner_text(timeout=500)).split())
                        if DISMISS_TEXT.match(text):
                            await button.click(timeout=800)
                            await page.wait_for_timeout(250)
                    except Exception:  # noqa: BLE001
                        continue
            except Exception:  # noqa: BLE001
                continue

    async def _hide_structural_elements(self, page: Page, source: SourceSpec) -> None:
        selectors = COMMON_EXCLUDES + list(source.exclude_selectors)
        await page.evaluate(
            """
            (selectors) => {
              for (const selector of selectors) {
                let nodes = [];
                try { nodes = [...document.querySelectorAll(selector)]; } catch (_) { continue; }
                for (const node of nodes) {
                  node.dataset.pcHidden = 'true';
                  node.style.setProperty('visibility', 'hidden', 'important');
                }
              }
            }
            """,
            selectors,
        )

    async def _find_candidate_regions(self, page: Page, source: SourceSpec) -> list[dict]:
        selectors = list(source.include_selectors) or COMMON_REGION_SELECTORS
        viewport_area = float(self.viewport["width"] * self.viewport["height"])
        candidates: list[dict] = []
        for selector in selectors:
            try:
                loc = page.locator(selector)
                count = min(await loc.count(), 60)
            except Exception:  # noqa: BLE001
                continue
            for nth in range(count):
                item = loc.nth(nth)
                try:
                    if not await item.is_visible():
                        continue
                    box = await item.bounding_box()
                    if not box:
                        continue
                    w, h = box["width"], box["height"]
                    if w < 280 or h < 180:
                        continue
                    area_ratio = (w * h) / viewport_area
                    if area_ratio < 0.04 or area_ratio > 1.25:
                        continue
                    text = " ".join((await item.inner_text(timeout=500)).split())[:2000]
                    text_density = len(text) / max(1.0, w * h / 1000)
                    tag = await item.evaluate("el => el.tagName.toLowerCase()")
                    image_area_ratio = await item.evaluate(
                        """
                        el => {
                          const r = el.getBoundingClientRect();
                          const a = Math.max(1, r.width * r.height);
                          let total = 0;
                          if (el.matches('img, picture, video, canvas')) total += a;
                          for (const img of el.querySelectorAll('img, picture, video, canvas')) {
                            const b = img.getBoundingClientRect();
                            total += Math.max(0, b.width * b.height);
                          }
                          const bg = getComputedStyle(el).backgroundImage;
                          if (bg && bg !== 'none') total += a;
                          return Math.min(1, total / a);
                        }
                        """
                    )
                    confidence = (
                        0.35
                        + min(area_ratio, 0.6) * 0.45
                        + min(float(image_area_ratio), 1.0) * 0.30
                        - min(text_density / 18.0, 0.25)
                    )
                    if text_looks_like_overlay(text):
                        confidence -= 0.8
                    if confidence < 0.50:
                        continue
                    candidates.append(
                        {
                            "selector": selector,
                            "nth": nth,
                            "bbox": [box["x"], box["y"], w, h],
                            "area": w * h,
                            "viewport_area_ratio": area_ratio,
                            "image_area_ratio": float(image_area_ratio),
                            "text_density": text_density,
                            "text": text,
                            "tag": tag,
                            "confidence": max(0.0, min(1.0, confidence)),
                        }
                    )
                except Exception:  # noqa: BLE001
                    continue
        return sorted(candidates, key=lambda x: (x["confidence"], x["area"]), reverse=True)


def collect_browser_source(source: SourceSpec, run_date: str, workdir: str | Path, settings: dict):
    return asyncio.run(BrowserCollector(workdir, settings).collect(source, run_date))
