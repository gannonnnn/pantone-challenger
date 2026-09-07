from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from PIL import Image

from challenger.temporal_semantic_integrity import (
    CandidateInfo,
    _load_config,
    _mask_component_stats,
    _temporal_status,
    _tie_analysis,
    run_integrity,
)


def test_future_dated_url_is_rejected(tmp_path: Path) -> None:
    cfg = _load_config(tmp_path)
    record = {
        "source_id": "future-news",
        "source_name": "Future News",
        "source_url": "https://example.com/2026/09/06/new-palette",
        "domain": "art",
        "signal_stage": "creation",
        "panel_type": "discovery",
        "event_type": "newly_published",
    }
    status, reasons, *_ = _temporal_status(record, date(2026, 9, 5), {"sources": {}}, "abc", cfg)
    assert status == "rejected_future"
    assert "after the requested cultural date" in reasons[0]


def test_undated_historical_art_is_context_only(tmp_path: Path) -> None:
    cfg = _load_config(tmp_path)
    record = {
        "source_id": "museum-work",
        "source_name": "Museum Work",
        "domain": "art",
        "signal_stage": "creation",
        "panel_type": "discovery",
        "event_type": "permanent_collection",
    }
    status, reasons, *_ = _temporal_status(record, date(2026, 9, 5), {"sources": {}}, "abc", cfg)
    assert status == "context_only_historical"
    assert any("current dated" in reason for reason in reasons)


def test_unchanged_undated_benchmark_is_baseline_only(tmp_path: Path) -> None:
    cfg = _load_config(tmp_path)
    record = {
        "source_id": "brand",
        "source_name": "Brand",
        "domain": "marketing",
        "signal_stage": "distribution",
        "panel_type": "benchmark",
    }
    prior = {"sources": {"brand": {"fingerprint": "same", "first_seen": "2026-09-01", "last_changed": "2026-09-01"}}}
    status, reasons, *_ = _temporal_status(record, date(2026, 9, 5), prior, "same", cfg)
    assert status == "baseline_only_unchanged"
    assert any("unchanged" in reason.lower() for reason in reasons)


def test_connected_area_rejects_sparse_color(tmp_path: Path) -> None:
    cfg = _load_config(tmp_path)
    image = Image.new("RGB", (200, 200), "white")
    pixels = image.load()
    for i in range(30):
        pixels[(i * 37) % 200, (i * 53) % 200] = (137, 117, 93)
    path = tmp_path / "sparse.png"
    image.save(path)
    total, component = _mask_component_stats(path, "#89755D", cfg) or (1.0, 1.0)
    assert total < cfg["muted_minimum_total_color_share"]
    assert component < cfg["muted_minimum_component_share"]


def test_connected_area_accepts_deliberate_color_field(tmp_path: Path) -> None:
    cfg = _load_config(tmp_path)
    image = Image.new("RGB", (200, 200), "white")
    for y in range(40, 160):
        for x in range(30, 170):
            image.putpixel((x, y), (137, 117, 93))
    path = tmp_path / "field.png"
    image.save(path)
    total, component = _mask_component_stats(path, "#89755D", cfg) or (0.0, 0.0)
    assert total > 0.30
    assert component > 0.30


def test_ties_are_evaluated_after_eligibility(tmp_path: Path) -> None:
    cfg = _load_config(tmp_path)
    candidates = [
        CandidateInfo("Brown", "#89755D", 99.2, 15, 7, 8, 0.02),
        CandidateInfo("Gray", "#777777", 98.8, 20, 10, 10, 0.01),
        CandidateInfo("Blue", "#115BB9", 95.7, 8, 5, 6, 0.02),
    ]
    result = _tie_analysis(candidates, candidates[0], cfg)
    assert result["is_tie"] is False
    assert result["second"]["hex"] == "#115BB9"
    assert result["score_delta"] > cfg["tie_score_delta"]


def test_run_integrity_blocks_wide_muted_cluster_and_suppresses_emergence(tmp_path: Path) -> None:
    archive = tmp_path / "archive" / "2026-09-05"
    archive.mkdir(parents=True)
    (archive / "workflow-state.txt").write_text("review_only\n", encoding="utf-8")
    (archive / "review-summary.md").write_text(
        """# Pantone Challenger — 2026-09-05

State: `review_only`
Coverage: 36 / 58 active sources
Historical baseline: 0 prior valid days

## Challenger

- CULTURAL SIGNAL BROWN #89755D — 15 sources, 7 domains, emergence 99.2, cluster diameter: 0.04848

- The leading score is close to the next candidate; treat as review-only unless a tie is selected.
""",
        encoding="utf-8",
    )
    report = run_integrity(tmp_path, date(2026, 9, 5))
    assert report.final_state == "blocked"
    assert any("cluster diameter" in reason for reason in report.reasons)
    rewritten = (archive / "review-summary.md").read_text(encoding="utf-8")
    assert "provisional calibration score 99.2" in rewritten
    assert "no emergence claim" in rewritten.lower()
    assert "leading score is close" not in rewritten.lower()
    assert (archive / "temporal-semantic-integrity.json").exists()
    assert (archive / "temporal-ledger.json").exists()


