from PIL import Image

from challenger.models import DailyResult, PaletteRegime, PublicationState
from challenger.render import render_daily
from tests.helpers import candidate


def result(tmp_path, colors=("#A5C84A",), state=PublicationState.READY):
    challengers = [candidate(color, score=75-i) for i, color in enumerate(colors)]
    for c in challengers:
        for i, e in enumerate(c.evidence):
            p = tmp_path / f"evidence-{c.hex[1:]}-{i}.png"
            Image.new("RGB", (600, 400), e.local_hex).save(p)
            e.region_path = str(p)
    return DailyResult(
        date="2026-09-05",
        state=state,
        methodology_version="1.5.1",
        registry_version="test",
        panel_declared=48,
        sources_attempted=48,
        sources_captured=40,
        sources_with_eligible_evidence=36,
        domains_covered=8,
        sectors_covered=12,
        stages_covered=3,
        benchmark_sources=28,
        discovery_sources=8,
        challenger=challengers,
        undercurrent=challengers[0],
        mainstream_leader=challengers[-1],
        usage_leader=challengers[-1],
        runner_ups=[candidate("#A34D43"), candidate("#4799A2"), candidate("#C5A14A")],
        palette_regime=PaletteRegime(.2,.15,.6,.45,.55,.32,4.2,.1,.3,.7,"high-chroma maximalism",[{"colors":["#A5C84A","#4799A2"],"score":.5}]),
        palette_pair={"colors":["#A5C84A","#4799A2"],"score":.5},
        blocking_reasons=[],
        review_reasons=[],
        baseline_days=14,
        recurrence={},
    )


def test_feed_winner_field_matches_hex(tmp_path):
    out = tmp_path / "out"
    render_daily(result(tmp_path), out, {}, {})
    image = Image.open(out / "feed-post.png").convert("RGB")
    assert image.getpixel((500, 500)) == (165, 200, 74)


def test_tie_renders_both_colors(tmp_path):
    out = tmp_path / "out"
    render_daily(result(tmp_path, ("#A5C84A", "#4799A2")), out, {}, {})
    image = Image.open(out / "feed-post.png").convert("RGB")
    assert image.getpixel((250, 500)) == (165, 200, 74)
    assert image.getpixel((800, 500)) == (71, 153, 162)


def test_runner_up_swatches_render_exact_colors(tmp_path):
    out = tmp_path / "out"
    render_daily(result(tmp_path), out, {}, {})
    image = Image.open(out / "story-04-runners-up.png").convert("RGB")
    assert image.getpixel((200, 500)) == (163, 77, 67)
    assert image.getpixel((200, 940)) == (71, 153, 162)
    assert image.getpixel((200, 1380)) == (197, 161, 74)


def test_evidence_uses_local_swatch_not_logo(tmp_path):
    out = tmp_path / "out"
    render_daily(result(tmp_path), out, {}, {})
    image = Image.open(out / "story-02-evidence.png").convert("RGB")
    assert image.getpixel((120, 350)) == (165, 200, 74)


def test_calibration_banner_and_assets(tmp_path):
    out = tmp_path / "out"
    render_daily(result(tmp_path, state=PublicationState.REVIEW_ONLY), out, {}, {})
    assert (out / "feed-post.png").exists()
    assert (out / "caption.txt").exists()
