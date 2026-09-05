import json
from pathlib import Path

from challenger.annual import build_annual_summary, write_annual_package
from challenger.colors import oklab_from_hex, oklab_to_oklch
from challenger.models import Candidate, Source


def candidate(value: str, sources: list[str], sectors: list[str], score: float = 80.0) -> Candidate:
    lab = oklab_from_hex(value)
    return Candidate(
        hex=value,
        oklab=lab,
        oklch=oklab_to_oklch(lab),
        score=score,
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


def write_result(root: Path, day: str, item: Candidate) -> None:
    path = root / day / "result.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "date": day,
                "status": "ready",
                "methodology_version": "1.3.0",
                "panel_size": 4,
                "captured_sources": 4,
                "winner": item.to_dict(),
                "winner_name": item.hex,
            }
        ),
        encoding="utf-8",
    )


def sources() -> list[Source]:
    return [
        Source(id=f"s{i}", name=f"Source {i}", sector="fashion", url=f"https://e{i}.com")
        for i in range(4)
    ]


def test_year_end_groups_similar_daily_winners(tmp_path):
    write_result(tmp_path, "2026-01-01", candidate("#8AA84A", ["s0", "s1"], ["fashion", "technology"]))
    write_result(tmp_path, "2026-01-02", candidate("#8EAE4F", ["s1", "s2"], ["technology", "home"]))
    write_result(tmp_path, "2026-01-03", candidate("#3A75B7", ["s3"], ["finance"]))

    summary = build_annual_summary(
        archive_root=tmp_path,
        year=2026,
        sources=sources(),
        distance_threshold=0.055,
    )

    assert summary["approved_days"] == 3
    assert summary["most_frequent_family"]["winning_days"] == 2
    assert summary["most_frequent_family"]["unique_company_count"] == 3
    assert summary["longest_streak_family"]["longest_streak"] == 2


def test_year_end_writes_social_assets(tmp_path):
    write_result(tmp_path, "2026-01-01", candidate("#8AA84A", ["s0", "s1"], ["fashion", "technology"]))
    output = write_annual_package(
        archive_root=tmp_path,
        year=2026,
        sources=sources(),
        distance_threshold=0.055,
    )
    assert (output / "annual-summary.json").exists()
    assert (output / "annual-summary.md").exists()
    assert (output / "year-in-color.png").exists()
    assert (output / "year-color-grid.png").exists()
