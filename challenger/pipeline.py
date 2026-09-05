from __future__ import annotations

import shutil
from pathlib import Path

from .archive import write_analysis_archive, write_manifest, write_publish_package
from .capture import capture_panel, load_capture_report
from .config import load_settings, load_source_panel
from .dates import iso_now, resolve_marketing_date
from .dedupe import deduplicate_records
from .evidence import observation_from_capture
from .integrity import validate_result_integrity
from .models import CaptureRecord, DailyResult, Source, SourceObservation
from .naming import candidate_labels
from .recurrence import calculate_recurrence
from .render import render_daily, render_evidence_contact_sheet
from .scoring import (
    confidence_label,
    evaluate_quality,
    load_history,
    publication_state,
    score_candidates,
    select_daily_candidates,
    select_distinct_runners,
)
from .site import build_site


DISCLAIMER = (
    "Pantone Challenger is an independent computational art project and is not "
    "affiliated with, sponsored by, or endorsed by Pantone LLC. The index measures "
    "a declared panel of official marketing pages, not the entire internet. Company "
    "names identify monitored sources and do not imply endorsement."
)


def _balanced_limit(sources: list[Source], maximum: int) -> list[Source]:
    if maximum <= 0 or maximum >= len(sources):
        return list(sources)
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
    settings,
) -> list[SourceObservation]:
    observations: list[SourceObservation] = []
    for record in records:
        # Dedupe, challenge-page, and capture failures remain available in the
        # private report, but they must never cast a color vote.
        if not record.success:
            continue
        observation = observation_from_capture(record, settings)
        if observation is None:
            record.success = False
            if not record.error:
                record.error = (
                    "Capture did not produce traceable color evidence from an eligible "
                    "marketing-creative region"
                )
            continue
        record.success = True
        observations.append(observation)
    return observations


def _label_candidates(candidates, target) -> None:
    for candidate in candidates:
        family, creative, _ = candidate_labels(candidate, target)
        candidate.family_label = family
        candidate.creative_name = creative


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
    registry_version, all_sources = load_source_panel(config_dir)
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
    history = load_history(
        archive_root,
        target,
        settings.baseline_lookback_days,
        methodology_version=settings.methodology_version,
    )
    raw_candidates = score_candidates(observations, sources, history, settings)
    candidates = select_daily_candidates(raw_candidates, len(history), settings)

    # Recalculate margins after non-display neutrals have been removed.
    for index, candidate in enumerate(candidates):
        next_score = candidates[index + 1].score if index + 1 < len(candidates) else 0.0
        candidate.score_margin_to_next = round(candidate.score - next_score, 3)

    gate = evaluate_quality(candidates, observations, sources, settings)
    if raw_candidates and not candidates:
        message = (
            "The detected clusters were near-neutral page infrastructure rather than a "
            "qualified commercial color signal."
        )
        if message not in gate.reasons:
            gate.reasons.append(message)
        gate.passed = False
        gate.state = "blocked"

    limited_panel = 0 < max_sources < len(all_sources)
    if limited_panel:
        gate.passed = False
        gate.state = "blocked"
        gate.reasons.append(
            "This run used a limited panel. Limited-panel runs are engineering checks and "
            "cannot create an official or calibration result."
        )

    state = publication_state(gate, len(history), settings)
    result_confidence = confidence_label(candidates[0] if candidates else None, state)
    winner = candidates[0] if candidates else None
    runners = (
        select_distinct_runners(winner, candidates[1:], settings)
        if winner is not None and state != "blocked"
        else []
    )
    _label_candidates([candidate for candidate in [winner, *runners] if candidate], target)

    winner_name: str | None = None
    runner_names: list[str] = []
    if winner:
        _, _, winner_name = candidate_labels(winner, target)
        winner.confidence = confidence_label(winner, state)
    for runner in runners:
        _, _, display = candidate_labels(runner, target)
        runner.confidence = "Calibration" if state == "review_only" else "Moderate"
        runner_names.append(display)

    recurrence = (
        calculate_recurrence(
            archive_root=archive_root,
            target_date=target,
            winner=winner,
            panel_size=len(all_sources),
            captured_sources=len(observations),
            distance_threshold=settings.recurrence_distance,
        )
        if state == "ready" and winner
        else None
    )

    source_failures = [
        {
            "source_id": record.source_id,
            "source_name": record.source_name,
            "error": record.error or "Capture did not produce eligible creative evidence",
        }
        for record in captures
        if not record.success
    ]
    result = DailyResult(
        date=target.isoformat(),
        generated_at=iso_now(settings.timezone),
        project=settings.project_name,
        methodology_version=settings.methodology_version,
        panel_size=len(all_sources),
        captured_sources=len(observations),
        captured_sectors=len({item.sector for item in observations}),
        baseline_days=len(history),
        status=state,
        confidence_label=result_confidence,
        quality_gate=gate,
        winner=winner,
        winner_name=winner_name,
        runners_up=runners,
        source_failures=source_failures,
        disclaimer=DISCLAIMER,
        runner_up_names=runner_names,
        recurrence=recurrence,
        registry_version=registry_version,
        calibration_day=(
            min(len(history) + 1, settings.calibration_days)
            if state == "review_only"
            else 0
        ),
    )

    validate_result_integrity(result, sources, settings)
    day_dir = write_analysis_archive(
        archive_root,
        result,
        observations,
        captures,
        sources=sources,
        project_root=config_dir.parent,
    )
    validate_result_integrity(result, sources, settings)

    assets = render_daily(result, day_dir)
    review_dir = work_root / "review" / target.isoformat()
    if review_dir.exists():
        shutil.rmtree(review_dir)
    review_dir.mkdir(parents=True, exist_ok=True)
    if winner:
        render_evidence_contact_sheet(result, review_dir / "evidence-contact-sheet.png")

    write_publish_package(day_dir, result, assets)
    write_manifest(day_dir)
    build_site(archive_root, site_root, all_sources)
    return result
