import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from challenger.evidence import verify_archive
from challenger.render import _write_text_assets
from challenger.trail import color_trail
from challenger.runtime import RuntimeLedger
from challenger.sources.base import CollectionResult
from tests.test_pipeline_v16 import pipeline_fixture
from tests.test_runtime import _source
from tests.test_render import result
from challenger.pipeline import DailyPipeline
from challenger.models import EvidenceRegion


def test_caption_separates_winner_support_and_panel_coverage(tmp_path):
    r = result(tmp_path)
    r.sources_with_eligible_evidence = 36
    r.panel_declared = 58
    r.challenger = [replace(r.challenger[0], source_count=6, domain_count=4)]
    _write_text_assets(r, tmp_path)
    text = (tmp_path / 'caption.txt').read_text()
    assert '6 supporting source groups across 4 domains' in text
    assert 'Panel coverage: 36 of 58' in text
    assert 'signal appeared across 36' not in text


def test_trail_excludes_blocked_days_and_future_observations(tmp_path, monkeypatch):
    p = pipeline_fixture(tmp_path, monkeypatch)
    r = p.run()
    rows = color_trail(p.archive_dir, '#A5C84A', r.date, 'cohort-evidence-v2')
    assert len(rows) == 1 and rows[0]['matching_groups'] == 8
    assert color_trail(p.archive_dir, '#A5C84A', '2026-09-10', 'cohort-evidence-v2') == []
    manifest_path = p.archive_dir / r.date / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()); manifest['state'] = 'blocked'
    manifest_path.write_text(json.dumps(manifest))
    assert color_trail(p.archive_dir, '#A5C84A', r.date, 'cohort-evidence-v2') == []


def test_resume_reuses_verified_capture_and_retries_failed_source(tmp_path, monkeypatch):
    p = DailyPipeline(archive_dir=tmp_path/'archive', work_dir=tmp_path/'work')
    p._run_work = tmp_path/'work'/'2026-09-11'; p._run_work.mkdir(parents=True)
    p._resume = False
    sources = [_source('good'), _source('retry')]
    calls = []
    def collect(selected, date, workdir, settings, *, progress_callback, heartbeat_callback):
        calls.append([s.id for s in selected])
        for source in selected:
            if source.id == 'retry':
                progress_callback(CollectionResult(source, [], {'status':'source_timeout'}), 1)
                continue
            path = Path(workdir)/'source.png'; Image.new('RGB',(20,20),'green').save(path)
            region = EvidenceRegion(source.id, 'f', 'r', 'img', 'image', str(path), (0,0,20,20), 1, 1, 0, .5, .1, .9, True)
            progress_callback(CollectionResult(source,[region],{'status':'captured'}), .1)
    monkeypatch.setattr('challenger.pipeline.collect_browser_sources', collect)
    p._collect(sources, '2026-09-11', RuntimeLedger(tmp_path/'ledger1',total_sources=2))
    p._resume = True
    p._collect(sources, '2026-09-11', RuntimeLedger(tmp_path/'ledger2',total_sources=2))
    assert calls == [['good','retry'],['retry']]


def test_blocked_output_cannot_advance_baseline(tmp_path, monkeypatch):
    from challenger.baseline import load_history
    p = pipeline_fixture(tmp_path, monkeypatch)
    p.settings['quality']['min_evidence_sources_block'] = 100
    r=p.run()
    assert r.state.value == 'blocked'
    assert not (p.archive_dir/r.date/'feed-post.png').exists()
    assert load_history(p.archive_dir,'2026-09-12',compatibility_key='cohort-evidence-v2') == []


def test_site_refuses_an_archive_changed_to_ready(tmp_path, monkeypatch):
    from challenger.site import build_site
    p = pipeline_fixture(tmp_path, monkeypatch)
    r = p.run()
    path = p.archive_dir / r.date / 'result.json'
    payload = json.loads(path.read_text()); payload['state'] = 'ready'
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match='Archive integrity failed'):
        build_site(p.archive_dir, tmp_path / 'site')
