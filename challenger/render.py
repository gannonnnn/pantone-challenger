from __future__ import annotations

import math
import textwrap
from datetime import date
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

from .colors import contrast_text_color, hex_from_oklab
from .models import DailyResult


FEED_SIZE = (1080, 1350)
STORY_SIZE = (1080, 1920)
OFF_WHITE = "#F5F1E8"
INK = "#171717"


def _font_path(bold: bool = False) -> str | None:
    candidates = (
        [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
        if bold
        else [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]
    )
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = _font_path(bold=bold)
    if path:
        return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    start: int,
    minimum: int,
    *,
    bold: bool = True,
) -> ImageFont.ImageFont:
    size = start
    while size > minimum:
        font = _font(size, bold=bold)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return font
        size -= 2
    return _font(minimum, bold=bold)


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    *,
    max_width: int,
    font: ImageFont.ImageFont,
    fill: str,
    spacing: int = 12,
    max_lines: int | None = None,
) -> int:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        proposal = f"{line} {word}".strip()
        width = draw.textbbox((0, 0), proposal, font=font)[2]
        if line and width > max_width:
            lines.append(line)
            line = word
        else:
            line = proposal
    if line:
        lines.append(line)
    if max_lines is not None:
        lines = lines[:max_lines]

    x, y = xy
    bbox = draw.textbbox((0, 0), "Ag", font=font)
    line_height = bbox[3] - bbox[1] + spacing
    for item in lines:
        draw.text((x, y), item, font=font, fill=fill)
        y += line_height
    return y


def _human_date(value: str) -> str:
    parsed = date.fromisoformat(value)
    return parsed.strftime("%B %-d, %Y") if hasattr(parsed, "strftime") else value


def _adjusted_hex(lab: tuple[float, float, float], lightness_shift: float) -> str:
    L, a, b = lab
    return hex_from_oklab((max(0.08, min(0.96, L + lightness_shift)), a, b))


def _draw_brand(draw: ImageDraw.ImageDraw, y: int, color: str) -> None:
    draw.text((74, y), "PANTONE CHALLENGER", font=_font(29, bold=True), fill=color)
    draw.text(
        (74, y + 43),
        "THE COMMERCIAL COLOR INDEX",
        font=_font(18, bold=False),
        fill=color,
    )


def render_feed(result: DailyResult, output: Path) -> None:
    assert result.winner and result.winner_name
    winner = result.winner
    background = winner.hex
    foreground = contrast_text_color(background)
    image = Image.new("RGB", FEED_SIZE, background)
    draw = ImageDraw.Draw(image)
    _draw_brand(draw, 70, foreground)

    draw.text(
        (74, 250),
        "YESTERDAY’S CHALLENGER",
        font=_font(24, bold=True),
        fill=foreground,
    )
    name_font = _fit_font(draw, result.winner_name.upper(), 930, 94, 54, bold=True)
    y = _draw_wrapped(
        draw,
        result.winner_name.upper(),
        (70, 320),
        max_width=930,
        font=name_font,
        fill=foreground,
        spacing=2,
        max_lines=3,
    )
    draw.text((74, y + 38), winner.hex, font=_font(35, bold=False), fill=foreground)

    rule_y = 1060
    draw.line((74, rule_y, 1006, rule_y), fill=foreground, width=2)
    stats = [
        (str(winner.source_count), "INDEPENDENT SOURCES"),
        (str(winner.sector_count), "COMMERCIAL SECTORS"),
        (f"{winner.score:.1f}", "CHALLENGER SCORE"),
    ]
    x_positions = (74, 395, 720)
    for x, (value, label) in zip(x_positions, stats):
        draw.text((x, rule_y + 35), value, font=_font(41, bold=True), fill=foreground)
        draw.text((x, rule_y + 91), label, font=_font(15, bold=True), fill=foreground)

    draw.text(
        (74, 1276),
        _human_date(result.date).upper(),
        font=_font(18, bold=True),
        fill=foreground,
    )
    image.save(output, quality=95)


