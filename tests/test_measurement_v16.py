from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from challenger.baseline import load_history, panel_candidate_history
from challenger.emergence import score_emergence, select_leaders
from challenger.evidence import prepare_evidence, verify_payload
from challenger.identity import observation_identity
from challenger.models import Domain, PanelType, ScaleClass, SignalStage, TrendState
from tests.helpers import candidate, observation
from tests.test_runtime import _source

COLOR = '#A5C84A'


def observations(n=16, match=lambda i: i % 2 == 0):
    return [{'source_id': f'source-{i}', 'domain': ['art', 'fashion'][i % 2],
             'panel_type': 'benchmark', 'metadata': {'baseline_eligible': True},
             'swatches': [{'hex': COLOR if match(i) else '#CC1100', 'share': .2}]}
            for i in range(n)]


def history(rows):
    return [{'date': f'2026-09-{i:02}', 'observations': rows} for i in range(1, 8)]


def test_more_coverage_does_not_make_an_unchanged_color_surge():
    c = candidate(source_count=8)
    c = replace(c, evidence=[replace(e, source_id=f'source-{i*2}') for i, e in enumerate(c.evidence)])
    old = observations(8)
    now = observations(16)
    result = score_emergence([c], history(old), {}, now)[0]
    assert result.comparison['valid']
    assert result.comparison['change_percentage_points'] == 0
    assert result.trend_state == TrendState.IDENTITY
    assert result.novelty == 0
    assert not select_leaders([result], {}, 7)[0]


def test_url_turnover_does_not_create_growth():
    c = candidate(source_count=8)
    renamed = replace(c, evidence=[replace(e, source_id='new-url-' + e.source_id) for e in c.evidence])
    result = score_emergence([renamed], history(observations()), {}, observations())[0]
    assert result.trend_state == TrendState.STABLE
    assert result.novelty == 0


def test_real_growth_on_the_same_sources_can_qualify():
    c = candidate(source_count=8)
    old = observations(8, lambda i: i < 2)
    now = observations(8, lambda i: True)
    result = score_emergence([c], history(old), {}, now)[0]
    assert result.comparison['valid']
    assert result.comparison['change_percentage_points'] > 50
    assert result.trend_state in {TrendState.SURGING, TrendState.SPREADING, TrendState.RISING}
    assert select_leaders([result], {}, 7)[0]


def test_missing_actors_and_new_sources_are_unknown():
    old = observations(4)
    now = observations(16)
    result = panel_candidate_history(history(old), candidate().oklab, current_observations=now)
    assert not result['valid']
    assert result['stable_benchmark_actors'] == 4
    assert result['change_percentage_points'] is None


def test_discovery_rotation_cannot_change_benchmark_prevalence():
    now = observations() + [{**o, 'source_id': 'new-' + o['source_id'], 'panel_type': 'discovery'} for o in observations(30, lambda _: True)]
    result = panel_candidate_history(history(observations()), candidate().oklab, current_observations=now)
    assert result['valid'] and result['change_percentage_points'] == 0
    assert result['observed_benchmark_actors'] == 16


def test_old_invalid_days_and_invalid_observations_do_not_enter_baseline(tmp_path):
    for d, state, admitted in [('01', 'blocked', True), ('02', 'ready', False), ('03', 'baseline_only', True)]:
        day = tmp_path / f'2026-09-{d}'; day.mkdir()
        (day / 'manifest.json').write_text(json.dumps({'state': state, 'baseline_eligible': admitted, 'baseline_compatibility_key': 'v2'}))
        (day / 'observations.json').write_text(json.dumps([{'source_id': 'good', 'metadata': {'baseline_eligible': True}}, {'source_id': 'bad', 'metadata': {'baseline_eligible': False}}]))
    loaded = load_history(tmp_path, '2026-09-05', compatibility_key='v2')
    assert [d['date'] for d in loaded] == ['2026-09-03']
    assert [o['source_id'] for o in loaded[0]['observations']] == ['good']


def test_unknown_feed_creators_use_one_conservative_group(tmp_path):
    source = _source('feed', adapter='rss')
    region = observation(tmp_path, 'a', COLOR).region
    first = observation_identity(source, region, item_adapter=True)
    second = observation_identity(source, replace(region, page_url='https://example.test/a-different-post'), item_adapter=True)
    assert first['actor_id'] == second['actor_id'] == 'publisher:feed'
    assert first['item_id'] != second['item_id']
    assert not first['identity_verified']


def test_verified_seller_identity_survives_new_listing_urls(tmp_path):
    source = replace(_source('etsy', adapter='etsy'), platform='etsy')
    region = replace(observation(tmp_path, 'a', COLOR).region, metadata={'creator_id': 'shop-12', 'identity_verified': True, 'item_id': 'listing-1'})
    first = observation_identity(source, region, item_adapter=True)
    second = observation_identity(source, replace(region, metadata={**region.metadata, 'item_id': 'listing-2'}), item_adapter=True)
    assert first['actor_id'] == second['actor_id'] == 'etsy:shop-12'
    assert first['identity_verified']


def test_rejections_happen_before_scoring_and_do_not_build_baseline(tmp_path):
    obs = observation(tmp_path, 'future', COLOR)
    obs.region.published_at = '2026-09-06'
    baseline, current, report, _ = prepare_evidence([obs], '2026-09-05', {}, tmp_path / 'archive')
    assert baseline == current == []
    assert report['temporal_counts'] == {'rejected_future': 1}


def test_undated_historical_art_cannot_support_a_daily_color(tmp_path):
    obs = replace(observation(tmp_path, 'art', COLOR), event_type='permanent_collection')
    baseline, current, _, _ = prepare_evidence([obs], '2026-09-05', {}, tmp_path / 'archive')
    assert baseline == current == []


def test_current_dated_creative_is_admitted(tmp_path):
    obs = observation(tmp_path, 'art', COLOR)
    obs.region.published_at = '2026-09-05'
    baseline, current, report, _ = prepare_evidence([obs], '2026-09-05', {}, tmp_path / 'archive')
    assert len(baseline) == len(current) == 1
    assert current[0].metadata['current_eligible']
    assert report['current_regions'] == 1


def test_undated_benchmark_can_build_history_without_public_evidence(tmp_path):
    obs = observation(tmp_path, 'brand', COLOR, domain=Domain.TECHNOLOGY, stage=SignalStage.DISTRIBUTION,
                      scale=ScaleClass.LARGE_COMMERCIAL, panel=PanelType.BENCHMARK)
    obs = replace(obs, event_type='brand_campaign')
    baseline, current, _, _ = prepare_evidence([obs], '2026-09-05', {}, tmp_path / 'archive')
    assert len(baseline) == 1 and not current


def test_frozen_result_verifier_rejects_unadmitted_support():
    assert verify_payload({'challenger': [{'source_count': 1, 'domain_count': 1, 'hex': COLOR,
                           'evidence': [{'source_id': 'unadmitted', 'region_id': 'r', 'domain': 'art', 'local_hex': COLOR}]}]}, [])


def test_score_margin_ignores_ineligible_candidates():
    a = candidate(score=80)
    neutral = replace(candidate('#777777', score=79), family_label='Gray')
    b = candidate('#4799A2', score=70)
    selected = select_leaders([a, neutral, b], {}, 7)[0]
    assert len(selected) == 1
    assert selected[0].score_margin == 10
