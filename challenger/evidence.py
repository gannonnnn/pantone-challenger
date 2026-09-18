"""Typed evidence admission before scoring; histories use the same decisions."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import replace
from datetime import date
from pathlib import Path

from challenger.identity import canonical_url
from challenger.image_quality import hash_distance
from challenger.models import Observation
from challenger.palette import swatch_is_candidate_eligible
from challenger.temporal_semantic_integrity import _load_config, _slug, _temporal_status
from challenger.capture.temporal import snapshot_is_current


def _prior_regions(archive: Path, before: str, key: str) -> dict:
    prior = {}
    for day in sorted(archive.glob('????-??-??')):
        if day.name >= before:
            continue
        try:
            manifest = json.loads((day / 'manifest.json').read_text())
            if (manifest.get('baseline_eligible') is not True or manifest.get('state') == 'blocked'
                    or manifest.get('baseline_compatibility_key') != key):
                continue
            verification = json.loads((day / 'temporal-semantic-integrity.json').read_text())
            if verification.get('passed') is not True:
                continue
            expected = manifest.get('validated_sha256', {}).get('evidence-ledger.json')
            if hashlib.sha256((day / 'evidence-ledger.json').read_bytes()).hexdigest() != expected:
                continue
            ledger = json.loads((day / 'evidence-ledger.json').read_text())
            prior.update(ledger.get('regions', {}))
        except (ValueError, OSError, TypeError):
            continue
    return prior


def region_key(obs: Observation) -> str:
    item_id = obs.metadata.get('item_id', '') if obs.metadata.get('adapter') != 'webpage' else ''
    slot = item_id or f'{obs.region.selector_hint}|{obs.region.region_id}'
    value = f'{obs.source_id}|{canonical_url(obs.region.page_url)}|{slot}'
    return hashlib.sha256(value.encode()).hexdigest()


def prepare_evidence(observations: list[Observation], run_date: str, settings: dict,
                     archive: Path) -> tuple[list[Observation], list[Observation], dict, dict]:
    cfg = _load_config(Path(__file__).resolve().parent.parent)
    cfg.update(settings.get('temporal', {}))
    prior = _prior_regions(archive, run_date, settings.get('baseline', {}).get('compatibility_key', ''))
    baseline, current, decisions = [], [], []
    ledger = {'schema_version': 2, 'date': run_date, 'regions': {}}
    for original in observations:
        obs = replace(original, metadata=dict(original.metadata))
        key = region_key(obs)
        old = prior.get(key, {})
        fingerprint = obs.region.content_hash
        record = {
            'source_id': obs.source_id, 'source_name': obs.source_name,
            'source_url': obs.region.page_url, 'published_at': obs.region.published_at,
            'domain': obs.domain.value, 'signal_stage': obs.signal_stage.value,
            'panel_type': obs.panel_type.value, 'scale_class': obs.scale_class.value,
            'event_type': obs.event_type,
        }
        prior_for_status = {'sources': {_slug(obs.source_id): old}} if old else {'sources': {}}
        status, reasons, *_ = _temporal_status(record, date.fromisoformat(run_date),
                                              prior_for_status, fingerprint, cfg)
        proof = obs.region.metadata.get('temporal_evidence', {})
        if (proof.get('kind') == 'ranked_snapshot' and obs.signal_stage.value == 'attention'
                and not status.startswith('rejected_')):
            if snapshot_is_current(proof, obs.metadata.get('temporal_policy', {}), obs.region.page_url,
                                   obs.region.captured_at, run_date, settings.get('timezone', 'America/New_York')):
                status = 'eligible_observed_attention'
                reasons = ['Ranked chart appearance was recorded with item links and ranks at capture time. This is not a release date or proof of increasing attention.']
            else:
                status = 'context_only_unverified_snapshot'
                reasons = ['The chart snapshot could not be verified for this source and observation date.']
        if proof.get('event_end') and proof['event_end'] < run_date:
            status = 'context_only_stale'
            reasons = ['The documented event ended before the observation date.']
        if status == 'eligible_changed_today' and old.get('perceptual_hash') and obs.region.perceptual_hash:
            if hash_distance(old['perceptual_hash'], obs.region.perceptual_hash) <= int(settings.get('dedupe', {}).get('cross_source_phash_distance', 6)):
                status = 'baseline_only_unchanged'
                reasons = ['Only a minor image change was observed; no new creative is established.']
        kept_swatches = []
        for swatch in obs.swatches:
            muted = swatch.oklch[1] < float(cfg['muted_chroma_threshold'])
            min_share = float(cfg['muted_minimum_total_color_share'] if muted else cfg['minimum_total_color_share'])
            min_component = float(cfg['muted_minimum_component_share'] if muted else cfg['minimum_component_share'])
            if (swatch_is_candidate_eligible(swatch, settings) and swatch.share >= min_share
                    and swatch.largest_component_share >= min_component):
                kept_swatches.append(swatch)
        baseline_ok = status.startswith(('eligible_', 'baseline_only_', 'calibration_only_'))
        current_ok = status.startswith('eligible_') and bool(kept_swatches)
        obs = replace(obs, swatches=kept_swatches)
        obs.metadata.update({'temporal_status': status, 'baseline_eligible': baseline_ok,
                             'current_eligible': current_ok, 'admission_version': 2,
                             'admission_reasons': reasons, 'evidence_key': key})
        decisions.append({'source_id': obs.source_id, 'region_id': obs.region.region_id,
                          'registry_source_id': obs.metadata.get('registry_source_id', obs.source_id),
                          'signal_stage': obs.signal_stage.value,
                          'source_url': obs.region.page_url, 'temporal_status': status,
                          'baseline_eligible': baseline_ok, 'current_eligible': current_ok,
                          'kept_swatches': len(kept_swatches), 'reasons': reasons})
        if baseline_ok:
            # Keep successfully observed zero-match actors in denominators.
            baseline.append(obs)
            ledger['regions'][key] = {
                'fingerprint': fingerprint, 'perceptual_hash': obs.region.perceptual_hash,
                'first_seen': old.get('first_seen', run_date), 'last_seen': run_date,
                'last_changed': old.get('last_changed', run_date) if status == 'baseline_only_unchanged' else run_date,
                'captured_at': obs.captured_at, 'source_id': obs.source_id,
                'item_id': obs.metadata.get('item_id', ''),
            }
        if current_ok:
            current.append(obs)
    report = {'schema_version': 2, 'date': run_date,
              'temporal_counts': dict(Counter(d['temporal_status'] for d in decisions)),
              'baseline_regions': len(baseline), 'current_regions': len(current), 'decisions': decisions}
    return baseline, current, report, ledger


def verify_payload(result: dict, observations: list[dict]) -> list[str]:
    """Check the frozen result against admitted typed observations, without reranking."""
    errors = []
    allowed = {}
    for obs in observations:
        if obs.get('metadata', {}).get('current_eligible') is not True:
            continue
        for swatch in obs.get('swatches', []):
            allowed[(obs['source_id'], obs['region']['region_id'], swatch['hex'])] = obs
    for candidate in result.get('challenger', []) + result.get('runner_ups', []):
        evidence = candidate.get('evidence', [])
        ids = [e.get('source_id') for e in evidence]
        if len(ids) != len(set(ids)) or candidate.get('source_count') != len(ids):
            errors.append('Candidate support is not one vote per source group.')
        if candidate.get('domain_count') != len({e.get('domain') for e in evidence}):
            errors.append('Candidate domain count disagrees with evidence.')
        for e in evidence:
            if (e.get('source_id'), e.get('region_id'), e.get('local_hex')) not in allowed:
                errors.append('Candidate contains evidence that was not admitted before scoring.')
        if candidate.get('hex') not in {e.get('local_hex') for e in evidence}:
            errors.append('Candidate representative is not an admitted local swatch.')
    if result.get('state') == 'ready':
        if not result.get('challenger'):
            errors.append('A ready result needs a Challenger.')
        for candidate in result.get('challenger', []):
            if not candidate.get('comparison', {}).get('valid'):
                errors.append('Public growth claims require a valid comparable cohort.')
            if candidate.get('trend_state') not in {'rising', 'spreading', 'surging', 'new'}:
                errors.append('A public Challenger must have measured growth.')
    return sorted(set(errors))


def verify_archive(day: Path) -> dict:
    result = json.loads((day / 'result.json').read_text())
    observations = json.loads((day / 'observations.json').read_text())
    manifest = json.loads((day / 'manifest.json').read_text())
    errors = verify_payload(result, observations)
    for filename in ['result.json', 'observations.json', 'evidence-admission.json', 'evidence-ledger.json']:
        expected = manifest.get('validated_sha256', {}).get(filename)
        if not expected or hashlib.sha256((day / filename).read_bytes()).hexdigest() != expected:
            errors.append(f'Validated file changed or was not recorded in the manifest: {filename}')
    if manifest.get('state') != result.get('state') or (day / 'workflow-state.txt').read_text().strip() != result.get('state'):
        errors.append('Publication states disagree.')
    if manifest.get('baseline_eligible') and result.get('state') == 'blocked':
        errors.append('Blocked result was admitted to baseline.')
    return {'schema_version': 2, 'passed': not errors, 'state': result.get('state'), 'errors': errors}
