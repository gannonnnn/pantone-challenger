from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from challenger.baseline import load_history
from challenger.evidence import prepare_evidence, verify_payload, verify_archive
from challenger.identity import observation_identity
from challenger.config import ROOT, load_settings, load_sources, source_is_configured
from challenger.color_truth import require_color_truth
from challenger.capture.browser import collect_browser_sources
from challenger.capture.api_batch import collect_api_sources
from challenger.emergence import score_emergence, select_leaders
from challenger.image_quality import hash_distance
from challenger.models import DailyResult, Observation, PanelType, PublicationState, EvidenceRegion
from challenger.palette import extract_palette
from challenger.quality import decide_state
from challenger.recurrence import recurrence_for_candidates
from challenger.regimes import calculate_regime, select_palette_pair
from challenger.render import render_daily
from challenger.reports import (
    write_color_proof_sheet,
    write_contact_sheet,
    write_json,
    write_summary,
)
from challenger.serialize import clean
from challenger.runtime import RuntimeLedger
from challenger.signal_matrix import build_candidates
from challenger.sources.base import CollectionResult


ITEM_ADAPTERS = {
    "rss",
    "met_open_access",
    "artic_open_access",
    "cleveland_open_access",
    "itunes_search",
    "musicbrainz_cover_art",
    "etsy",
    "ebay",
    "product_hunt",
    "submission_inbox",
}


def stage_diagnostics(collection_results, admission: dict) -> dict:
    """Count source groups, including failed collection and rejected dates."""
    result = {}
    decisions = admission.get('decisions', [])
    for stage in ('creation', 'distribution', 'attention'):
        sources = [r for r in collection_results if r.source.signal_stage.value == stage]
        ids = {r.source.id for r in sources}
        rows = [d for d in decisions if d.get('registry_source_id', d['source_id']) in ids]
        def source_ids(predicate):
            return sorted({d.get('registry_source_id', d['source_id']) for d in rows if predicate(d)})
        result[stage] = {
            'attempted_sources': len(ids),
            'captured_sources': len({r.source.id for r in sources if r.regions}),
            'admitted_sources': len(source_ids(lambda d: d['baseline_eligible'])),
            'current_sources': len(source_ids(lambda d: d['current_eligible'])),
            'undated_sources': source_ids(lambda d: 'undated' in d['temporal_status']),
            'stale_sources': source_ids(lambda d: d['temporal_status'] == 'context_only_stale'),
            'collection_failures': [{'source_id': r.source.id, 'status': r.report.get('status', 'unknown')}
                                    for r in sources if not r.regions],
            'admission': rows,
        }
    return result


