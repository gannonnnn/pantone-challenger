from pathlib import Path

from PIL import Image

from challenger.colors import oklab_from_hex, oklab_to_oklch
from challenger.models import Candidate, DailyResult, QualityGate
from challenger.render import FEED_SIZE, STORY_SIZE, render_daily


def candidate(value: str, score: float, count: int = 9) -> Candidate:
    lab = oklab_from_hex(value)
    return Candidate(
        hex=value,
        oklab=lab,
        oklch=oklab_to_oklch(lab),
        score=score,
        source_count=count,
        sector_count=5,
        source_ids=[f"s{i}" for i in range(count)],
        source_names=[f"Source {i}" for i in range(count)],
        sectors=["beauty", "finance", "retail", "technology", "travel"],
        prevalence=0.30,
        sector_breadth=0.50,
        mean_salience=0.24,
        momentum=0.80,
        baseline_prevalence=0.12,
        neutral_penalty=0,
        concentration_penalty=0,
        components={"source_breadth": 20},
    )


def test_daily_social_package_has_expected_sizes(tmp_path):
    winner = candidate("#6F8557", 81.2)
    result = DailyResult(
        date="2026-08-25",
        generated_at="2026-08-25T23:00:00-04:00",
        project="Pantone Challenger",
        methodology_version="1.0",
        panel_size=48,
        captured_sources=39,
        captured_sectors=11,
        baseline_days=12,
        status="ready",
        quality_gate=QualityGate(True, [], 39, 48, 11, 12),
        winner=winner,
        winner_name="Expensive Olive Oil Green",
        runners_up=[candidate("#A34D43", 74.0), candidate("#4799A2", 71.0), candidate("#C5A14A", 68.0)],
        source_failures=[],
        disclaimer="Independent project.",
    )
    outputs = render_daily(result, tmp_path)
    assert len(outputs) == 5
    assert Image.open(tmp_path / "feed-post.png").size == FEED_SIZE
    for name in (
        "story-01-color.png",
        "story-02-evidence.png",
        "story-03-why-it-won.png",
        "story-04-runners-up.png",
    ):
        assert Image.open(tmp_path / name).size == STORY_SIZE
    assert "The algorithm chooses the color" in (tmp_path / "caption.txt").read_text()
