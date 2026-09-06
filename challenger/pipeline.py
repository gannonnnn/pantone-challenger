from __future__ import annotations

import hashlib
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from challenger.baseline import load_history
from challenger.config import ROOT, load_settings, load_sources, source_is_configured
from challenger.color_truth import require_color_truth
from challenger.emergence import score_emergence, select_leaders
from challenger.image_quality import hash_distance
from challenger.models import DailyResult, Observation, PanelType, PublicationState
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
from challenger.signal_matrix import build_candidates
from challenger.sources.registry import build_adapter


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

    def run(self, run_date: str = "auto", max_sources: int = 0, rebuild: bool = False) -> DailyResult:
        date_value = self.resolve_date(run_date)
        archive_day = self.archive_dir / date_value
        if archive_day.exists() and not rebuild:
            raise FileExistsError(f"Archive already exists for {date_value}. Use --rebuild to replace it.")
        if archive_day.exists() and rebuild:
            shutil.rmtree(archive_day)
        run_work = self.work_dir / date_value
        if run_work.exists():
            shutil.rmtree(run_work)
        run_work.mkdir(parents=True)

        active, unconfigured = self._select_sources(date_value, max_sources)
        collection_results = self._collect(active, date_value)
        observations, extraction_report = self._extract_observations(collection_results, date_value)
        observations, duplicate_report = self._dedupe_cross_source(observations)
        history = load_history(
            self.archive_dir,
            date_value,
            int(self.settings.get("baseline", {}).get("history_days", 30)),
            compatibility_key=str(
                self.settings.get("baseline", {}).get("compatibility_key", "")
            ),
        )
        candidates = build_candidates(observations, date_value, self.settings)
        candidates = score_emergence(candidates, history, self.settings)
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
        evidence_sources = len({str(o.metadata.get("registry_source_id", o.source_id)) for o in observations})
        captured_base_sources = sum(bool(r.regions) for r in collection_results)
        benchmark_sources = len({str(o.metadata.get("registry_source_id", o.source_id)) for o in observations if o.panel_type == PanelType.BENCHMARK})
        discovery_sources = len({str(o.metadata.get("registry_source_id", o.source_id)) for o in observations if o.panel_type == PanelType.DISCOVERY})
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
        recurrence = recurrence_for_candidates(
            self.archive_dir, int(date_value[:4]), challenger, date_value
        ) if challenger else {}
        result = DailyResult(
            date=date_value,
            state=state,
            methodology_version=str(self.settings.get("methodology_version", "1.5.1")),
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
            reports={},
        )
        archive_day.mkdir(parents=True)
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
        return result

    def resolve_date(self, value: str) -> str:
        if value != "auto":
            datetime.strptime(value, "%Y-%m-%d")
            return value
        timezone = ZoneInfo(str(self.settings.get("timezone", "America/New_York")))
        return (datetime.now(timezone).date() - timedelta(days=1)).isoformat()

    def _select_sources(self, run_date: str, max_sources: int):
        enabled = [s for s in self.sources if s.enabled]
        configured = [s for s in enabled if source_is_configured(s)]
        unconfigured = [s for s in enabled if not source_is_configured(s)]
        benchmarks = [s for s in configured if s.panel_type == PanelType.BENCHMARK]
        discovery = [s for s in configured if s.panel_type == PanelType.DISCOVERY]
        per_run = int(self.settings.get("discovery", {}).get("sources_per_run", len(discovery)))
        # Stable daily rotation, distributed by domain rather than a global random draw.
        selected_discovery = []
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
            active = active[:max_sources]
        return active, unconfigured

    def _collect(self, active, run_date):
        workers = int(self.settings.get("capture", {}).get("workers", 4))
        results = []
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {
                executor.submit(build_adapter(s.adapter, self.work_dir, self.settings).collect, s, run_date): s
                for s in active
            }
            for future in as_completed(futures):
                source = futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:  # noqa: BLE001
                    from challenger.sources.base import CollectionResult

                    results.append(
                        CollectionResult(
                            source=source,
                            report={"status": "unhandled_error", "error": f"{type(exc).__name__}: {exc}"},
                        )
                    )
        return sorted(results, key=lambda r: r.source.id)

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
                if spec.adapter in ITEM_ADAPTERS and region.page_url:
                    digest = hashlib.sha256(region.page_url.encode()).hexdigest()[:12]
                    actor_id = f"{spec.id}:{digest}"
                    actor_name = region.page_title or spec.name
                    creator_id = region.page_url
                else:
                    actor_id = spec.id
                    actor_name = spec.name
                    creator_id = spec.creator_id or spec.id
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
                        captured_at=datetime.utcnow().isoformat() + "Z",
                        region=region,
                        swatches=swatches,
                        metadata={"registry_source_id": spec.id, "adapter": spec.adapter},
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
                "date": result.date,
                "state": result.state.value,
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