def render_story_color(result: DailyResult, output: Path) -> None:
    assert result.winner and result.winner_name
    winner = result.winner
    foreground = contrast_text_color(winner.hex)
    image = Image.new("RGB", STORY_SIZE, winner.hex)
    draw = ImageDraw.Draw(image)
    _draw_brand(draw, 82, foreground)
    draw.text(
        (74, 420),
        "YESTERDAY’S\nCHALLENGER",
        font=_font(38, bold=True),
        fill=foreground,
        spacing=10,
    )
    name_font = _fit_font(draw, result.winner_name.upper(), 920, 105, 58, bold=True)
    y = _draw_wrapped(
        draw,
        result.winner_name.upper(),
        (74, 660),
        max_width=920,
        font=name_font,
        fill=foreground,
        spacing=8,
        max_lines=4,
    )
    draw.text((74, y + 58), winner.hex, font=_font(40), fill=foreground)
    draw.text(
        (74, 1790),
        _human_date(result.date).upper(),
        font=_font(21, bold=True),
        fill=foreground,
    )
    image.save(output, quality=95)


def render_story_evidence(result: DailyResult, output: Path) -> None:
    assert result.winner and result.winner_name
    winner = result.winner
    image = Image.new("RGB", STORY_SIZE, OFF_WHITE)
    draw = ImageDraw.Draw(image)
    _draw_brand(draw, 82, INK)
    draw.text((74, 245), "WHERE IT APPEARED", font=_font(54, bold=True), fill=INK)
    draw.text(
        (74, 326),
        "Independent official marketing pages contributing to the winning cluster.",
        font=_font(24),
        fill=INK,
    )

    card_top = 440
    card_height = 230
    gap = 24
    sources = list(zip(winner.source_names[:5], winner.source_ids[:5]))
    shifts = [0.12, -0.08, 0.04, -0.14, 0.18]
    for index, (source_name, source_id) in enumerate(sources):
        top = card_top + index * (card_height + gap)
        card_color = _adjusted_hex(winner.oklab, shifts[index % len(shifts)])
        card_text = contrast_text_color(card_color)
        draw.rounded_rectangle(
            (74, top, 1006, top + card_height),
            radius=28,
            fill=card_color,
        )
        draw.text(
            (112, top + 46),
            f"{index + 1:02d}",
            font=_font(24, bold=True),
            fill=card_text,
        )
        source_font = _fit_font(draw, source_name, 720, 42, 28, bold=True)
        draw.text((205, top + 37), source_name, font=source_font, fill=card_text)
        draw.text(
            (205, top + 106),
            "OFFICIAL MARKETING PAGE",
            font=_font(18, bold=True),
            fill=card_text,
        )
        draw.text(
            (205, top + 151),
            "Color evidence recorded; source imagery is not republished.",
            font=_font(18),
            fill=card_text,
        )

    draw.text(
        (74, 1790),
        f"{winner.source_count} SOURCES TOTAL · {winner.sector_count} SECTORS",
        font=_font(20, bold=True),
        fill=INK,
    )
    image.save(output, quality=95)


def render_story_why(result: DailyResult, output: Path) -> None:
    assert result.winner
    winner = result.winner
    image = Image.new("RGB", STORY_SIZE, "#111111")
    draw = ImageDraw.Draw(image)
    _draw_brand(draw, 82, OFF_WHITE)
    draw.text((74, 245), "WHY IT WON", font=_font(60, bold=True), fill=OFF_WHITE)

    rows = [
        ("SOURCE BREADTH", f"{winner.source_count} independent brands"),
        ("SECTOR BREADTH", f"{winner.sector_count} commercial sectors"),
        ("VISUAL SALIENCE", f"{winner.mean_salience * 100:.1f}% mean adjusted share"),
    ]
    if result.baseline_days >= 7:
        ratio = (winner.prevalence + 0.02) / (winner.baseline_prevalence + 0.02)
        rows.append(("MOMENTUM", f"{ratio:.2f}× its trailing baseline"))
    else:
        rows.append(("BASELINE", f"Day {result.baseline_days + 1} of calibration"))

    top = 480
    for index, (label, value) in enumerate(rows):
        y = top + index * 260
        draw.text((74, y), label, font=_font(22, bold=True), fill="#A7A7A7")
        value_font = _fit_font(draw, value, 900, 48, 32, bold=True)
        draw.text((74, y + 58), value, font=value_font, fill=OFF_WHITE)
        draw.line((74, y + 180, 1006, y + 180), fill="#414141", width=2)

    draw.text(
        (74, 1570),
        f"CHALLENGER SCORE  {winner.score:.1f}",
        font=_font(31, bold=True),
        fill=winner.hex,
    )
    note = (
        "The color is selected by the published scoring method. "
        "It is never replaced because a different result would look prettier."
    )
    _draw_wrapped(
        draw,
        note,
        (74, 1655),
        max_width=900,
        font=_font(23),
        fill=OFF_WHITE,
        spacing=10,
    )
    image.save(output, quality=95)


