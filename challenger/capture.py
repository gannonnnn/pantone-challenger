from __future__ import annotations

import asyncio
import hashlib
import json
import time
from pathlib import Path

from .config import Settings
from .dates import iso_now
from .models import CaptureFrame, CaptureRecord, EvidenceRegion, Source

BLOCK_SIGNATURES = (
    "access denied",
    "verify you are human",
    "unusual traffic",
    "are you a robot",
    "security check",
    "captcha",
    "request blocked",
    "temporarily blocked",
)

COOKIE_BUTTON_LABELS = (
    "Accept all",
    "Accept All",
    "Allow all",
    "I agree",
    "Agree",
    "Accept",
    "Got it",
    "Continue",
)

DEFAULT_REGION_SELECTORS = (
    "main section",
    "main article",
    "[role='main'] section",
    "[role='main'] article",
    "main picture",
    "main img",
    "[role='main'] picture",
    "[role='main'] img",
    "section",
    "article",
    "picture",
    "[style*='background-image']",
)

DEFAULT_EXCLUDE_SELECTORS = (
    "header",
    "nav",
    "footer",
    "aside",
    "[role='banner']",
    "[role='navigation']",
    "[role='dialog']",
    "[aria-modal='true']",
    "[class*='cookie' i]",
    "[id*='cookie' i]",
    "[class*='chat' i]",
    "[id*='chat' i]",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _dismiss_cookie_banner(page) -> None:
    for label in COOKIE_BUTTON_LABELS:
        try:
            locator = page.get_by_role("button", name=label, exact=True)
            if await locator.count() and await locator.first.is_visible(timeout=250):
                await locator.first.click(timeout=750)
                await page.wait_for_timeout(250)
                return
        except Exception:
            continue


def _intersection_over_union(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> float:
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    left = max(ax, bx)
    top = max(ay, by)
    right = min(ax + aw, bx + bw)
    bottom = min(ay + ah, by + bh)
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    union = aw * ah + bw * bh - intersection
    return intersection / max(union, 1)


async def _discover_visible_regions(
    page,
    source: Source,
    settings: Settings,
    frame_id: str,
) -> list[dict[str, object]]:
    selectors = [*DEFAULT_REGION_SELECTORS, *source.include_selectors]
    excludes = [*DEFAULT_EXCLUDE_SELECTORS, *source.exclude_selectors]
    payload = {
        "selectors": selectors,
        "excludes": excludes,
        "frameId": frame_id,
        "minWidth": settings.min_region_width,
        "minHeight": settings.min_region_height,
        "minArea": settings.min_region_viewport_area,
        "minConfidence": settings.min_region_confidence,
        "limit": settings.max_region_candidates_per_frame,
    }
    return await page.evaluate(
        """
        args => {
          const viewportWidth = window.innerWidth;
          const viewportHeight = window.innerHeight;
          const viewportArea = Math.max(viewportWidth * viewportHeight, 1);
          const excludeSelector = args.excludes.join(',');
          const unique = new Set();
          const elements = [];
          for (const selector of args.selectors) {
            let found = [];
            try { found = document.querySelectorAll(selector); } catch (_) { continue; }
            for (const element of found) {
              if (!unique.has(element)) {
                unique.add(element);
                elements.push(element);
              }
            }
          }

          const intersectionArea = rect => {
            const left = Math.max(rect.left, 0);
            const top = Math.max(rect.top, 0);
            const right = Math.min(rect.right, viewportWidth);
            const bottom = Math.min(rect.bottom, viewportHeight);
            return Math.max(0, right - left) * Math.max(0, bottom - top);
          };

          const results = [];
          let serial = 0;
          for (const element of elements) {
            if (!(element instanceof HTMLElement) && !(element instanceof SVGElement)) continue;
            if (excludeSelector && element.closest(excludeSelector)) continue;
            const style = getComputedStyle(element);
            if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) < 0.05) continue;
            const rect = element.getBoundingClientRect();
            const visibleArea = intersectionArea(rect);
            const visibleWidth = Math.min(rect.right, viewportWidth) - Math.max(rect.left, 0);
            const visibleHeight = Math.min(rect.bottom, viewportHeight) - Math.max(rect.top, 0);
            if (visibleWidth < args.minWidth || visibleHeight < args.minHeight) continue;
            const areaRatio = visibleArea / viewportArea;
            if (areaRatio < args.minArea) continue;

            const tag = element.tagName.toLowerCase();
            const textLength = ((element.innerText || element.getAttribute('alt') || '')).trim().length;
            const textDensity = textLength / Math.max(visibleArea / 10000, 1);
            let imageArea = 0;
            const media = [];
            if (['img', 'picture', 'video', 'canvas'].includes(tag)) media.push(element);
            for (const child of element.querySelectorAll('img,picture,video,canvas')) media.push(child);
            for (const child of media.slice(0, 30)) {
              const childRect = child.getBoundingClientRect();
              imageArea += intersectionArea(childRect);
            }
            const hasBackground = style.backgroundImage && style.backgroundImage !== 'none';
            if (hasBackground) imageArea = Math.max(imageArea, visibleArea * 0.85);
            if (['img', 'picture', 'video', 'canvas'].includes(tag)) imageArea = visibleArea;
            const imageRatio = Math.min(imageArea / Math.max(visibleArea, 1), 1);

            const areaScore = Math.min(areaRatio / 0.35, 1);
            const imageScore = Math.min(imageRatio / 0.70, 1);
            const topScore = 1 - Math.min(Math.max(rect.top, 0) / Math.max(viewportHeight, 1), 1);
            const textScore = 1 - Math.min(textDensity / 16, 1);
            let confidence = 0.35 * areaScore + 0.35 * imageScore + 0.20 * topScore + 0.10 * textScore;
            if (tag === 'img' || tag === 'picture') confidence += 0.05;
            confidence = Math.min(confidence, 1);
            if (confidence < args.minConfidence) continue;

            const regionId = `${args.frameId}-r${String(++serial).padStart(2, '0')}`;
            element.setAttribute('data-pc-region-id', regionId);
            const classes = typeof element.className === 'string'
              ? element.className.split(/\\s+/).filter(Boolean).slice(0, 3).join('.')
              : '';
            const hint = `${tag}${element.id ? '#' + element.id : ''}${classes ? '.' + classes : ''}`.slice(0, 180);
            const regionType = ['img', 'picture', 'video', 'canvas'].includes(tag)
              ? 'media'
              : hasBackground
                ? 'background_media'
                : (rect.top < viewportHeight * 0.65 && areaRatio > 0.18 ? 'hero' : 'section');
            results.push({
              region_id: regionId,
              selector_hint: hint,
              region_type: regionType,
              page_x: Math.max(0, rect.left + window.scrollX),
              page_y: Math.max(0, rect.top + window.scrollY),
              width: Math.min(visibleWidth, viewportWidth),
              height: Math.min(visibleHeight, viewportHeight),
              viewport_area_ratio: areaRatio,
              image_area_ratio: imageRatio,
              text_density: textDensity,
              confidence,
            });
          }
          results.sort((a, b) => b.confidence - a.confidence || b.viewport_area_ratio - a.viewport_area_ratio);
          return results.slice(0, args.limit);
        }
        """,
        payload,
    )


async def _capture_regions_for_frame(
    page,
    source: Source,
    source_dir: Path,
    settings: Settings,
    frame_id: str,
    existing: list[EvidenceRegion],
) -> list[EvidenceRegion]:
    try:
        candidates = await _discover_visible_regions(page, source, settings, frame_id)
    except Exception:
        return []

    captured: list[EvidenceRegion] = []
    existing_boxes = [region.bbox for region in existing]
    existing_hashes = {region.sha256 for region in existing}
    for item in candidates:
        if len(existing) + len(captured) >= settings.max_regions_per_source:
            break
        bbox = (
            int(round(float(item["page_x"]))),
            int(round(float(item["page_y"]))),
            max(1, int(round(float(item["width"])))),
            max(1, int(round(float(item["height"])))),
        )
        if any(_intersection_over_union(bbox, old) >= 0.72 for old in [*existing_boxes, *[r.bbox for r in captured]]):
            continue
        local_region_id = str(item["region_id"])
        region_id = f"{source.id}-{local_region_id}"
        path = source_dir / f"region-{region_id}.png"
        try:
            await page.screenshot(
                path=str(path),
                type="png",
                clip={
                    "x": bbox[0],
                    "y": bbox[1],
                    "width": bbox[2],
                    "height": bbox[3],
                },
                animations="disabled",
                caret="hide",
                scale="css",
            )
        except Exception:
            path.unlink(missing_ok=True)
            continue
        digest = _sha256(path)
        if digest in existing_hashes or any(region.sha256 == digest for region in captured):
            path.unlink(missing_ok=True)
            continue
        captured.append(
            EvidenceRegion(
                source_id=source.id,
                frame_id=frame_id,
                # Region ids are globally unique inside a daily run. This keeps
                # evidence-count gates from collapsing identical f01-r01 ids
                # across unrelated companies into one region.
                region_id=region_id,
                selector_hint=str(item["selector_hint"]),
                region_type=str(item["region_type"]),
                path=str(path),
                sha256=digest,
                bbox=bbox,
                viewport_area_ratio=round(float(item["viewport_area_ratio"]), 5),
                image_area_ratio=round(float(item["image_area_ratio"]), 5),
                text_density=round(float(item["text_density"]), 5),
                confidence=round(float(item["confidence"]), 5),
            )
        )
    return captured


async def _capture_source(
    context,
    source: Source,
    output_dir: Path,
    settings: Settings,
    semaphore: asyncio.Semaphore,
) -> CaptureRecord:
    started = time.monotonic()
    record = CaptureRecord(
        source_id=source.id,
        source_name=source.name,
        sector=source.sector,
        url=source.url,
        captured_at=iso_now(settings.timezone),
    )
    async with semaphore:
        page = await context.new_page()
        try:
            response = await page.goto(
                source.url,
                wait_until="domcontentloaded",
                timeout=settings.navigation_timeout_ms,
            )
            await page.wait_for_timeout(settings.post_load_wait_ms)
            await _dismiss_cookie_banner(page)
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass

            record.final_url = page.url
            record.title = (await page.title()).strip()
            try:
                body_text = (await page.locator("body").inner_text(timeout=3000))[:8000].lower()
            except Exception:
                body_text = ""
            status = response.status if response else 0
            blocked = status in (401, 403, 429) or any(sig in body_text for sig in BLOCK_SIGNATURES)
            record.blocked = blocked
            if blocked:
                raise RuntimeError(
                    f"Source returned a blocked or challenge page (HTTP {status or 'unknown'})"
                )

            source_dir = output_dir / source.id
            source_dir.mkdir(parents=True, exist_ok=True)
            positions = [0]
            if min(source.frames, settings.frames_per_source) > 1:
                positions.append(settings.second_frame_scroll_y)

            for index, scroll_y in enumerate(positions, start=1):
                await page.evaluate("(y) => window.scrollTo(0, y)", scroll_y)
                await page.wait_for_timeout(900)
                frame_id = f"f{index:02d}"
                path = source_dir / f"frame-{index:02d}.jpg"
                await page.screenshot(
                    path=str(path),
                    type="jpeg",
                    quality=88,
                    full_page=False,
                    animations="disabled",
                    caret="hide",
                    scale="css",
                )
                record.frames.append(
                    CaptureFrame(path=str(path), scroll_y=scroll_y, sha256=_sha256(path))
                )
                record.regions.extend(
                    await _capture_regions_for_frame(
                        page,
                        source,
                        source_dir,
                        settings,
                        frame_id,
                        record.regions,
                    )
                )

            record.success = bool(record.regions)
            if not record.success:
                record.error = "Page loaded, but no eligible marketing-creative region was found"
        except Exception as exc:
            record.error = f"{type(exc).__name__}: {exc}"
        finally:
            record.duration_seconds = round(time.monotonic() - started, 3)
            await page.close()
            if settings.request_delay_seconds > 0:
                await asyncio.sleep(settings.request_delay_seconds)
    return record


async def capture_panel_async(
    sources: list[Source],
    output_dir: Path,
    settings: Settings,
) -> list[CaptureRecord]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run `python -m pip install -e .` and "
            "`python -m playwright install chromium`."
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(max(1, settings.concurrency))
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-background-networking",
                "--disable-component-update",
            ],
        )
        context = await browser.new_context(
            viewport={"width": settings.viewport_width, "height": settings.viewport_height},
            locale="en-US",
            timezone_id=settings.timezone,
            color_scheme="light",
            reduced_motion="reduce",
            service_workers="block",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36 PantoneChallenger/1.3"
            ),
        )

        async def route_handler(route):
            if route.request.resource_type in {"media", "websocket"}:
                await route.abort()
            else:
                await route.continue_()

        await context.route("**/*", route_handler)
        records = await asyncio.gather(
            *[
                _capture_source(context, source, output_dir, settings, semaphore)
                for source in sources
            ]
        )
        await context.close()
        await browser.close()

    report = {
        "generated_at": iso_now(settings.timezone),
        "configured_sources": len(sources),
        "captured_sources": sum(1 for record in records if record.success),
        "sources_with_regions": sum(1 for record in records if record.regions),
        "eligible_regions": sum(len(record.regions) for record in records),
        "records": [record.to_dict() for record in records],
    }
    (output_dir / "capture-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return records


def capture_panel(
    sources: list[Source],
    output_dir: Path,
    settings: Settings,
) -> list[CaptureRecord]:
    return asyncio.run(capture_panel_async(sources, output_dir, settings))


def load_capture_report(path: Path) -> list[CaptureRecord]:
    data = json.loads(path.read_text(encoding="utf-8"))
    records: list[CaptureRecord] = []
    for raw in data.get("records", []):
        item = dict(raw)
        item["frames"] = [CaptureFrame(**frame) for frame in item.get("frames", [])]
        regions = []
        for region in item.get("regions", []):
            region = dict(region)
            region["bbox"] = tuple(int(value) for value in region.get("bbox", (0, 0, 0, 0)))
            regions.append(EvidenceRegion(**region))
        item["regions"] = regions
        # V1.2 reports may contain deprecated logo fields. Ignore them safely.
        item.pop("logo_path", None)
        item.pop("logo_source", None)
        item.pop("logo_error", None)
        records.append(CaptureRecord(**item))
    return records
