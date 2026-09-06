import json

from challenger.annual import build_annual_summary
from challenger.site import build_site


def write_day(root, date, color="#A5C84A", family="Chartreuse"):
    day = root / date
    day.mkdir(parents=True)
    result = {
        "date": date,
        "state": "ready",
        "challenger": [{"hex": color, "family_label": family, "creative_name": family, "evidence": [{"source_id":"a","domain":"art"}]}],
        "domains_covered": 5,
        "sectors_covered": 6,
        "stages_covered": 3,
        "sources_with_eligible_evidence": 20,
        "baseline_days": 10,
        "palette_regime": {"dominant_regime":"saturated accents","median_chroma":.15,"neutral_share":.2},
        "undercurrent": {"family_label":"Chartreuse"},
        "mainstream_leader": {"family_label":"Blue"},
    }
    (day / "result.json").write_text(json.dumps(result))


def test_annual_summary_and_grid(tmp_path):
    archive = tmp_path / "archive"
    write_day(archive, "2026-01-01")
    write_day(archive, "2026-01-02", "#4799A2", "Teal")
    summary = build_annual_summary(archive, 2026)
    assert summary["approved_challenger_days"] == 2
    assert (archive / "yearly/2026/year-color-grid.png").exists()


def test_historical_site_builds(tmp_path):
    archive = tmp_path / "archive"
    write_day(archive, "2026-01-01")
    dest = tmp_path / "site"
    build_site(archive, dest)
    assert (dest / "index.html").exists()
    assert (dest / "days/2026-01-01/index.html").exists()
    assert (dest / "feed.json").exists()
