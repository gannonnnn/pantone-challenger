from pathlib import Path

from PIL import Image, ImageDraw

from challenger.colors import oklab_from_hex, oklab_to_oklch
from challenger.models import Candidate, DailyResult, QualityGate, RecurrenceSummary
from challenger.render import FEED_SIZE, STORY_SIZE, render_daily


def candidate(value: str, score: float, count: int = 9) -> Candidate:
    lab = oklab_from_hex(value)
    sectors = ["beauty", "finance", "retail", "technology", "travel"]
    return Candidate(
        hex=value,
        oklab=lab,
        oklch=oklab_to_oklch(lab),
        score=score,
        source_count=count,
        sector_count=5,
        source_ids=[f"s{i}" for i in range(count)],
        source_names=[f"Source {i}" for i in range(count)],
        sectors=sectors,
        prevalence=0.30,
        sector_breadth=0.50,
        mean_salience=0.24,
        momentum=0.80,
        baseline_prevalence=0.12,
        neutral_penalty=0,
        concentration_penalty=0,
        components={"source_breadth": 20},
        source_sectors=[sectors[i % len(sectors)] for i in range(count)],
        source_salience=[0.22 - (i * 0.01) for i in range(count)],
    )


def _make_logo(path: Path, label: str) -> None:
    image = Image.new("RGBA", (260, 128), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((20, 20, 240, 108), radius=18, fill="#FFFFFF")
    draw.text((86, 50), label, fill="#111111")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def test_daily_social_package_has_visible_colors_logos_and_counts(tmp_path):
    winner = candidate("#6F8557", 81.2)
    logo_map = {}
    for index in range(8):
        relative = f"logos/s{index}.png"
        _make_logo(tmp_path / relative, f"S{index}")
        logo_map[f"s{index}"] = relative

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
        runners_up=[
            candidate("#A34D43", 74.0),
            candidate("#4799A2", 71.0),
            candidate("#C5A14A", 68.0),
        ],
        source_failures=[],
        disclaimer="Independent project.",
        runner_up_names=["Hotel Lobby Red", "Pool Tile Blue", "Loyalty Tier Gold"],
        source_logos=logo_map,
        recurrence=RecurrenceSummary(
            year=2026,
            family_name="Olive Green",
            representative_hex="#748553",
            distance_threshold=0.055,
            winning_days=3,
            previous_winning_days=2,
            current_streak=2,
            longest_streak=2,
            first_win_date="2026-08-20",
            latest_win_date="2026-08-25",
            matching_dates=["2026-08-20", "2026-08-24", "2026-08-25"],
            unique_company_count=17,
            unique_company_ids=[f"s{i}" for i in range(17)],
            unique_company_names=[f"Source {i}" for i in range(17)],
            panel_company_count=48,
            supporting_company_days=26,
            average_analyzed_company_pages=39.3,
            sectors=["fashion", "technology", "home", "retail"],
            sector_count=4,
            sector_day_counts={"fashion": 3, "technology": 2, "home": 1, "retail": 1},
            ready_days_in_year=20,
        ),
    )
    outputs = render_daily(result, tmp_path)
    assert len(outputs) == 5

    feed = Image.open(tmp_path / "feed-post.png")
    assert feed.size == FEED_SIZE
    assert feed.getpixel((900, 500)) == (111, 133, 87)

    runners = Image.open(tmp_path / "story-04-runners-up.png")
    assert runners.size == STORY_SIZE
    assert runners.getpixel((180, 550)) == (163, 77, 67)
    assert runners.getpixel((180, 985)) == (71, 153, 162)

    for name in (
        "story-01-color.png",
        "story-02-evidence.png",
        "story-03-why-it-won.png",
        "story-04-runners-up.png",
    ):
        assert Image.open(tmp_path / name).size == STORY_SIZE

    caption = (tmp_path / "caption.txt").read_text()
    assert "48 company pages monitored" in caption
    assert "39 successfully analyzed" in caption
    assert "RUNNERS-UP" in caption
    assert "3rd day in 2026" in caption
    assert "17 unique companies" in caption

    review = (tmp_path / "review-summary.md").read_text()
    assert "Company pages monitored" in review
    assert "Supporting sources" in review
    assert "Year-to-date recurrence" in review
    assert "OKLab distance" in review
    assert "Runner-up colors" not in review  # descriptive image alt is intentionally concise
