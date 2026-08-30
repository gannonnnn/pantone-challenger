import json
from pathlib import Path

from challenger.config import load_sources
from challenger.site import build_site


def test_empty_site_is_real_launch_placeholder_not_demo(tmp_path):
    archive = tmp_path / "archive"
    archive.mkdir()
    site = tmp_path / "site"
    build_site(archive, site, load_sources(Path("config")))
    html = (site / "index.html").read_text()
    assert "FIRST LIVE RESULT IS PENDING" in html
    assert "synthetic" in html.lower()
    assert 'href="./"' in html


def test_site_exposes_recurrence_and_year_end_summary(tmp_path):
    archive = tmp_path / "archive"
    daily = archive / "2026-08-26"
    daily.mkdir(parents=True)
    result = {
        "date": "2026-08-26",
        "status": "ready",
        "winner_name": "Electric Grocery Aisle",
        "panel_size": 48,
        "captured_sources": 41,
        "captured_sectors": 11,
        "quality_gate": {"configured_sectors": 12},
        "winner": {
            "hex": "#A7C84A",
            "score": 81.2,
            "source_count": 8,
            "sector_count": 8,
            "source_ids": [],
            "source_names": [],
            "sectors": [],
        },
        "runners_up": [],
        "runner_up_names": [],
        "source_logos": {},
        "recurrence": {
            "year": 2026,
            "family_name": "Chartreuse",
            "winning_days": 3,
            "unique_company_count": 24,
            "panel_company_count": 48,
            "sector_count": 8,
        },
    }
    (daily / "result.json").write_text(json.dumps(result))

    annual_dir = archive / "yearly" / "2026"
    annual_dir.mkdir(parents=True)
    family = {
        "family_name": "Chartreuse",
        "representative_hex": "#A4C44B",
        "winning_days": 25,
        "longest_streak": 4,
        "unique_company_count": 31,
        "panel_company_count": 48,
        "sector_count": 10,
    }
    annual = {
        "year": 2026,
        "approved_days": 300,
        "average_panel_coverage_percent": 84.0,
        "most_frequent_family": family,
        "families": [family],
    }
    (annual_dir / "annual-summary.json").write_text(json.dumps(annual))
    for name in ("year-in-color.png", "year-color-grid.png", "annual-summary.md"):
        (annual_dir / name).write_bytes(b"placeholder")

    site = tmp_path / "site"
    build_site(archive, site, load_sources(Path("config")))

    home = (site / "index.html").read_text()
    detail = (site / "archive" / "2026-08-26" / "index.html").read_text()
    year = (site / "year" / "2026" / "index.html").read_text()
    assert "Chartreuse wins in 2026" in home
    assert "day <strong>3</strong>" in detail
    assert "2026 YEAR IN COLOR" in year
    assert "25" in year
