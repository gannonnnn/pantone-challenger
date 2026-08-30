from __future__ import annotations

import asyncio
import hashlib
import io
import json
import time
from pathlib import Path
from urllib.parse import urljoin

from PIL import Image

from .config import Settings
from .dates import iso_now
from .models import CaptureFrame, CaptureRecord, Source

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

LOGO_SELECTORS = (
    'header img[alt*="logo" i]',
    '[role="banner"] img[alt*="logo" i]',
    'header a[href="/"] img',
    '[role="banner"] a[href="/"] img',
    'header img',
    '[role="banner"] img',
    'header svg',
    '[role="banner"] svg',
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _trim_near_white_background(image: Image.Image) -> Image.Image:
    """Remove a plain near-white backdrop while preserving colored/black marks."""
    rgba = image.convert("RGBA")
    if rgba.width < 2 or rgba.height < 2:
        return rgba
    corners = [
        rgba.getpixel((0, 0)),
        rgba.getpixel((rgba.width - 1, 0)),
        rgba.getpixel((0, rgba.height - 1)),
        rgba.getpixel((rgba.width - 1, rgba.height - 1)),
    ]
    white_corners = sum(
        1 for r, g, b, a in corners if a > 220 and min(r, g, b) >= 244
    )
    if white_corners < 3:
        return rgba

    pixels = []
    flattened = (
        rgba.get_flattened_data()
        if hasattr(rgba, "get_flattened_data")
        else rgba.getdata()
    )
    for r, g, b, a in flattened:
        if a > 0 and min(r, g, b) >= 246 and max(r, g, b) - min(r, g, b) <= 5:
            pixels.append((r, g, b, 0))
        else:
            pixels.append((r, g, b, a))
    rgba.putdata(pixels)
    return rgba


def _normalise_logo_image(image: Image.Image, output: Path) -> bool:
    """Create a consistent transparent brand-mark asset for social rendering."""
    rgba = _trim_near_white_background(image)
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return False
    rgba = rgba.crop(bbox)
    if rgba.width < 12 or rgba.height < 8:
        return False
    if rgba.width > 1600 or rgba.height > 800:
        return False

    rgba.thumbnail((244, 112), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (260, 128), (0, 0, 0, 0))
    x = (canvas.width - rgba.width) // 2
    y = (canvas.height - rgba.height) // 2
    canvas.alpha_composite(rgba, (x, y))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)
    return True


def _normalise_logo_file(source: Path, output: Path) -> bool:
    try:
        with Image.open(source) as image:
            return _normalise_logo_image(image, output)
    except (OSError, ValueError):
        return False


def _normalise_logo_bytes(payload: bytes, output: Path) -> bool:
    try:
        with Image.open(io.BytesIO(payload)) as image:
            return _normalise_logo_image(image, output)
    except (OSError, ValueError):
        return False


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


async def _capture_visible_brand_mark(page, source: Source, source_dir: Path) -> str:
    """Prefer the visible first-party header mark over a generic favicon."""
    brand_tokens = {
        token.lower().strip("+&.,'’")
        for token in source.name.split()
        if len(token.strip("+&.,'’")) >= 3
    }
    candidates: list[tuple[float, object]] = []
    seen: set[str] = set()

    for selector in LOGO_SELECTORS:
        try:
            locator = page.locator(selector)
            count = min(await locator.count(), 10)
        except Exception:
            continue
        for index in range(count):
            item = locator.nth(index)
            try:
                if not await item.is_visible(timeout=250):
                    continue
                box = await item.bounding_box()
                if not box:
                    continue
                width, height = box["width"], box["height"]
                if width < 24 or height < 10 or width > 700 or height > 340:
                    continue
                signature = f"{round(box['x'])}:{round(box['y'])}:{round(width)}:{round(height)}"
                if signature in seen:
                    continue
                seen.add(signature)
                metadata = " ".join(
                    filter(
                        None,
                        [
                            await item.get_attribute("alt"),
                            await item.get_attribute("aria-label"),
                            await item.get_attribute("title"),
                            await item.get_attribute("src"),
                            await item.get_attribute("class"),
                        ],
                    )
                ).lower()
                score = 0.0
                if "logo" in metadata or "brand" in metadata:
                    score += 70.0
                if any(token in metadata for token in brand_tokens):
                    score += 85.0
                if box["y"] < 180:
                    score += 25.0
                ratio = width / max(height, 1)
                if 1.1 <= ratio <= 8.0:
                    score += 15.0
                score += min(width, 250) / 25.0
                candidates.append((score, item))
            except Exception:
                continue

    for _, item in sorted(candidates, key=lambda value: value[0], reverse=True):
        temporary = source_dir / "logo-visible-raw.png"
        output = source_dir / "logo.png"
        try:
            await item.screenshot(path=str(temporary), type="png")
            if _normalise_logo_file(temporary, output):
                temporary.unlink(missing_ok=True)
                return str(output)
        except Exception:
            pass
        temporary.unlink(missing_ok=True)
    return ""


