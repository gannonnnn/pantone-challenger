from __future__ import annotations

import asyncio
import os
import re
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from playwright.async_api import Browser, BrowserContext, Page, Route, async_playwright

from challenger.image_quality import (
    content_hash,
    dedupe_regions,
    image_rejection_reason,
    perceptual_hash,
    region_metrics,
    text_looks_like_overlay,
)
from challenger.models import EvidenceRegion, SourceSpec
from challenger.sources.base import CollectionResult


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

TRACKER_MARKERS = (
    "google-analytics.com",
    "googletagmanager.com",
    "doubleclick.net",
    "connect.facebook.net",
    "hotjar.com",
    "clarity.ms",
    "segment.io",
    "segment.com",
    "newrelic.com",
    "nr-data.net",
)

ProgressCallback = Callable[[CollectionResult, float], None]
HeartbeatCallback = Callable[[int, int, int, float], None]


class BrowserCollector:
    """Collect webpage evidence with one shared Chromium process.

    A source gets an isolated browser context, but all sources share the same
    Chromium process. Every source also has an absolute wall-clock timeout, so
    a difficult site cannot hold the whole daily run hostage.
    """

    def __init__(self, workdir: str | Path, settings: dict):
        self.workdir = Path(workdir)
        self.settings = settings
        capture = settings.get("capture", {})
        self.viewport = capture.get("viewport", {"width": 1440, "height": 1200})
        self.navigation_timeout_ms = int(capture.get("navigation_timeout_ms", 18_000))
        self.element_timeout_ms = int(capture.get("element_timeout_ms", 4_000))
        self.screenshot_timeout_ms = int(capture.get("screenshot_timeout_ms", 6_000))
        self.source_timeout_s = float(capture.get("browser_source_timeout_s", 55))
        self.collection_budget_s = float(capture.get("collection_budget_s", 1_200))
        self.browser_workers = max(1, int(capture.get("browser_workers", capture.get("workers", 5))))
        self.heartbeat_s = max(5.0, float(capture.get("heartbeat_seconds", 20)))
        self.max_regions = max(1, int(capture.get("max_regions_per_source", 3)))
        self.max_candidate_attempts = max(
            self.max_regions,
            int(capture.get("max_candidate_regions", max(self.max_regions * 2, 6))),
        )
        self.max_fallback_urls = max(0, int(capture.get("max_fallback_urls", 1)))
        self.network_idle_timeout_ms = int(capture.get("network_idle_timeout_ms", 3_000))
        self.post_load_wait_ms = int(capture.get("post_load_wait_ms", 700))
        self.visual_wait_ms = int(capture.get("visual_wait_ms", 1_000))
        self.overlay_timeout_s = float(capture.get("overlay_timeout_s", 3.0))
        self.max_nodes_per_selector = max(8, int(capture.get("max_nodes_per_selector", 28)))

    async def collect(self, source: SourceSpec, run_date: str) -> tuple[list[EvidenceRegion], dict]:
        results = await self.collect_many([source], run_date)
        result = results[0]
        return result.regions, result.report

    async def collect_many(
        self,
        sources: list[SourceSpec],
        run_date: str,
        *,
        progress_callback: ProgressCallback | None = None,
        heartbeat_callback: HeartbeatCallback | None = None,
    ) -> list[CollectionResult]:
        if not sources:
            return []

        loop = asyncio.get_running_loop()
        batch_started = loop.time()
        global_deadline = batch_started + self.collection_budget_s
        semaphore = asyncio.Semaphore(self.browser_workers)
        results: list[CollectionResult] = []

        async with async_playwright() as playwright:
            launch_options: dict[str, Any] = {
                "headless": True,
                "args": [
                    "--disable-background-networking",
                    "--disable-dev-shm-usage",
                    "--disable-extensions",
                    "--mute-audio",
                ],
            }
            executable_path = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", "").strip()
            if executable_path:
                launch_options["executable_path"] = executable_path
            browser = await playwright.chromium.launch(**launch_options)
            try:
                async def run_source(source: SourceSpec) -> CollectionResult:
                    async with semaphore:
                        started = time.monotonic()
                        remaining = global_deadline - loop.time()
                        if remaining <= 0:
                            result = CollectionResult(
                                source=source,
                                report={
                                    "status": "skipped_collection_budget",
                                    "error": "The shared browser collection budget was exhausted before this source started.",
                                },
                            )
                        else:
                            timeout = max(0.05, min(self.source_timeout_s, remaining))
                            try:
                                regions, report = await asyncio.wait_for(
                                    self._collect_with_browser(browser, source, run_date),
                                    timeout=timeout,
                                )
                                result = CollectionResult(source=source, regions=regions, report=report)
                            except asyncio.TimeoutError:
                                result = CollectionResult(
                                    source=source,
                                    report={
                                        "status": "source_timeout",
                                        "timeout_seconds": round(timeout, 2),
                                        "error": "The source exceeded its wall-clock budget and was skipped.",
                                    },
                                )
                            except asyncio.CancelledError:
                                raise
                            except Exception as exc:  # noqa: BLE001
                                result = CollectionResult(
                                    source=source,
                                    report={
                                        "status": "unhandled_error",
                                        "error": f"{type(exc).__name__}: {exc}"[:500],
                                    },
                                )
                        duration = time.monotonic() - started
                        result.report.setdefault("duration_seconds", round(duration, 3))
                        result.report.setdefault("browser_shared", True)
                        if progress_callback:
                            progress_callback(result, duration)
                        return result

                tasks = {
                    asyncio.create_task(run_source(source), name=f"collect:{source.id}"): source
                    for source in sources
                }
                pending = set(tasks)
                while pending:
                    if loop.time() >= global_deadline:
                        for task in pending:
                            task.cancel()
                        await asyncio.gather(*pending, return_exceptions=True)
                        for task in pending:
                            source = tasks[task]
                            result = CollectionResult(
                                source=source,
                                report={
                                    "status": "skipped_collection_budget",
                                    "error": "The shared browser collection budget expired.",
                                    "duration_seconds": round(loop.time() - batch_started, 3),
                                    "browser_shared": True,
                                },
                            )
                            if progress_callback:
                                progress_callback(result, float(result.report["duration_seconds"]))
                            results.append(result)
                        pending.clear()
                        break

                    wait_for = min(self.heartbeat_s, max(0.1, global_deadline - loop.time()))
                    done, pending = await asyncio.wait(
                        pending,
                        timeout=wait_for,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if not done:
                        if heartbeat_callback:
                            active = min(self.browser_workers, len(pending))
                            queued = max(0, len(pending) - active)
                            heartbeat_callback(len(results), active, queued, loop.time() - batch_started)
                        continue
                    for task in done:
                        try:
                            results.append(task.result())
                        except asyncio.CancelledError:
                            source = tasks[task]
                            results.append(
                                CollectionResult(
                                    source=source,
                                    report={"status": "cancelled", "browser_shared": True},
                                )
                            )
            finally:
                await browser.close()

        return sorted(results, key=lambda item: item.source.id)

    async def _collect_with_browser(
        self,
        browser: Browser,
        source: SourceSpec,
        run_date: str,
    ) -> tuple[list[EvidenceRegion], dict]:
        attempts = [source.url, *source.fallback_urls[: self.max_fallback_urls]]
        attempt_reports: list[dict[str, Any]] = []
        context = await browser.new_context(
            viewport=self.viewport,
            device_scale_factor=1,
            color_scheme="light",
            reduced_motion="reduce",
            locale="en-US",
            ignore_https_errors=True,
            service_workers="block",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36 "
                "PantoneChallenger/1.6.0 research"
            ),
        )
        context.set_default_timeout(self.element_timeout_ms)
        context.set_default_navigation_timeout(self.navigation_timeout_ms)
        await context.route("**/*", self._route_request)
        try:
            for frame_index, url in enumerate(attempts, start=1):
                regions, report = await self._collect_url(
                    context,
                    source,
                    url,
                    run_date,
                    frame_index,
                )
                attempt_reports.append(report)
                if regions:
                    return regions, {
                        "status": "captured",
                        "attempts": attempt_reports,
                        "used_url": url,
                        "fallback_used": frame_index > 1,
                    }
            return [], {"status": "no_eligible_region", "attempts": attempt_reports}
        finally:
            await context.close()

    async def _route_request(self, route: Route) -> None:
        request = route.request
        url = request.url.lower()
        if request.resource_type in {"font", "media"} or any(marker in url for marker in TRACKER_MARKERS):
            await route.abort()
            return
        await route.continue_()

    async def _collect_url(
        self,
        context: BrowserContext,
        source: SourceSpec,
        url: str,
        run_date: str,
        frame_index: int,
    ) -> tuple[list[EvidenceRegion], dict]:
        page = await context.new_page()
        report: dict[str, Any] = {"url": url, "frame_index": frame_index}
        try:
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.navigation_timeout_ms,
            )
            try:
                await page.wait_for_load_state("networkidle", timeout=self.network_idle_timeout_ms)
            except Exception:  # noqa: BLE001
                pass
            await page.wait_for_timeout(self.post_load_wait_ms)
            final_url = page.url
            report["status_code"] = response.status if response else None
            report["final_url"] = final_url
            if not self._host_allowed(final_url, source):
                report["status"] = "unapproved_redirect"
                return [], report

            await self._dismiss_overlays(page)
            await self._hide_structural_elements(page, source)
            await page.wait_for_timeout(250)
            title = await page.title()
            try:
                body_text = " ".join(
                    (await page.locator("body").inner_text(timeout=2_500)).split()
                )[:3000]
            except Exception:  # noqa: BLE001
                body_text = ""
            if text_looks_like_overlay(body_text) and len(body_text) < 1000:
                report["status"] = "challenge_or_overlay_page"
                return [], report

            source_dir = self.workdir / "captures" / run_date / source.id
            source_dir.mkdir(parents=True, exist_ok=True)
            full_path = source_dir / f"page-{frame_index:02d}.png"
            try:
                await page.screenshot(
                    path=str(full_path),
                    full_page=False,
                    timeout=self.screenshot_timeout_ms,
                    animations="disabled",
                )
            except Exception as exc:  # noqa: BLE001
                report["page_screenshot_error"] = type(exc).__name__

            raw_candidates = await self._find_candidate_regions(page, source)
            candidates = self._dedupe_candidate_boxes(raw_candidates)
            report["candidate_region_count_raw"] = len(raw_candidates)
            report["candidate_region_count"] = len(candidates)
            saved: list[dict[str, Any]] = []
            attempted: list[dict[str, Any]] = []
            for index, candidate in enumerate(candidates[: self.max_candidate_attempts], start=1):
                loc = page.locator(candidate["selector"]).nth(candidate["nth"])
                path = source_dir / f"region-{source.id}-f{frame_index:02d}-r{index:02d}.png"
                try:
                    await loc.scroll_into_view_if_needed(timeout=2_000)
                    await self._wait_for_visuals(loc)
                    await page.wait_for_timeout(120)
                    await loc.screenshot(
                        path=str(path),
                        timeout=self.screenshot_timeout_ms,
                        animations="disabled",
                    )
                except Exception as exc:  # noqa: BLE001
                    candidate["save_error"] = type(exc).__name__
                    candidate["rejection_reason"] = "region_screenshot_error"
                    attempted.append(candidate)
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
                attempted.append(candidate)
                if not rejection:
                    saved.append(candidate)
                if len(saved) >= self.max_regions:
                    break

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
            report["screenshot_attempts"] = len(attempted)
            report["rejections"] = [
                {
                    "selector": candidate.get("selector"),
                    "reason": candidate.get("rejection_reason"),
                }
                for candidate in attempted
                if candidate.get("rejection_reason")
            ]
            return regions, report
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            report["status"] = "error"
            report["error_type"] = type(exc).__name__
            report["error"] = str(exc)[:500]
            return [], report
        finally:
            await page.close()

    async def _wait_for_visuals(self, locator) -> None:
        async def decode() -> None:
            await locator.evaluate(
                """
                async el => {
                  const images = [];
                  if (el.matches && el.matches('img')) images.push(el);
                  images.push(...el.querySelectorAll('img'));
                  await Promise.all(images.slice(0, 8).map(async img => {
                    try {
                      if (!img.complete || !img.naturalWidth) {
                        await Promise.race([
                          img.decode ? img.decode() : Promise.resolve(),
                          new Promise(resolve => setTimeout(resolve, 900))
                        ]);
                      }
                    } catch (_) {}
                  }));
                }
                """
            )

        try:
            await asyncio.wait_for(decode(), timeout=max(0.5, self.visual_wait_ms / 1000))
        except Exception:  # noqa: BLE001
            return

    def _host_allowed(self, url: str, source: SourceSpec) -> bool:
        host = (urlparse(url).hostname or "").lower()
        allowed = source.allowed_hosts or [(urlparse(source.url).hostname or "").lower()]
        return any(host == allowed_host or host.endswith(f".{allowed_host}") for allowed_host in allowed if allowed_host)

    async def _dismiss_overlays(self, page: Page) -> None:
        async def dismiss() -> None:
            try:
                await page.keyboard.press("Escape")
            except Exception:  # noqa: BLE001
                pass
            clicked = 0
            for frame in page.frames:
                if clicked >= 4:
                    break
                try:
                    buttons = frame.get_by_role("button")
                    count = min(await buttons.count(), 50)
                    texts = await buttons.all_inner_texts()
                    for index, text in enumerate(texts[:count]):
                        if clicked >= 4:
                            break
                        normalized = " ".join(text.split())
                        if not DISMISS_TEXT.match(normalized):
                            continue
                        try:
                            await buttons.nth(index).click(timeout=700)
                            clicked += 1
                            await page.wait_for_timeout(120)
                        except Exception:  # noqa: BLE001
                            continue
                except Exception:  # noqa: BLE001
                    continue

        try:
            await asyncio.wait_for(dismiss(), timeout=self.overlay_timeout_s)
        except Exception:  # noqa: BLE001
            return

    async def _hide_structural_elements(self, page: Page, source: SourceSpec) -> None:
        selectors = COMMON_EXCLUDES + list(source.exclude_selectors)
        try:
            await page.evaluate(
                """
                (selectors) => {
                  for (const selector of selectors) {
                    let nodes = [];
                    try { nodes = [...document.querySelectorAll(selector)]; } catch (_) { continue; }
                    for (const node of nodes) {
                      node.dataset.pcHidden = 'true';
                      node.style.setProperty('visibility', 'hidden', 'important');
                      node.style.setProperty('pointer-events', 'none', 'important');
                    }
                  }
                }
                """,
                selectors,
            )
        except Exception:  # noqa: BLE001
            return

    async def _find_candidate_regions(self, page: Page, source: SourceSpec) -> list[dict[str, Any]]:
        selectors = list(source.include_selectors) or COMMON_REGION_SELECTORS
        viewport_area = float(self.viewport["width"] * self.viewport["height"])
        payload = await page.evaluate(
            """
            ({selectors, maxNodes}) => {
              const out = [];
              for (const selector of selectors) {
                let nodes = [];
                try { nodes = [...document.querySelectorAll(selector)].slice(0, maxNodes); }
                catch (_) { continue; }
                nodes.forEach((el, nth) => {
                  const style = getComputedStyle(el);
                  const box = el.getBoundingClientRect();
                  if (!box.width || !box.height || style.display === 'none' ||
                      style.visibility === 'hidden' || Number(style.opacity || 1) < 0.05 ||
                      el.getClientRects().length === 0) return;
                  const area = Math.max(1, box.width * box.height);
                  let imageArea = 0;
                  if (el.matches('img, picture, video, canvas')) imageArea += area;
                  for (const image of el.querySelectorAll('img, picture, video, canvas')) {
                    const b = image.getBoundingClientRect();
                    imageArea += Math.max(0, b.width * b.height);
                  }
                  const bg = style.backgroundImage;
                  if (bg && bg !== 'none') imageArea += area;
                  out.push({
                    selector,
                    nth,
                    bbox: [box.x, box.y, box.width, box.height],
                    text: String(el.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 2000),
                    tag: String(el.tagName || 'element').toLowerCase(),
                    imageAreaRatio: Math.min(1, imageArea / area),
                  });
                });
              }
              return out;
            }
            """,
            {"selectors": selectors, "maxNodes": self.max_nodes_per_selector},
        )

        candidates: list[dict[str, Any]] = []
        for raw in payload:
            x, y, width, height = (float(value) for value in raw["bbox"])
            if width < 280 or height < 180:
                continue
            area = width * height
            area_ratio = area / viewport_area
            if area_ratio < 0.04 or area_ratio > 1.25:
                continue
            text = str(raw.get("text", ""))
            text_density = len(text) / max(1.0, area / 1000)
            image_area_ratio = float(raw.get("imageAreaRatio", 0.0))
            confidence = (
                0.35
                + min(area_ratio, 0.6) * 0.45
                + min(image_area_ratio, 1.0) * 0.30
                - min(text_density / 18.0, 0.25)
            )
            if text_looks_like_overlay(text):
                confidence -= 0.8
            if confidence < 0.50:
                continue
            candidates.append(
                {
                    "selector": str(raw["selector"]),
                    "nth": int(raw["nth"]),
                    "bbox": [x, y, width, height],
                    "area": area,
                    "viewport_area_ratio": area_ratio,
                    "image_area_ratio": image_area_ratio,
                    "text_density": text_density,
                    "text": text,
                    "tag": str(raw.get("tag", "element")),
                    "confidence": max(0.0, min(1.0, confidence)),
                }
            )
        return sorted(candidates, key=lambda item: (item["confidence"], item["area"]), reverse=True)

    @staticmethod
    def _dedupe_candidate_boxes(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        accepted: list[dict[str, Any]] = []
        for candidate in candidates:
            if any(_boxes_overlap(candidate["bbox"], other["bbox"]) for other in accepted):
                continue
            accepted.append(candidate)
        return accepted


def _boxes_overlap(a: list[float], b: list[float]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    left = max(ax, bx)
    top = max(ay, by)
    right = min(ax + aw, bx + bw)
    bottom = min(ay + ah, by + bh)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    if intersection <= 0:
        return False
    area_a = max(1.0, aw * ah)
    area_b = max(1.0, bw * bh)
    union = area_a + area_b - intersection
    iou = intersection / max(1.0, union)
    containment = intersection / min(area_a, area_b)
    return iou >= 0.80 or containment >= 0.90


def collect_browser_sources(
    sources: list[SourceSpec],
    run_date: str,
    workdir: str | Path,
    settings: dict,
    *,
    progress_callback: ProgressCallback | None = None,
    heartbeat_callback: HeartbeatCallback | None = None,
) -> list[CollectionResult]:
    return asyncio.run(
        BrowserCollector(workdir, settings).collect_many(
            sources,
            run_date,
            progress_callback=progress_callback,
            heartbeat_callback=heartbeat_callback,
        )
    )


def collect_browser_source(source: SourceSpec, run_date: str, workdir: str | Path, settings: dict):
    results = collect_browser_sources([source], run_date, workdir, settings)
    result = results[0]
    return result.regions, result.report
