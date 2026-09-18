"""Offline page fixtures exercise actual Chromium capture. Required in CI."""

import asyncio
from dataclasses import replace
import os
from urllib.parse import quote

import pytest
from playwright.async_api import async_playwright

from challenger.capture.browser import BrowserCollector
from challenger.models import SignalStage
from tests.test_runtime import _source
from tests.test_temporal_capture_v161 import URL, POLICY


@pytest.mark.parametrize("kind", ["dated_card", "ranked_chart"])
def test_browser_saves_temporal_evidence_with_the_image(tmp_path, kind):
    async def run():
        async with async_playwright() as pw:
            try:
                browser = await pw.chromium.launch(headless=True)
            except Exception as exc:
                if (
                    "Executable doesn't exist" in str(exc)
                    and os.getenv("REQUIRE_CAPTURE_BROWSER_TEST") != "1"
                ):
                    pytest.skip("Chromium is not installed; CI requires this browser test.")
                raise
            context = await browser.new_context(viewport={"width": 1440, "height": 1200})
            svg = '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="380"><defs><linearGradient id="g"><stop stop-color="#A5C84A"/><stop offset="1" stop-color="#4799A2"/></linearGradient></defs><rect width="600" height="380" fill="url(#g)"/><circle cx="200" cy="180" r="80" fill="#E34834"/></svg>'
            img = '<img src="data:image/svg+xml,' + quote(svg) + '">'
            if kind == "dated_card":
                source = replace(_source("dated"), include_selectors=["main article"])
                markup = (
                    '<style>article{width:600px;height:420px}img{width:600px;height:380px}</style><main><article><a href="/work">'
                    + img
                    + '</a><time datetime="2026-09-16">September 16, 2026</time></article></main>'
                )
            else:
                source = replace(
                    _source("chart"),
                    url=URL,
                    allowed_hosts=["apple.com"],
                    signal_stage=SignalStage.ATTENTION,
                    event_type="commercial_attention",
                    include_selectors=["main section"],
                    options={"temporal_evidence": POLICY},
                )
                markup = (
                    "<style>section{display:flex;width:1000px;height:300px}.card{width:320px}img{width:300px;height:230px}</style><main><section>"
                    + "".join(
                        f'<div class="card"><a href="/us/music-video/item-{i}/{i}">{img}</a><span>{i}</span><p>Video {i}</p></div>'
                        for i in range(1, 4)
                    )
                    + "</section></main>"
                )
            html = (
                "<html><head><title>Top Music Charts</title></head><body>"
                + markup
                + "</body></html>"
            )

            async def respond(route):
                await route.fulfill(status=200, content_type="text/html", body=html)

            await context.route("**/*", respond)
            collector = BrowserCollector(
                tmp_path, {"capture": {"post_load_wait_ms": 0, "network_idle_timeout_ms": 100}}
            )
            try:
                regions, report = await collector._collect_url(
                    context, source, source.url, "2026-09-16", 1
                )
                assert regions, report
                region = regions[0]
                assert region.captured_at
                proof = region.metadata["temporal_evidence"]
                if kind == "dated_card":
                    assert region.published_at == "2026-09-16"
                    assert region.page_url == "https://example.test/work"
                else:
                    assert region.published_at == ""
                    assert proof["kind"] == "ranked_snapshot" and len(proof["items"]) == 3
                    assert proof["observed_at"] == region.captured_at
            finally:
                await context.close()
                await browser.close()

    asyncio.run(run())