async def _capture_favicon(context, page, source_dir: Path) -> str:
    """Fetch a first-party icon when a visible header logo cannot be captured."""
    candidates: list[str] = []
    try:
        items = await page.locator(
            'link[rel~="icon"], link[rel="apple-touch-icon"], link[rel="shortcut icon"]'
        ).evaluate_all(
            """elements => elements.map(element => ({
                href: element.href || '',
                rel: element.rel || '',
                sizes: element.sizes ? element.sizes.value : '',
                type: element.type || ''
            }))"""
        )
    except Exception:
        items = []

    def icon_rank(item: dict[str, str]) -> tuple[int, int]:
        rel = item.get("rel", "").lower()
        sizes = item.get("sizes", "")
        numeric = [int(value) for value in sizes.replace("x", " ").split() if value.isdigit()]
        size = max(numeric, default=0)
        return (2 if "apple-touch" in rel else 1, size)

    for item in sorted(items, key=icon_rank, reverse=True):
        href = item.get("href", "")
        if href and href not in candidates:
            candidates.append(href)
    fallback = urljoin(page.url, "/favicon.ico")
    if fallback not in candidates:
        candidates.append(fallback)

    output = source_dir / "logo.png"
    for icon_url in candidates[:8]:
        if icon_url.startswith("data:"):
            continue
        try:
            response = await context.request.get(icon_url, timeout=7000, fail_on_status_code=False)
            if not response.ok:
                continue
            content_type = (response.headers.get("content-type") or "").lower()
            if "svg" in content_type or icon_url.lower().endswith(".svg"):
                continue
            body = await response.body()
            if not body or len(body) > 2_000_000:
                continue
            if _normalise_logo_bytes(body, output):
                return str(output)
        except Exception:
            continue
    return ""


async def _capture_brand_mark(context, page, source: Source, source_dir: Path) -> tuple[str, str]:
    visible = await _capture_visible_brand_mark(page, source, source_dir)
    if visible:
        return visible, "official_page_header"
    favicon = await _capture_favicon(context, page, source_dir)
    if favicon:
        return favicon, "official_page_icon"
    return "", ""


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
            logo_path, logo_source = await _capture_brand_mark(context, page, source, source_dir)
            record.logo_path = logo_path
            record.logo_source = logo_source

            positions = [0]
            if min(source.frames, settings.frames_per_source) > 1:
                positions.append(settings.second_frame_scroll_y)

            for index, scroll_y in enumerate(positions, start=1):
                await page.evaluate("(y) => window.scrollTo(0, y)", scroll_y)
                await page.wait_for_timeout(900)
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
            record.success = bool(record.frames)
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
            viewport={
                "width": settings.viewport_width,
                "height": settings.viewport_height,
            },
            locale="en-US",
            timezone_id=settings.timezone,
            color_scheme="light",
            reduced_motion="reduce",
            service_workers="block",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36 PantoneChallenger/1.1"
            ),
        )

        async def route_handler(route):
            if route.request.resource_type in {"media", "websocket"}:
                await route.abort()
            else:
                await route.continue_()

        await context.route("**/*", route_handler)
        tasks = [
            _capture_source(context, source, output_dir, settings, semaphore)
            for source in sources
        ]
        records = await asyncio.gather(*tasks)
        await context.close()
        await browser.close()

    report = {
        "generated_at": iso_now(settings.timezone),
        "configured_sources": len(sources),
        "captured_sources": sum(1 for record in records if record.success),
        "captured_logos": sum(1 for record in records if record.logo_path),
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
    for item in data.get("records", []):
        item = dict(item)
        item["frames"] = [CaptureFrame(**frame) for frame in item.get("frames", [])]
        records.append(CaptureRecord(**item))
    return records