def render_story_runners(result: DailyResult, output: Path) -> None:
    image = Image.new("RGB", STORY_SIZE, OFF_WHITE)
    draw = ImageDraw.Draw(image)
    _draw_brand(draw, 82, INK)
    draw.text((74, 245), "RUNNERS-UP", font=_font(60, bold=True), fill=INK)

    candidates = result.runners_up[:3]
    top = 440
    height = 360
    gap = 54
    for index, candidate in enumerate(candidates):
        y = top + index * (height + gap)
        text = contrast_text_color(candidate.hex)
        draw.rounded_rectangle((74, y, 1006, y + height), radius=34, fill=candidate.hex)
        draw.text(
            (112, y + 54),
            f"#{index + 2}",
            font=_font(28, bold=True),
            fill=text,
        )
        draw.text(
            (112, y + 118),
            candidate.hex,
            font=_font(50, bold=True),
            fill=text,
        )
        draw.text(
            (112, y + 204),
            f"{candidate.source_count} sources · {candidate.sector_count} sectors",
            font=_font(24),
            fill=text,
        )
        draw.text(
            (112, y + 260),
            f"Score {candidate.score:.1f}",
            font=_font(22, bold=True),
            fill=text,
        )

    image.save(output, quality=95)


def build_caption(result: DailyResult) -> str:
    assert result.winner and result.winner_name
    winner = result.winner
    baseline = (
        f"It appeared at {((winner.prevalence + 0.02) / (winner.baseline_prevalence + 0.02)):.2f}× "
        "its trailing prevalence."
        if result.baseline_days >= 7
        else f"The index is still calibrating its {30}-day baseline."
    )
    sectors = ", ".join(item.replace("_", " ") for item in winner.sectors[:5])
    return (
        f"Yesterday’s Challenger was {result.winner_name} ({winner.hex}).\n\n"
        f"It was the most unusually prominent color across {result.captured_sources} "
        f"usable official marketing pages in the monitored panel, with support from "
        f"{winner.source_count} independent sources across {winner.sector_count} sectors"
        f"{f'—including {sectors}' if sectors else ''}.\n\n"
        f"{baseline}\n\n"
        "The algorithm chooses the color. It does not get replaced for being ugly.\n\n"
        "Pantone Challenger is an independent computational art project and is not "
        "affiliated with or endorsed by Pantone LLC.\n\n"
        "#PantoneChallenger #ColorTrends #MarketingTrends #CreativeTechnology"
    )


def render_daily(result: DailyResult, output_dir: Path) -> list[Path]:
    if result.status != "ready" or not result.winner:
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        output_dir / "feed-post.png",
        output_dir / "story-01-color.png",
        output_dir / "story-02-evidence.png",
        output_dir / "story-03-why-it-won.png",
        output_dir / "story-04-runners-up.png",
    ]
    render_feed(result, outputs[0])
    render_story_color(result, outputs[1])
    render_story_evidence(result, outputs[2])
    render_story_why(result, outputs[3])
    render_story_runners(result, outputs[4])
    (output_dir / "caption.txt").write_text(build_caption(result), encoding="utf-8")
    return outputs
