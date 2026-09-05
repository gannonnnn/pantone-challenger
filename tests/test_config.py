from pathlib import Path

from challenger.config import load_source_panel, panel_summary


def test_real_panel_is_balanced_and_text_only_until_marks_are_curated():
    version, sources = load_source_panel(Path("config"))
    summary = panel_summary(sources)
    assert version == "1.3"
    assert summary["sources"] == 48
    assert summary["sectors"] == 12
    assert set(summary["sector_counts"].values()) == {4}
    assert summary["approved_brand_marks"] == 0
    assert summary["text_only_sources"] == 48
    assert all(source.url.startswith("https://") for source in sources)


def test_canonical_company_sectors_are_authoritative():
    _, sources = load_source_panel(Path("config"))
    sector = {item.name: item.sector for item in sources}
    assert sector["Spotify"] == "entertainment"
    assert sector["Max"] == "entertainment"
    assert sector["PlayStation"] == "gaming"
    assert sector["Epic Games Store"] == "gaming"
    assert sector["Nike"] == "sports"
    assert sector["Peloton"] == "sports"
    assert sector["Apple"] == "technology"
    assert sector["Sephora"] == "beauty"
