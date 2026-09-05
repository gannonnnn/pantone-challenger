import json
from datetime import date
from pathlib import Path

from challenger.colors import oklab_from_hex, oklab_to_oklch
from challenger.models import Candidate
from challenger.recurrence import calculate_recurrence, color_family_name


def candidate(value: str, sources: list[str], sectors: list[str]) -> Candidate:
    lab = oklab_from_hex(value)
    return Candidate(
        hex=value,
        oklab=lab,
        oklch=oklab_to_oklch(lab),
        score=80.0,
        source_count=len(sources),
        sector_count=len(set(sectors)),
        source_ids=sources,
        source_names=[item.upper() for item in sources],
        sectors=sorted(set(sectors)),
        prevalence=0.3,
        sector_breadth=0.5,
        mean_salience=0.2,
        momentum=0.7,
        baseline_prevalence=0.1,
        neutral_penalty=0,
        concentration_penalty=0,
        components={},
        source_sectors=sectors,
        source_salience=[0.2 for _ in sources],
    )


def write_result(root: Path, day: str, item: Candidate, captured: int = 40) -> None:
    path = root / day / "result.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "date": day,
                "status": "ready",
                "methodology_version": "1.3.0",
                "panel_size": 48,
                "captured_sources": captured,
                "winner": item.to_dict(),
            }
        ),
        encoding="utf-8",
    )


def test_recurrence_counts_perceptually_similar_wins_and_unique_companies(tmp_path):
    write_result(
        tmp_path,
        "2026-08-24",
        candidate("#89A94A", ["a", "b"], ["fashion", "technology"]),
    )
    write_result(
        tmp_path,
        "2026-08-25",
        candidate("#8EAE4F", ["b", "c"], ["technology", "home"]),
    )
    write_result(
        tmp_path,
        "2026-08-23",
        candidate("#3A75B7", ["z"], ["finance"]),
    )

    current = candidate(
        "#91B34E",
        ["c", "d"],
        ["fashion", "retail"],
    )
    summary = calculate_recurrence(
        archive_root=tmp_path,
        target_date=date(2026, 8, 26),
        winner=current,
        panel_size=48,
        captured_sources=39,
        distance_threshold=0.055,
    )

    assert summary.winning_days == 3
    assert summary.previous_winning_days == 2
    assert summary.current_streak == 3
    assert summary.longest_streak == 3
    assert summary.unique_company_count == 4
    assert summary.panel_company_count == 48
    assert summary.sector_count == 4
    assert summary.matching_dates == ["2026-08-24", "2026-08-25", "2026-08-26"]


def test_recurrence_resets_at_calendar_year(tmp_path):
    prior = candidate("#8EAE4F", ["a"], ["fashion"])
    write_result(tmp_path, "2025-12-31", prior)
    summary = calculate_recurrence(
        archive_root=tmp_path,
        target_date=date(2026, 1, 1),
        winner=prior,
        panel_size=48,
        captured_sources=40,
        distance_threshold=0.055,
    )
    assert summary.winning_days == 1
    assert summary.first_win_date == "2026-01-01"


def test_family_label_is_stable_and_not_based_on_daily_name():
    assert color_family_name(oklab_from_hex("#8EAE4F")) in {"Yellow-Green", "Chartreuse", "Olive Green"}
    assert color_family_name(oklab_from_hex("#2F70C0")) == "Blue"
