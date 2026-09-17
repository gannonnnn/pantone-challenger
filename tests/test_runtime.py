from __future__ import annotations

import json
import sys
import time
import types
from pathlib import Path

try:
    import feedparser  # noqa: F401
except ModuleNotFoundError:
    sys.modules["feedparser"] = types.SimpleNamespace(parse=lambda _value: types.SimpleNamespace(entries=[]))

from challenger.capture.browser import BrowserCollector
from challenger.models import (
    Domain,
    PanelType,
    RightsMode,
    ScaleClass,
    SignalStage,
    SourceSpec,
)
from challenger.pipeline import DailyPipeline
from challenger.runtime import RuntimeLedger
from challenger.sources.base import CollectionResult, SourceAdapter


def _source(source_id: str, *, adapter: str = "webpage") -> SourceSpec:
    return SourceSpec(
        id=source_id,
        name=source_id.replace("-", " ").title(),
        enabled=True,
        adapter=adapter,
        domain=Domain.ART,
        sector="art",
        signal_stage=SignalStage.CREATION,
        scale_class=ScaleClass.INDEPENDENT,
        panel_type=PanelType.DISCOVERY,
        event_type="newly_published",
        geography="global",
        rights_mode=RightsMode.ANALYZE_ONLY,
        url=f"https://example.test/{source_id}",
    )


def test_runtime_ledger_persists_incremental_progress(tmp_path, capsys):
    ledger = RuntimeLedger(tmp_path, total_sources=2)
    ledger.start_phase("collection")
    ledger.record_source(
        source_id="one",
        source_name="Source One",
        adapter="webpage",
        status="captured",
        regions=2,
        duration_seconds=1.25,
    )
    ledger.heartbeat(active=1, pending=0)
    ledger.end_phase("collection")
    summary = ledger.finalize(status="complete")

    rows = [json.loads(line) for line in (tmp_path / "runtime-progress.jsonl").read_text().splitlines()]
    saved = json.loads((tmp_path / "runtime-summary.json").read_text())
    assert rows[0]["source_id"] == "one"
    assert rows[0]["completed"] == 1
    assert summary["status_counts"] == {"captured": 1}
    assert saved["status"] == "complete"
    assert "[01/02] Source One" in capsys.readouterr().out


def test_nested_candidate_boxes_are_deduplicated():
    candidates = [
        {"bbox": [0.0, 0.0, 1000.0, 700.0], "confidence": 0.9},
        {"bbox": [10.0, 10.0, 980.0, 680.0], "confidence": 0.8},
        {"bbox": [1050.0, 0.0, 300.0, 300.0], "confidence": 0.7},
    ]
    accepted = BrowserCollector._dedupe_candidate_boxes(candidates)
    assert accepted == [candidates[0], candidates[2]]


def test_source_adapter_deadline_marks_timeout(tmp_path):
    class Adapter(SourceAdapter):
        def collect(self, source, run_date):
            raise NotImplementedError

    adapter = Adapter(
        tmp_path,
        {"capture": {"api_source_timeout_s": 0.001, "http_timeout_s": 0.001}},
    )
    time.sleep(0.01)
    result = adapter.finalize_result(CollectionResult(source=_source("api", adapter="rss")))
    assert result.report["status"] == "source_timeout"
    assert result.report["deadline_exceeded"] is True


def test_pipeline_sends_all_web_sources_to_one_browser_batch(tmp_path, monkeypatch):
    pipeline = DailyPipeline(archive_dir=tmp_path / "archive", work_dir=tmp_path / "work")
    sources = [_source("alpha"), _source("beta")]
    calls = []

    def fake_collect_browser_sources(
        selected,
        run_date,
        workdir,
        settings,
        *,
        progress_callback,
        heartbeat_callback,
    ):
        calls.append([source.id for source in selected])
        results = []
        for source in selected:
            result = CollectionResult(source=source, report={"status": "captured"})
            progress_callback(result, 0.1)
            results.append(result)
        return results

    monkeypatch.setattr("challenger.pipeline.collect_browser_sources", fake_collect_browser_sources)
    ledger = RuntimeLedger(tmp_path / "runtime", total_sources=2)
    results = pipeline._collect(sources, "2026-09-07", ledger)

    assert calls == [["alpha", "beta"]]
    assert [result.source.id for result in results] == ["alpha", "beta"]
    assert ledger.completed_sources == 2


def test_runtime_configuration_bounds_a_full_browser_panel():
    pipeline = DailyPipeline()
    capture = pipeline.settings["capture"]
    workers = int(capture["browser_workers"])
    source_timeout = float(capture["browser_source_timeout_s"])
    declared_sources = 58
    theoretical_seconds = ((declared_sources + workers - 1) // workers) * source_timeout
    assert theoretical_seconds < float(capture["collection_budget_s"])
    assert float(capture["collection_budget_s"]) <= 20 * 60


def test_daily_workflow_preserves_diagnostics_and_has_hard_timeout():
    workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")
    assert "timeout-minutes: 35" in workflow
    assert "PYTHONUNBUFFERED: \"1\"" in workflow
    assert "Upload failed-run diagnostics" in workflow
    assert "continue-on-error: true" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "timeout --signal=TERM --kill-after=30s 28m" in workflow


def test_browser_batch_uses_one_process_and_times_out_slow_source(tmp_path, monkeypatch):
    import asyncio

    launches = {"count": 0}

    class FakeBrowser:
        async def close(self):
            return None

    class FakeChromium:
        async def launch(self, **_kwargs):
            launches["count"] += 1
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeManager:
        async def __aenter__(self):
            return FakePlaywright()

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setattr("challenger.capture.browser.async_playwright", lambda: FakeManager())
    settings = {
        "capture": {
            "browser_workers": 2,
            "browser_source_timeout_s": 0.02,
            "collection_budget_s": 1,
            "heartbeat_seconds": 0.01,
        }
    }
    collector = BrowserCollector(tmp_path, settings)

    async def fake_collect(_browser, source, _run_date):
        if source.id == "slow":
            await asyncio.sleep(0.08)
        return [], {"status": "captured"}

    monkeypatch.setattr(collector, "_collect_with_browser", fake_collect)
    progress = []
    results = asyncio.run(
        collector.collect_many(
            [_source("fast"), _source("slow")],
            "2026-09-07",
            progress_callback=lambda result, duration: progress.append(
                (result.source.id, result.report["status"], duration)
            ),
        )
    )

    by_id = {result.source.id: result for result in results}
    assert launches["count"] == 1
    assert by_id["fast"].report["status"] == "captured"
    assert by_id["slow"].report["status"] == "source_timeout"
    assert {row[0] for row in progress} == {"fast", "slow"}
