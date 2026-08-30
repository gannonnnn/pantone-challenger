from __future__ import annotations

import shutil
from pathlib import Path

from .archive import (
    write_analysis_archive,
    write_manifest,
    write_publish_package,
)
from .capture import capture_panel, load_capture_report
from .colors import extract_palette
from .config import Settings, load_settings, load_sources
from .dates import iso_now, resolve_marketing_date
from .dedupe import deduplicate_records
from .models import CaptureRecord, DailyResult, Source, SourceObservation
from .naming import name_candidate
from .recurrence import calculate_recurrence
from .render import render_daily
from .scoring import evaluate_quality, load_history, score_candidates
from .site import build_site


DISCLAIMER = (
    "Pantone Challenger is an independent computational art project and is not "
    "affiliated with, sponsored by, or endorsed by Pantone LLC. The index measures "
    "a declared panel of official marketing pages, not the entire internet."
)


def _balanced_limit(sources: list[Source], maximum: int) -> list[Source]:
    if maximum <= 0 or maximum >= len(sources):
        return sources
    buckets: dict[str, list[Source]] = {}
    for source in sources:
        buckets.setdefault(source.sector, []).append(source)
    selected: list[Source] = []
    while len(selected) < maximum:
        changed = False
        for sector in sorted(buckets):
            if buckets[sector] and len(selected) < maximum:
                selected.append(buckets[sector].pop(0))
                changed = True
        if not changed:
            break
    return selected




def observations_from_captures(
    records: list[CaptureRecord],
    settings: Settings,
) -> list[SourceObservation]:
    observations: list[SourceObservation] = []
    for record in records:
        if not record.success or not record.frames:
            continue
        paths = [Path(frame.path) for frame in record.frames if Path(frame.path).exists()]
        if not paths:
            record.success = False
            record.error = "No captured frames remained available for analysis"
            continue
        try:
            swatches = extract_palette(
                paths,
                merge_distance=settings.source_cluster_distance,
            )
        except Exception as exc:
            record.success = False
            record.error = f"Color extraction failed: {type(exc).__name__}: {exc}"
            continue
        if len(swatches) < 2:
            record.success = False
            record.error = "Color extraction produced fewer than two usable swatches"
            continue
        observations.append(
            SourceObservation(
                source_id=record.source_id,
                source_name=record.source_name,
                sector=record.sector,
                url=record.final_url or record.url,
                captured_at=record.captured_at,
                screenshot_hashes=[frame.sha256 for frame in record.frames],
                swatches=swatches,
            )
        )
    return observations


def run_daily(
    *,
    requested_date: str = "auto",
    config_dir: Path = Path("config"),
    archive_root: Path = Path("archive"),
    work_root: Path = Path(".work"),
    site_root: Path = Path("site"),
    max_sources: int = 0,
    force: bool = False,
    reuse_capture: bool = False,
) -> DailyResult:
    settings = load_settings(config_dir)
    all_sources = load_sources(config_dir)
    sources = _balanced_limit(all_sources, max_sources)
    target = resolve_marketing_date(
        requested_date,
        timezone_name=settings.timezone,
        rollover_hour=settings.rollover_hour,
    )
    day_dir = archive_root / target.isoformat()
    if day_dir.exists() and not force:
        raise FileExistsError(
            f"{day_dir} already exists. Pass --force only when intentionally rebuilding "
            "the same marketing day."
        )
    if day_dir.exists() and force:
        shutil.rmtree(day_dir)

    capture_dir = work_root / "captures" / target.isoformat()
    report_path = capture_dir / "capture-report.json"
    if reuse_capture:
        if not report_path.exists():
            raise FileNotFoundError(f"No existing capture report found at {report_path}")
        captures = load_capture_report(report_path)
    else:
        if capture_dir.exists():
            shutil.rmtree(capture_dir)
        captures = capture_panel(sources, capture_dir, settings)

    deduplicate_records(captures)
    observations = observations_from_captures(captures, settings)
    history = load_history(archive_root, target, settings.baseline_lookback_days)
    candidates = score_candidates(observations, sources, history, settings)
    gate = evaluate_quality(candidates, observations, sources, settings)
    if 0 < max_sources < len(all_sources):
        gate.passed = False
        gate.reasons.append(
            "This run used a limited live panel. Limited-panel runs are engineering "
            "checks and can never create a publishable daily result."
        )
    winner = candidates[0] if candidates else None
    status = "ready" if gate.passed and winner else "blocked"
    name = name_candidate(winner, target) if status == "ready" and winner else None
    runner_up_names = (
        [name_candidate(candidate, target) for candidate in candidates[1:4]]
        if status == "ready"
        else []
    )
    recurrence = (
        calculate_recurrence(
            archive_root=archive_root,
            target_date=target,
            winner=winner,
            panel_size=len(sources),
            captured_sources=len(observations),
            distance_threshold=settings.recurrence_distance,
        )
        if status == "ready" and winner
        else None
    )
    source_failures = [
        {
            "source_id": record.source_id,
            "source_name": record.source_name,
            "error": record.error or "Capture did not produce usable evidence",
        }
        for record in captures
        if not record.success
    ]
    result = DailyResult(
        date=target.isoformat(),
        generated_at=iso_now(settings.timezone),
        project=settings.project_name,
        methodology_version=settings.methodology_version,
        panel_size=len(sources),
        captured_sources=len(observations),
        captured_sectors=len({item.sector for item in observations}),
        baseline_days=len(history),
        status=status,
        quality_gate=gate,
        winner=winner,
        winner_name=name,
        runners_up=candidates[1:4],
        source_failures=source_failures,
        disclaimer=DISCLAIMER,
        runner_up_names=runner_up_names,
        recurrence=recurrence,
    )

    day_dir = write_analysis_archive(archive_root, result, observations, captures)
    assets = render_daily(result, day_dir)
    write_publish_package(day_dir, result, assets)
    write_manifest(day_dir)
    build_site(archive_root, site_root, all_sources)
    return result
