from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

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
                raise RuntimeError(f"Source returned a blocked or challenge page (HTTP {status or 'unknown'})")

            source_dir = output_dir / source.id
            source_dir.mkdir(parents=True, exist_ok=True)
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
                "Chrome/131.0.0.0 Safari/537.36 PantoneChallenger/1.0"
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
