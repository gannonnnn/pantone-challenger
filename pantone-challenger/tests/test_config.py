from pathlib import Path

from challenger.config import load_sources, panel_summary


def test_real_panel_is_balanced():
    sources = load_sources(Path("config"))
    summary = panel_summary(sources)
    assert summary["sources"] == 48
    assert summary["sectors"] == 12
    assert set(summary["sector_counts"].values()) == {4}
    assert all(source.url.startswith("https://") for source in sources)