class DailyPipeline:
    def __init__(
        self,
        *,
        settings_path: str | Path = "config/settings.yml",
        sources_path: str | Path = "config/sources.yml",
        archive_dir: str | Path = "archive",
        work_dir: str | Path = ".work",
    ):
        self.settings = load_settings(settings_path)
        self.registry_version, self.sources = load_sources(sources_path)
        self.archive_dir = Path(archive_dir)
        self.work_dir = Path(work_dir)
        if not self.archive_dir.is_absolute():
            self.archive_dir = ROOT / self.archive_dir
        if not self.work_dir.is_absolute():
            self.work_dir = ROOT / self.work_dir

    def run(self, run_date: str = "auto", max_sources: int = 0, rebuild: bool = False, resume: bool = False) -> DailyResult:
        date_value = self.resolve_date(run_date)
        if date_value != self.resolve_date("auto"):
            raise ValueError("Live collection must use today's observation date (auto). Historical dates require original saved evidence; changing the date cannot recreate yesterday's webpage.")
        final_day = self.archive_dir / date_value
        if final_day.exists() and not rebuild:
            raise FileExistsError(f"Archive already exists for {date_value}. Inspect it before using --rebuild.")
        run_work = self.work_dir / date_value
        if run_work.exists() and not resume:
            shutil.rmtree(run_work)
        run_work.mkdir(parents=True, exist_ok=True)
        archive_day = run_work / "result-stage"
        if archive_day.exists():
            shutil.rmtree(archive_day)
        self._run_work = run_work
        self._resume = resume
        active, unconfigured = self._select_sources(date_value, max_sources)
        session = {"date": date_value, "settings": self.settings, "sources": [clean(s) for s in active]}
        session_key = hashlib.sha256(json.dumps(session, sort_keys=True).encode()).hexdigest()
        session_path = run_work / "session.json"
        if resume and session_path.exists() and json.loads(session_path.read_text()).get("key") != session_key:
            raise ValueError("Resume settings or selected sources changed. Use a fresh collection.")
        write_json(session_path, {"key": session_key, "date": date_value})
        ledger = RuntimeLedger(run_work, total_sources=len(active))
        try:
            ledger.start_phase("collection")
            collection_results = self._collect(active, date_value, ledger)
            ledger.end_phase("collection")

            ledger.start_phase("palette extraction")
            observations, extraction_report = self._extract_observations(collection_results, date_value)
            ledger.end_phase("palette extraction")

            ledger.start_phase("dedupe and scoring")
            observations, current_observations, self._admission, self._evidence_ledger = prepare_evidence(
                observations, date_value, self.settings, self.archive_dir)
            current_observations, duplicate_report = self._dedupe_cross_source(current_observations)
            history = load_history(
                self.archive_dir,
                date_value,
                int(self.settings.get("baseline", {}).get("history_days", 30)),
                compatibility_key=str(
                    self.settings.get("baseline", {}).get("compatibility_key", "")
                ),
            )
            candidates = build_candidates(current_observations, date_value, self.settings)
            candidates = score_emergence(candidates, history, self.settings, [clean(o) for o in observations])
            challenger, undercurrent, mainstream, usage, runners = select_leaders(
                candidates, self.settings, len(history)
            )
            regime = calculate_regime(observations)
            pair = select_palette_pair(
                regime, float(self.settings.get("palette_pairs", {}).get("min_score", 0.20))
            )
            domains = len({o.domain.value for o in observations})
            sectors = len({o.sector for o in observations})
            stages = len({o.signal_stage.value for o in observations})
            evidence_sources = len(
                {str(o.metadata.get("registry_source_id", o.source_id)) for o in observations}
            )
            captured_base_sources = sum(bool(r.regions) for r in collection_results)
            benchmark_sources = len(
                {
                    str(o.metadata.get("registry_source_id", o.source_id))
                    for o in observations
                    if o.panel_type == PanelType.BENCHMARK
                }
            )
            discovery_sources = len(
                {
                    str(o.metadata.get("registry_source_id", o.source_id))
                    for o in observations
                    if o.panel_type == PanelType.DISCOVERY
                }
            )
            state, blocking, review = decide_state(
                active_sources=len(active),
                attempted_sources=len(active),
                captured_sources=captured_base_sources,
                evidence_sources=evidence_sources,
                domains=domains,
                stages=stages,
                challenger=challenger,
                observations=observations,
                baseline_days=len(history),
                settings=self.settings,
            )
            recurrence = (
                recurrence_for_candidates(
                    self.archive_dir, int(date_value[:4]), challenger, date_value,
                    compatibility_key=self.settings.get("baseline", {}).get("compatibility_key", "")
                )
                if challenger and state == PublicationState.READY
                else {}
            )
            ledger.end_phase("dedupe and scoring")

            runtime_snapshot = ledger.snapshot()
            result = DailyResult(
                date=date_value,
                state=state,
                methodology_version=str(self.settings.get("methodology_version", "1.6.1")),
                registry_version=self.registry_version,
                panel_declared=len(active),
                sources_attempted=len(active),
                sources_captured=captured_base_sources,
                sources_with_eligible_evidence=evidence_sources,
                domains_covered=domains,
                sectors_covered=sectors,
                stages_covered=stages,
                benchmark_sources=benchmark_sources,
                discovery_sources=discovery_sources,
                challenger=challenger,
                undercurrent=undercurrent,
                mainstream_leader=mainstream,
                usage_leader=usage,
                runner_ups=runners,
                palette_regime=regime,
                palette_pair=pair,
                blocking_reasons=blocking,
                review_reasons=review,
                baseline_days=len(history),
                recurrence=recurrence,
                reports={
                    "runtime_elapsed_seconds": str(runtime_snapshot.get("elapsed_seconds", 0)),
                    "current_evidence_sources": str(len({o.metadata["registry_source_id"] for o in current_observations})),
                    "observation_date_basis": "Live capture date in the configured timezone; dated items use the stated current window.",
                    "runtime_timed_out_sources": str(
                        len(runtime_snapshot.get("timed_out_sources", []))
                    ),
                    "runtime_status_counts": str(runtime_snapshot.get("status_counts", {})),
                },
            )
            errors = verify_payload(result.to_dict(), [clean(o) for o in observations])
            if errors:
                raise ValueError("Frozen result failed validation: " + "; ".join(errors))
            archive_day.mkdir(parents=True)
            ledger.start_phase("render and reports")
            self._write_outputs(
                result=result,
                observations=observations,
                collection_results=collection_results,
                extraction_report=extraction_report,
                duplicate_report=duplicate_report,
                unconfigured=unconfigured,
                candidates=candidates,
                archive_day=archive_day,
                run_work=run_work,
            )
            ledger.end_phase("render and reports")
            final_runtime = ledger.finalize(
                status="complete",
                extra={
                    "publication_state": result.state.value,
                    "eligible_evidence_sources": evidence_sources,
                    "candidate_count": len(candidates),
                },
            )
            result.reports["runtime_elapsed_seconds"] = str(
                final_runtime.get("elapsed_seconds", 0)
            )
            result.reports["runtime_timed_out_sources"] = str(
                len(final_runtime.get("timed_out_sources", []))
            )
            result.reports["runtime_status_counts"] = str(
                final_runtime.get("status_counts", {})
            )
            write_json(archive_day / "result.json", self._public_result(result))
            write_summary(archive_day / "review-summary.md", result)
            manifest_path = archive_day / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["validated_sha256"] = {
                name: hashlib.sha256((archive_day / name).read_bytes()).hexdigest()
                for name in ["result.json", "observations.json", "evidence-admission.json", "evidence-ledger.json"]
            }
            manifest["public_files"] = sorted(p.name for p in archive_day.iterdir() if p.is_file())
            write_json(manifest_path, manifest)
            verification = verify_archive(archive_day)
            write_json(archive_day / "temporal-semantic-integrity.json", verification)
            if not verification["passed"]:
                raise ValueError("Archive verification failed: " + "; ".join(verification["errors"]))
            final_day.parent.mkdir(parents=True, exist_ok=True)
            backup = run_work / "previous-result"
            if backup.exists():
                shutil.rmtree(backup)
            if final_day.exists():
                os.replace(final_day, backup)
            try:
                os.replace(archive_day, final_day)
            except BaseException:
                if backup.exists():
                    os.replace(backup, final_day)
                raise
            return result
        except BaseException as exc:
            ledger.fail(exc)
            raise

    def resolve_date(self, value: str) -> str:
        if value != "auto":
            datetime.strptime(value, "%Y-%m-%d")
            return value
        timezone = ZoneInfo(str(self.settings.get("timezone", "America/New_York")))
        return datetime.now(timezone).date().isoformat()

    def _select_sources(self, run_date: str, max_sources: int):
        enabled = [s for s in self.sources if s.enabled]
        configured = [s for s in enabled if source_is_configured(s)]
        unconfigured = [s for s in enabled if not source_is_configured(s)]
        benchmarks = [s for s in configured if s.panel_type == PanelType.BENCHMARK]
        discovery = [s for s in configured if s.panel_type == PanelType.DISCOVERY]
        per_run = int(self.settings.get("discovery", {}).get("sources_per_run", len(discovery)))
        # Stable daily rotation, distributed by domain rather than a global random draw.
        selected_discovery = [s for s in discovery if s.options.get('always_sample') is True]
        if len(selected_discovery) > per_run:
            raise ValueError('Always-sampled discovery sources exceed the daily discovery limit.')
        by_domain = {}
        for source in discovery:
            by_domain.setdefault(source.domain.value, []).append(source)
        while len(selected_discovery) < min(per_run, len(discovery)):
            changed = False
            for domain in sorted(by_domain):
                pool = sorted(
                    by_domain[domain],
                    key=lambda s: hashlib.sha256(f"{run_date}:{s.id}".encode()).hexdigest(),
                )
                next_item = next((s for s in pool if s not in selected_discovery), None)
                if next_item:
                    selected_discovery.append(next_item)
                    changed = True
                    if len(selected_discovery) >= min(per_run, len(discovery)):
                        break
            if not changed:
                break
        active = benchmarks + selected_discovery
        if max_sources > 0:
            # A small diagnostic run covers both panels instead of only the first brands.
            active = sorted(active, key=lambda s: hashlib.sha256(f"smoke:{run_date}:{s.id}".encode()).hexdigest())[:max_sources]
        return active, unconfigured

    def _collect(self, active, run_date, ledger: RuntimeLedger):
        browser_sources = [source for source in active if source.adapter == "webpage"]
        adapter_sources = [source for source in active if source.adapter != "webpage"]
        results_by_id: dict[str, CollectionResult] = {}
        workdir = getattr(self, "_run_work", self.work_dir / run_date)
        workdir.mkdir(parents=True, exist_ok=True)
        checkpoint = workdir / "collection-progress.json"
        if getattr(self, "_resume", False) and checkpoint.exists():
            saved = json.loads(checkpoint.read_text())
            source_map = {source.id: source for source in active}
            for entry in saved:
                source = source_map.get(entry.get("source_id"))
                if not source or entry.get("report", {}).get("status") != "captured":
                    continue
                try:
                    regions = [EvidenceRegion(**r) for r in entry.get("regions", [])]
                    valid = regions and all(Path(r.screenshot_path).is_file()
                        and Path(r.screenshot_path).resolve().is_relative_to(workdir.resolve())
                        and hashlib.sha256(Path(r.screenshot_path).read_bytes()).hexdigest() == r.metadata.get("file_sha256")
                        for r in regions)
                    if not valid:
                        continue
                    results_by_id[source.id] = CollectionResult(source=source, regions=regions, report=entry["report"])
                    ledger.record_source(source_id=source.id, source_name=source.name, adapter=source.adapter,
                                         status="reused_capture", regions=len(regions), duration_seconds=0.0)
                except (TypeError, ValueError, OSError):
                    continue
            browser_sources = [s for s in browser_sources if s.id not in results_by_id]
            adapter_sources = [s for s in adapter_sources if s.id not in results_by_id]
        lock = threading.Lock()

        def record(result: CollectionResult, duration_seconds: float) -> None:
            source = result.source
            with lock:
                if source.id in results_by_id:
                    return
                for region in result.regions:
                    if not region.captured_at:
                        region.captured_at = datetime.now(timezone.utc).isoformat()
                    path = Path(region.screenshot_path)
                    if path.is_file():
                        region.metadata["file_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                        region.metadata["artifact_path"] = str(path.resolve().relative_to(workdir.resolve()))
                results_by_id[source.id] = result
                write_json(checkpoint, [{"source_id": r.source.id, "report": r.report,
                                        "regions": [clean(region) for region in r.regions]}
                                       for r in results_by_id.values()])
            status = str(result.report.get("status", "unknown"))
            error = str(result.report.get("error", ""))
            ledger.record_source(
                source_id=source.id,
                source_name=source.name,
                adapter=source.adapter,
                status=status,
                regions=len(result.regions),
                duration_seconds=duration_seconds,
                error=error,
            )

        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pc-api-supervisor")
        api_future = executor.submit(collect_api_sources, adapter_sources, run_date, workdir, self.settings, record)

        try:
            collect_browser_sources(
                browser_sources,
                run_date,
                workdir,
                self.settings,
                progress_callback=record,
                heartbeat_callback=lambda _done, active_count, pending_count, _elapsed: ledger.heartbeat(
                    active=active_count,
                    pending=pending_count + max(0, len(active) - ledger.completed_sources - active_count),
                    label="web collection",
                ),
            )
        except Exception as exc:  # noqa: BLE001
            for source in browser_sources:
                if source.id not in results_by_id:
                    record(
                        CollectionResult(
                            source=source,
                            report={
                                "status": "browser_batch_error",
                                "error": f"{type(exc).__name__}: {exc}"[:500],
                            },
                        ),
                        0.0,
                    )
        finally:
            try:
                api_future.result()
            finally:
                executor.shutdown(wait=True, cancel_futures=True)

        for source in active:
            if source.id not in results_by_id:
                record(
                    CollectionResult(
                        source=source,
                        report={
                            "status": "missing_result",
                            "error": "No collector result was returned for this source.",
                        },
                    ),
                    0.0,
                )
        return sorted(results_by_id.values(), key=lambda result: result.source.id)

    def _extract_observations(self, collection_results, run_date):
        observations = []
        report = []
        for result in collection_results:
            spec = result.source
            for region in result.regions:
                try:
                    swatches = extract_palette(
                        region.screenshot_path,
                        colors=int(self.settings.get("palette", {}).get("colors_per_region", 7)),
                        neutral_chroma=float(self.settings.get("palette", {}).get("neutral_chroma", 0.035)),
                    )
                except Exception as exc:  # noqa: BLE001
                    report.append({"source_id": spec.id, "region_id": region.region_id, "status": "palette_error", "error": str(exc)})
                    continue
                if not swatches:
                    report.append({"source_id": spec.id, "region_id": region.region_id, "status": "empty_palette"})
                    continue
                identity = observation_identity(spec, region, item_adapter=spec.adapter in ITEM_ADAPTERS)
                actor_id, actor_name, creator_id = identity["actor_id"], identity["actor_name"], identity["creator_id"]
                observations.append(
                    Observation(
                        source_id=actor_id,
                        source_name=actor_name,
                        domain=spec.domain,
                        sector=spec.sector,
                        signal_stage=spec.signal_stage,
                        scale_class=spec.scale_class,
                        panel_type=spec.panel_type,
                        event_type=spec.event_type,
                        geography=spec.geography,
                        rights_mode=spec.rights_mode,
                        platform=spec.platform or spec.id,
                        creator_id=creator_id,
                        captured_at=region.captured_at or datetime.now(timezone.utc).isoformat(),
                        region=region,
                        swatches=swatches,
                        metadata={**identity, "adapter": spec.adapter,
                                  'temporal_policy': spec.options.get('temporal_evidence', {})},
                    )
                )
                report.append(
                    {
                        "source_id": actor_id,
                        "region_id": region.region_id,
                        "status": "accepted",
                        "swatch_count": len(swatches),
                        "swatches": [clean(swatch) for swatch in swatches],
                    }
                )
        return observations, report

    def _dedupe_cross_source(self, observations):
        accepted = []
        removed = []
        exact = {}
        for obs in sorted(observations, key=lambda o: o.region.confidence, reverse=True):
            h = obs.region.content_hash
            if h and h in exact:
                removed.append({"source_id": obs.source_id, "duplicate_of": exact[h].source_id, "reason": "exact_campaign_duplicate"})
                continue
            near = None
            if obs.region.perceptual_hash:
                for other in accepted:
                    if not other.region.perceptual_hash:
                        continue
                    if hash_distance(obs.region.perceptual_hash, other.region.perceptual_hash) <= int(
                        self.settings.get("dedupe", {}).get("cross_source_phash_distance", 6)
                    ):
                        near = other
                        break
            if near:
                removed.append({"source_id": obs.source_id, "duplicate_of": near.source_id, "reason": "near_campaign_duplicate"})
                continue
            accepted.append(obs)
            if h:
                exact[h] = obs
        return accepted, removed

    def _write_outputs(
        self,
        *,
        result,
        observations,
        collection_results,
        extraction_report,
        duplicate_report,
        unconfigured,
        candidates,
        archive_day,
        run_work,
    ):
        source_map = {s.id: s for s in self.sources}
        color_truth_report = require_color_truth(observations, candidates)
        write_json(run_work / "color-truth-audit.json", color_truth_report)
        public_color_truth = {
            "passed": bool(color_truth_report.get("passed")),
            "evidence_images_checked": int(color_truth_report.get("evidence_images_checked", 0)),
            "extracted_swatches_checked": int(color_truth_report.get("extracted_swatches_checked", 0)),
            "candidate_count_checked": int(color_truth_report.get("candidate_count_checked", 0)),
            "candidate_evidence_records_checked": int(
                color_truth_report.get("candidate_evidence_records_checked", 0)
            ),
            "rule": "Every extracted and candidate HEX must exist in decoded source pixels.",
        }
        result.reports["color_truth"] = "passed"
        result.reports["color_truth_swatches_checked"] = str(
            public_color_truth["extracted_swatches_checked"]
        )
        write_json(archive_day / "color-integrity.json", public_color_truth)
        write_json(archive_day / "evidence-admission.json", self._admission)
        write_json(archive_day / "evidence-ledger.json", self._evidence_ledger)
        diagnostics = stage_diagnostics(collection_results, self._admission)
        write_json(archive_day / 'stage-diagnostics.json', diagnostics)
        write_json(run_work / 'stage-diagnostics.json', diagnostics)
        result.reports['stage_diagnostics'] = json.dumps(diagnostics)
        render_daily(result, archive_day, source_map, self.settings)
        result_payload = self._public_result(result)
        write_json(archive_day / "result.json", result_payload)
        write_json(archive_day / "observations.json", [self._observation_record(o) for o in observations])
        write_json(archive_day / "palette-regime.json", result.palette_regime)
        write_summary(archive_day / "review-summary.md", result)
        write_json(
            run_work / "collection-report.json",
            [
                {
                    "source": clean(r.source),
                    "report": r.report,
                    "regions": [clean(region) for region in r.regions],
                }
                for r in collection_results
            ],
        )
        write_json(run_work / "extraction-report.json", extraction_report)
        write_json(run_work / "duplicate-campaign-report.json", duplicate_report)
        write_json(run_work / "candidate-report.json", [clean(c) for c in candidates])
        write_json(run_work / "unconfigured-sources.json", [clean(s) for s in unconfigured])
        if candidates:
            write_contact_sheet(
                run_work / "evidence-contact-sheet.png",
                candidates[:4],
                f"Pantone Challenger private evidence — {result.date}",
            )
            write_color_proof_sheet(
                run_work / "color-proof-sheet.png",
                candidates[:4],
                f"Pantone Challenger color proof — {result.date}",
                threshold=float(
                    self.settings.get("clustering", {}).get("proof_mask_distance", 0.035)
                ),
            )
        write_json(
            archive_day / "manifest.json",
            {
                "schema_version": 2,
                "date": result.date,
                "state": result.state.value,
                "baseline_eligible": result.state != PublicationState.BLOCKED and bool(observations),
                "baseline_reason": "Admitted observations passed collection quality and pre-score integrity." if result.state != PublicationState.BLOCKED else "Collection or evidence quality blocked this day.",
                "methodology_version": result.methodology_version,
                "registry_version": result.registry_version,
                "public_files": sorted(p.name for p in archive_day.iterdir() if p.is_file()),
                "private_artifact_path": str(run_work),
                "baseline_compatibility_key": str(
                    self.settings.get("baseline", {}).get("compatibility_key", "")
                ),
            },
        )
        (archive_day / "workflow-state.txt").write_text(result.state.value + "\n", encoding="utf-8")

    def _observation_record(self, obs: Observation):
        payload = clean(obs)
        # Baseline history needs colors and provenance, not a runner-local filesystem path.
        payload["region"]["screenshot_path"] = f"private-evidence:{obs.region.region_id}"
        return payload

    def _public_result(self, result: DailyResult):
        payload = result.to_dict()
        payload["baseline_compatibility_key"] = str(
            self.settings.get("baseline", {}).get("compatibility_key", "")
        )
        for key in ["challenger", "runner_ups"]:
            for candidate in payload.get(key, []):
                for evidence in candidate.get("evidence", []):
                    evidence["region_path"] = f"private-evidence:{evidence.get('region_id', '')}"
        for key in ["undercurrent", "mainstream_leader", "usage_leader"]:
            candidate = payload.get(key)
            if candidate:
                for evidence in candidate.get("evidence", []):
                    evidence["region_path"] = f"private-evidence:{evidence.get('region_id', '')}"
        return payload
