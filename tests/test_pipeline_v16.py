import json
import time
from dataclasses import replace
from pathlib import Path

import pytest

from challenger.capture.api_batch import collect_api_sources
from challenger.evidence import verify_archive
from challenger.models import Domain, PanelType, ScaleClass, SignalStage, PublicationState
from challenger.pipeline import DailyPipeline
from challenger.sources.base import CollectionResult
from tests.helpers import observation
from tests.test_runtime import _source


def pipeline_fixture(tmp_path, monkeypatch, run_date='2026-09-11'):
    p = DailyPipeline(archive_dir=tmp_path / 'archive', work_dir=tmp_path / 'work')
    sources, observations = [], []
    for i in range(8):
        obs = observation(tmp_path, f's{i}', '#A5C84A', domain=[Domain.ART, Domain.FASHION, Domain.TECHNOLOGY, Domain.MARKETPLACE][i % 4],
                          stage=[SignalStage.CREATION, SignalStage.DISTRIBUTION, SignalStage.ATTENTION][i % 3],
                          panel=PanelType.BENCHMARK, scale=ScaleClass.LARGE_COMMERCIAL)
        obs.region.published_at = run_date
        obs.metadata.update(baseline_eligible=True, identity_verified=True, adapter='webpage', item_id=obs.region.page_url)
        observations.append(obs)
        sources.append(replace(_source(f's{i}'), domain=obs.domain, panel_type=PanelType.BENCHMARK))
    p.sources = sources
    p.settings['quality'].update(min_evidence_sources_block=4, min_evidence_sources_ready=6)
    p.settings['quality'].update(min_domains_block=2, min_domains_ready=4, min_stages_ready=3)
    p.settings['baseline']['compatibility_key'] = 'cohort-evidence-v2'
    monkeypatch.setattr(p, 'resolve_date', lambda value: run_date)
    monkeypatch.setattr(p, '_collect', lambda *args: [CollectionResult(s, [o.region], {'status': 'captured'}) for s, o in zip(sources, observations)])
    monkeypatch.setattr(p, '_extract_observations', lambda *args: (observations, []))
    return p


def test_pipeline_admits_baseline_before_render_and_seals_result(tmp_path, monkeypatch):
    p = pipeline_fixture(tmp_path, monkeypatch)
    result = p.run()
    day = p.archive_dir / result.date
    assert result.state == PublicationState.REVIEW_ONLY
    assert verify_archive(day)['passed']
    assert json.loads((day / 'manifest.json').read_text())['baseline_eligible']
    assert not (day / 'feed-post.png').exists()
    assert (day / 'review-summary.png').exists()
    assert (day / 'evidence-ledger.json').exists()


def test_failed_rebuild_preserves_existing_archive(tmp_path, monkeypatch):
    p = pipeline_fixture(tmp_path, monkeypatch)
    result = p.run()
    day = p.archive_dir / result.date
    previous = (day / 'result.json').read_bytes()
    def fail(*args, **kwargs):
        raise ValueError('Intentional render failure')
    monkeypatch.setattr('challenger.pipeline.render_daily', fail)
    with pytest.raises(ValueError, match='Intentional'):
        p.run(rebuild=True)
    assert (day / 'result.json').read_bytes() == previous
    assert verify_archive(day)['passed']


def test_postflight_detects_modified_results(tmp_path, monkeypatch):
    p = pipeline_fixture(tmp_path, monkeypatch)
    result = p.run()
    day = p.archive_dir / result.date
    record = json.loads((day / 'result.json').read_text())
    record['sources_with_eligible_evidence'] += 10
    (day / 'result.json').write_text(json.dumps(record))
    assert not verify_archive(day)['passed']


def _hung_adapter(connection, source, run_date, workdir, settings):
    time.sleep(30)


def test_uncooperative_api_worker_is_terminated(tmp_path):
    started = time.monotonic()
    results = []
    collect_api_sources([_source('api', adapter='rss')], '2026-09-11', tmp_path,
                        {'capture': {'api_source_timeout_s': .1}},
                        lambda result, elapsed: results.append(result), worker=_hung_adapter)
    assert time.monotonic() - started < 3
    assert results[0].report['status'] == 'source_timeout'


def test_live_backdating_rejected_before_collection(tmp_path, monkeypatch):
    p = DailyPipeline(archive_dir=tmp_path / 'archive', work_dir=tmp_path / 'work')
    monkeypatch.setattr(p, '_collect', lambda *args: pytest.fail('No collection should start'))
    with pytest.raises(ValueError, match='observation date'):
        p.run(run_date='2000-01-01')