def test_integrity_report_exposes_domain_stage_scale_and_panel_counts(tmp_path: Path) -> None:
    archive = tmp_path / "archive" / "2026-09-05"
    archive.mkdir(parents=True)
    (archive / "workflow-state.txt").write_text("baseline_only\n", encoding="utf-8")
    (archive / "review-summary.md").write_text(
        "# Pantone Challenger — 2026-09-05\n\nState: `baseline_only`\nCoverage: 30 / 58 active sources\nHistorical baseline: 0 prior valid days\n",
        encoding="utf-8",
    )
    data = {
        "observations": [
            {"source_id": "a", "source_name": "A", "domain": "art", "signal_stage": "creation", "scale_class": "independent", "panel_type": "discovery"},
            {"source_id": "b", "source_name": "B", "domain": "fashion", "signal_stage": "distribution", "scale_class": "large_commercial", "panel_type": "benchmark"},
        ]
    }
    (archive / "observations.json").write_text(json.dumps(data), encoding="utf-8")
    report = run_integrity(tmp_path, date(2026, 9, 5))
    assert report.source_breakdown["domain"] == {"art": 1, "fashion": 1}
    assert report.source_breakdown["stage"] == {"creation": 1, "distribution": 1}
    assert report.final_state == "baseline_only"


def test_capture_date_does_not_make_undated_art_current(tmp_path: Path) -> None:
    cfg = _load_config(tmp_path)
    record = {
        "source_id": "museum-work",
        "source_name": "Museum Work",
        "domain": "art",
        "signal_stage": "creation",
        "panel_type": "discovery",
        "event_type": "permanent_collection",
        "capture_date": "2026-09-05",
        "cultural_date": "2026-09-05",
    }
    status, *_ = _temporal_status(record, date(2026, 9, 5), {"sources": {}}, "abc", cfg)
    assert status == "context_only_historical"


def test_integrity_audited_ranking_uses_only_current_substantial_evidence(tmp_path: Path) -> None:
    from challenger.temporal_semantic_integrity import EvidenceFinding, _audited_clusters
    cfg = _load_config(tmp_path)
    findings = []
    for index in range(6):
        findings.append(EvidenceFinding(
            source_id=f"source-{index}",
            source_name=f"Source {index}",
            local_hex="#D6C547",
            domain=["art", "fashion", "marketplace", "design", "technology", "entertainment"][index],
            stage=["creation", "distribution", "attention"][index % 3],
            scale="independent" if index < 3 else "large-commercial",
            panel="discovery" if index < 3 else "benchmark",
            temporal_status="eligible_current",
            semantic_status="eligible",
            total_color_share=0.20,
            largest_component_share=0.10,
        ))
    # A broad but undated/static blue should not enter the audited current ranking.
    for index in range(12):
        findings.append(EvidenceFinding(
            source_id=f"blue-{index}",
            source_name=f"Blue {index}",
            local_hex="#115BB9",
            domain="technology",
            stage="distribution",
            scale="large-commercial",
            panel="benchmark",
            temporal_status="baseline_only_unchanged",
            semantic_status="eligible",
            total_color_share=0.50,
            largest_component_share=0.40,
        ))
    ranking = _audited_clusters(findings, cfg)
    assert ranking
    assert ranking[0].display_hex == "#D6C547"
    assert ranking[0].eligible is True
    assert all(cluster.display_hex != "#115BB9" for cluster in ranking)


def test_integrity_audited_tie_ignores_ineligible_cluster(tmp_path: Path) -> None:
    from challenger.temporal_semantic_integrity import AuditedCluster, _audited_tie
    cfg = _load_config(tmp_path)
    first = AuditedCluster("#D6C547", 88.0, 8, 5, 3, 3, 2, 0.01, [], [], [], [], True)
    neutral = AuditedCluster("#777777", 87.5, 15, 8, 3, 4, 2, 0.01, [], [], [], [], False)
    second = AuditedCluster("#3E79C5", 84.0, 7, 5, 3, 3, 2, 0.01, [], [], [], [], True)
    result = _audited_tie([first, neutral, second], cfg)
    assert result["is_tie"] is False
    assert result["second"]["display_hex"] == "#3E79C5"


def test_changed_undated_benchmark_can_be_current_distribution_evidence(tmp_path: Path) -> None:
    cfg = _load_config(tmp_path)
    record = {
        "source_id": "brand",
        "source_name": "Brand",
        "domain": "marketing",
        "signal_stage": "distribution",
        "panel_type": "benchmark",
    }
    prior = {"sources": {"brand": {"fingerprint": "old", "first_seen": "2026-09-01", "last_changed": "2026-09-01"}}}
    status, reasons, *_ = _temporal_status(record, date(2026, 9, 5), prior, "new", cfg)
    assert status == "eligible_changed_today"
    assert any("changed" in reason.lower() for reason in reasons)
