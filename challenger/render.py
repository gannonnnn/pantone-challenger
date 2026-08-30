from __future__ import annotations

from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat

from .colors import contrast_text_color
from .models import Candidate, DailyResult
from .recurrence import human_sector_list


FEED_SIZE = (1080, 1350)
STORY_SIZE = (1080, 1920)
OFF_WHITE = "#F5F1E8"
PAPER = "#FBF9F4"
INK = "#171717"
MUTED = "#6D6A64"
LINE = "#D9D2C5"


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
    try:
        return parsed.strftime("%B %-d, %Y")
    except ValueError:
        return parsed.strftime("%B %d, %Y").replace(" 0", " ")


def _ordinal(value: int) -> str:
    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def _recurrence_headline(result: DailyResult) -> str:
    recurrence = result.recurrence
    if not recurrence:
        return "FIRST RECORDED WIN"
    return f"{recurrence.winning_days} DAYS AS THE TOP COMMERCIAL COLOR IN {recurrence.year}"


def _recurrence_detail(result: DailyResult) -> str:
    recurrence = result.recurrence
    if not recurrence:
        return "YEAR-TO-DATE HISTORY BEGINS WITH THIS RESULT"
    return (
        f"{recurrence.family_name.upper()} · "
        f"{recurrence.unique_company_count} / {recurrence.panel_company_count} COMPANIES · "
        f"{recurrence.sector_count} SECTORS"
    )


def _recurrence_sentence(result: DailyResult) -> str:
    recurrence = result.recurrence
    if not recurrence:
        return "This result begins the year-to-date color history."
    sectors = human_sector_list(recurrence.sectors, limit=4)
    sentence = (
        f"This is the {_ordinal(recurrence.winning_days)} day in {recurrence.year} that "
        f"{recurrence.family_name} ranked as the top color in the monitored commercial panel. "
        f"Across those wins, it appeared across {sectors}, with "
        f"{recurrence.unique_company_count} unique companies represented in the "
        f"{recurrence.panel_company_count}-company panel."
    )
    if recurrence.current_streak >= 2:
        sentence += f" It is also a {recurrence.current_streak}-day consecutive streak."
    return sentence


def _draw_brand(draw: ImageDraw.ImageDraw, y: int, color: str) -> None:
    draw.text((74, y), "PANTONE CHALLENGER", font=_font(29, bold=True), fill=color)
    draw.text(
        (74, y + 43),
        "THE COMMERCIAL COLOR INDEX",
        font=_font(18),
        fill=color,
    )


def _initials(name: str) -> str:
    words = [word for word in name.replace("+", " Plus ").split() if word]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return f"{words[0][0]}{words[-1][0]}".upper()


def _logo_background(logo: Image.Image) -> str:
    rgba = logo.convert("RGBA")
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return PAPER
    cropped = rgba.crop(bbox)
    mask = cropped.getchannel("A")
    stat = ImageStat.Stat(cropped.convert("RGB"), mask=mask)
    r, g, b = stat.mean
    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
    return "#202020" if luminance > 0.83 else "#FFFFFF"


def _draw_logo(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    logo_path: Path | None,
    source_name: str,
) -> None:
    left, top, right, bottom = box
    logo: Image.Image | None = None
    if logo_path and logo_path.exists():
        try:
            logo = Image.open(logo_path).convert("RGBA")
        except OSError:
            logo = None

    background = _logo_background(logo) if logo is not None else "#EFE9DE"
    draw.rounded_rectangle(box, radius=24, fill=background, outline=LINE, width=2)
    if logo is None:
        initials = _initials(source_name)
        font = _fit_font(draw, initials, right - left - 24, 42, 26, bold=True)
        text_box = draw.textbbox((0, 0), initials, font=font)
        x = left + ((right - left) - (text_box[2] - text_box[0])) // 2
        y = top + ((bottom - top) - (text_box[3] - text_box[1])) // 2 - text_box[1]
        draw.text((x, y), initials, font=font, fill=INK)
        return

    available_width = right - left - 30
    available_height = bottom - top - 30
    logo.thumbnail((available_width, available_height), Image.Resampling.LANCZOS)
    x = left + ((right - left) - logo.width) // 2
    y = top + ((bottom - top) - logo.height) // 2
    image.paste(logo, (x, y), logo)
    logo.close()


def _coverage_items(result: DailyResult) -> list[tuple[str, str]]:
    assert result.winner
    return [
        (str(result.panel_size), "COMPANY PAGES\nMONITORED"),
        (str(result.captured_sources), "COMPANY PAGES\nANALYZED"),
        (str(result.winner.source_count), "BRANDS BEHIND\nWINNER"),
        (str(result.winner.sector_count), "SECTORS BEHIND\nWINNER"),
    ]


def _draw_stat_row(
    draw: ImageDraw.ImageDraw,
    items: list[tuple[str, str]],
    *,
    y: int,
    color: str,
    left: int = 74,
    right: int = 1006,
) -> None:
    width = (right - left) / len(items)
    for index, (value, label) in enumerate(items):
        x = int(left + index * width)
        if index:
            draw.line((x - 20, y + 2, x - 20, y + 112), fill=color, width=1)
        draw.text((x, y), value, font=_font(40, bold=True), fill=color)
        draw.text((x, y + 57), label, font=_font(14, bold=True), fill=color, spacing=3)


def render_feed(result: DailyResult, output: Path) -> None:
    assert result.winner and result.winner_name
    winner = result.winner
    image = Image.new("RGB", FEED_SIZE, OFF_WHITE)
    draw = ImageDraw.Draw(image)
    _draw_brand(draw, 62, INK)

    draw.text((74, 190), "YESTERDAY’S CHALLENGER", font=_font(24, bold=True), fill=INK)
    draw.text(
        (1006, 192),
        _human_date(result.date).upper(),
        font=_font(17, bold=True),
        fill=MUTED,
        anchor="ra",
    )

    swatch_box = (70, 250, 1010, 915)
    draw.rounded_rectangle(swatch_box, radius=44, fill=winner.hex)
    foreground = contrast_text_color(winner.hex)
    inverse = PAPER if foreground == "#111111" else INK
    inverse_text = contrast_text_color(inverse)
    draw.text((112, 300), "THE COLOR", font=_font(19, bold=True), fill=foreground)
    name_font = _fit_font(draw, result.winner_name.upper(), 840, 82, 46, bold=True)
    y = _draw_wrapped(
        draw,
        result.winner_name.upper(),
        (108, 382),
        max_width=840,
        font=name_font,
        fill=foreground,
        spacing=5,
        max_lines=3,
    )
    draw.text((112, min(y + 35, 690)), winner.hex, font=_font(36), fill=foreground)

    recurrence_box = (108, 740, 972, 876)
    draw.rounded_rectangle(recurrence_box, radius=28, fill=inverse)
    headline = _recurrence_headline(result)
    headline_font = _fit_font(draw, headline, 800, 24, 18, bold=True)
    draw.text((138, 770), headline, font=headline_font, fill=inverse_text)
    detail = _recurrence_detail(result)
    detail_font = _fit_font(draw, detail, 800, 18, 13, bold=True)
    draw.text((138, 821), detail, font=detail_font, fill=inverse_text)

    draw.text((74, 955), "TODAY’S EVIDENCE", font=_font(18, bold=True), fill=MUTED)
    draw.line((74, 998, 1006, 998), fill=LINE, width=2)
    _draw_stat_row(draw, _coverage_items(result), y=1025, color=INK)
    draw.text(
        (74, 1248),
        f"{winner.source_count} OF {result.captured_sources} ANALYZED COMPANY PAGES CONTRIBUTED TODAY",
        font=_font(16, bold=True),
        fill=MUTED,
    )
    image.save(output, quality=95)

def render_story_color(result: DailyResult, output: Path) -> None:
    assert result.winner and result.winner_name
    winner = result.winner
    foreground = contrast_text_color(winner.hex)
    inverse = PAPER if foreground == "#111111" else INK
    panel_text = contrast_text_color(inverse)
    image = Image.new("RGB", STORY_SIZE, winner.hex)
    draw = ImageDraw.Draw(image)
    _draw_brand(draw, 82, foreground)
    draw.text(
        (74, 370),
        "YESTERDAY’S\nCHALLENGER",
        font=_font(38, bold=True),
        fill=foreground,
        spacing=10,
    )
    name_font = _fit_font(draw, result.winner_name.upper(), 920, 102, 56, bold=True)
    y = _draw_wrapped(
        draw,
        result.winner_name.upper(),
        (74, 625),
        max_width=920,
        font=name_font,
        fill=foreground,
        spacing=8,
        max_lines=4,
    )
    draw.text((74, y + 48), winner.hex, font=_font(40), fill=foreground)

    recurrence_box = (54, 1215, 1026, 1480)
    draw.rounded_rectangle(recurrence_box, radius=38, fill=inverse)
    draw.text((92, 1262), "YEAR-TO-DATE COUNTER", font=_font(18, bold=True), fill=panel_text)
    headline = _recurrence_headline(result)
    headline_font = _fit_font(draw, headline, 900, 35, 23, bold=True)
    draw.text((92, 1310), headline, font=headline_font, fill=panel_text)
    detail = _recurrence_detail(result)
    detail_font = _fit_font(draw, detail, 900, 20, 15, bold=True)
    draw.text((92, 1380), detail, font=detail_font, fill=panel_text)

    panel = (54, 1510, 1026, 1845)
    draw.rounded_rectangle(panel, radius=38, fill=inverse)
    draw.text((92, 1558), "WHAT WAS MEASURED TODAY", font=_font(19, bold=True), fill=panel_text)
    _draw_stat_row(
        draw,
        _coverage_items(result),
        y=1632,
        color=panel_text,
        left=92,
        right=990,
    )
    draw.text(
        (74, 1872),
        _human_date(result.date).upper(),
        font=_font(18, bold=True),
        fill=foreground,
    )
    image.save(output, quality=95)

def render_story_evidence(result: DailyResult, output: Path) -> None:
    assert result.winner and result.winner_name
    winner = result.winner
    image = Image.new("RGB", STORY_SIZE, OFF_WHITE)
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, STORY_SIZE[0], 280), fill=winner.hex)
    foreground = contrast_text_color(winner.hex)
    _draw_brand(draw, 54, foreground)
    draw.text((74, 176), result.winner_name.upper(), font=_font(31, bold=True), fill=foreground)
    draw.text((1006, 185), winner.hex, font=_font(23, bold=True), fill=foreground, anchor="ra")

    draw.text((74, 340), "WHO PUT IT INTO THE WORLD", font=_font(49, bold=True), fill=INK)
    _draw_wrapped(
        draw,
        "The strongest independent brands and organizations contributing to the winning color cluster.",
        (74, 408),
        max_width=930,
        font=_font(20),
        fill=MUTED,
        spacing=5,
        max_lines=2,
    )

    visible_count = min(8, len(winner.source_ids))
    card_width = 448
    card_height = 218
    x_positions = (74, 558)
    top = 500
    row_gap = 22

    for index in range(visible_count):
        row = index // 2
        column = index % 2
        left = x_positions[column]
        y = top + row * (card_height + row_gap)
        right = left + card_width
        draw.rounded_rectangle(
            (left, y, right, y + card_height),
            radius=26,
            fill=PAPER,
            outline=LINE,
            width=2,
        )
        source_id = winner.source_ids[index]
        source_name = winner.source_names[index]
        sector = (
            winner.source_sectors[index]
            if index < len(winner.source_sectors)
            else "commercial source"
        )
        logo_relative = result.source_logos.get(source_id, "")
        logo_path = output.parent / logo_relative if logo_relative else None
        _draw_logo(image, draw, (left + 20, y + 28, left + 132, y + 140), logo_path, source_name)

        name_font = _fit_font(draw, source_name, 270, 29, 21, bold=True)
        name_y = _draw_wrapped(
            draw,
            source_name,
            (left + 153, y + 31),
            max_width=265,
            font=name_font,
            fill=INK,
            spacing=3,
            max_lines=2,
        )
        draw.text(
            (left + 153, max(name_y + 10, y + 104)),
            sector.replace("_", " ").upper(),
            font=_font(15, bold=True),
            fill=MUTED,
        )
        if index < len(winner.source_salience):
            draw.text(
                (left + 20, y + 168),
                f"{winner.source_salience[index] * 100:.1f}% ADJUSTED VISUAL SHARE",
                font=_font(14, bold=True),
                fill=MUTED,
            )

    footer_top = 1510
    draw.rounded_rectangle((74, footer_top, 1006, 1810), radius=30, fill=INK)
    _draw_stat_row(
        draw,
        _coverage_items(result),
        y=1568,
        color=OFF_WHITE,
        left=112,
        right=968,
    )
    hidden = max(winner.source_count - visible_count, 0)
    source_note = (
        f"SHOWING {visible_count} OF {winner.source_count} SUPPORTING BRANDS"
        if hidden
        else f"ALL {winner.source_count} SUPPORTING BRANDS SHOWN"
    )
    draw.text((112, 1734), source_note, font=_font(17, bold=True), fill="#C8C4BC")
    draw.text(
        (74, 1858),
        "Brand marks identify monitored sources; no endorsement or affiliation is implied.",
        font=_font(15),
        fill=MUTED,
    )
    image.save(output, quality=95)


def render_story_why(result: DailyResult, output: Path) -> None:
    assert result.winner and result.winner_name
    winner = result.winner
    recurrence = result.recurrence
    image = Image.new("RGB", STORY_SIZE, "#111111")
    draw = ImageDraw.Draw(image)
    _draw_brand(draw, 82, OFF_WHITE)

    draw.rounded_rectangle((74, 245, 254, 425), radius=34, fill=winner.hex)
    draw.text((294, 258), "WHY IT WON", font=_font(57, bold=True), fill=OFF_WHITE)
    draw.text((298, 340), result.winner_name.upper(), font=_font(22, bold=True), fill=winner.hex)
    draw.text((298, 378), winner.hex, font=_font(20), fill="#B7B7B7")

    recurrence_value = (
        f"{recurrence.winning_days} winning days as {recurrence.family_name} in {recurrence.year}"
        if recurrence
        else "First recorded win in the year-to-date archive"
    )
    rows = [
        (
            "PANEL COVERAGE",
            f"{result.captured_sources} of {result.panel_size} company pages analyzed "
            f"({max(result.panel_size - result.captured_sources, 0)} unavailable)",
        ),
        ("INDEPENDENT SUPPORT", f"{winner.source_count} companies backed this color today"),
        ("CROSS-INDUSTRY SPREAD", f"{winner.sector_count} of {result.captured_sectors} analyzed sectors today"),
        ("YEAR-TO-DATE", recurrence_value),
        ("VISUAL SALIENCE", f"{winner.mean_salience * 100:.1f}% mean adjusted share"),
    ]
    if result.baseline_days >= 7:
        ratio = (winner.prevalence + 0.02) / (winner.baseline_prevalence + 0.02)
        rows.append(("MOMENTUM", f"{ratio:.2f}× its trailing baseline"))
    else:
        rows.append(("BASELINE", f"Day {result.baseline_days + 1} of calibration"))

    top = 490
    row_height = 180
    for index, (label, value) in enumerate(rows):
        y = top + index * row_height
        draw.text((74, y), label, font=_font(18, bold=True), fill="#A7A7A7")
        value_font = _fit_font(draw, value, 900, 37, 25, bold=True)
        draw.text((74, y + 45), value, font=value_font, fill=OFF_WHITE)
        draw.line((74, y + 127, 1006, y + 127), fill="#414141", width=2)

    draw.text(
        (74, 1605),
        f"CHALLENGER SCORE  {winner.score:.1f}",
        font=_font(31, bold=True),
        fill=winner.hex,
    )
    note = (
        "The computer selects the color using the published method. "
        "A person may block bad data, but cannot replace an unattractive winner."
    )
    _draw_wrapped(
        draw,
        note,
        (74, 1680),
        max_width=900,
        font=_font(22),
        fill=OFF_WHITE,
        spacing=10,
    )
    image.save(output, quality=95)

def _runner_name(result: DailyResult, index: int, candidate: Candidate) -> str:
    if index < len(result.runner_up_names):
        return result.runner_up_names[index]
    return candidate.hex


def render_story_runners(result: DailyResult, output: Path) -> None:
    image = Image.new("RGB", STORY_SIZE, OFF_WHITE)
    draw = ImageDraw.Draw(image)
    _draw_brand(draw, 82, INK)
    draw.text((74, 245), "RUNNERS-UP", font=_font(60, bold=True), fill=INK)
    draw.text(
        (74, 325),
        "The next three strongest independently supported color clusters.",
        font=_font(22),
        fill=MUTED,
    )

    candidates = result.runners_up[:3]
    top = 430
    height = 390
    gap = 45
    for index, candidate in enumerate(candidates):
        y = top + index * (height + gap)
        draw.rounded_rectangle((74, y, 1006, y + height), radius=34, fill=PAPER, outline=LINE, width=2)
        draw.rounded_rectangle((96, y + 22, 382, y + height - 22), radius=28, fill=candidate.hex)
        swatch_text = contrast_text_color(candidate.hex)
        draw.text((124, y + 55), f"#{index + 2}", font=_font(25, bold=True), fill=swatch_text)
        draw.text((124, y + 292), candidate.hex, font=_font(29, bold=True), fill=swatch_text)

        name = _runner_name(result, index, candidate)
        name_font = _fit_font(draw, name.upper(), 560, 42, 28, bold=True)
        name_y = _draw_wrapped(
            draw,
            name.upper(),
            (424, y + 52),
            max_width=530,
            font=name_font,
            fill=INK,
            spacing=4,
            max_lines=3,
        )
        draw.text(
            (424, max(name_y + 25, y + 205)),
            f"{candidate.source_count} COMPANIES · {candidate.sector_count} SECTORS",
            font=_font(19, bold=True),
            fill=MUTED,
        )
        draw.text(
            (424, y + 298),
            f"CHALLENGER SCORE {candidate.score:.1f}",
            font=_font(21, bold=True),
            fill=INK,
        )

    draw.text(
        (74, 1788),
        f"PANEL: {result.panel_size} COMPANY PAGES MONITORED · "
        f"{result.captured_sources} ANALYZED · "
        f"{result.captured_sectors} SECTORS",
        font=_font(18, bold=True),
        fill=MUTED,
    )
    image.save(output, quality=95)


def build_caption(result: DailyResult) -> str:
    assert result.winner and result.winner_name
    winner = result.winner
    baseline = (
        f"It appeared at {((winner.prevalence + 0.02) / (winner.baseline_prevalence + 0.02)):.2f}× "
        "its trailing prevalence."
        if result.baseline_days >= 7
        else "The index is still calibrating its 30-day baseline."
    )
    sectors = ", ".join(item.replace("_", " ") for item in winner.sectors[:5])
    supporting = ", ".join(winner.source_names[:8])
    if winner.source_count > 8:
        supporting += f", and {winner.source_count - 8} more"
    runner_lines = []
    for index, candidate in enumerate(result.runners_up[:3]):
        runner_lines.append(
            f"#{index + 2} {_runner_name(result, index, candidate)} "
            f"({candidate.hex}) — {candidate.source_count} sources"
        )
    runners = "\n".join(runner_lines)

    return (
        f"Yesterday’s Challenger was {result.winner_name} ({winner.hex}).\n\n"
        f"YEAR-TO-DATE\n{_recurrence_sentence(result)}\n\n"
        f"PANEL COVERAGE\n"
        f"{result.panel_size} company pages monitored · {result.captured_sources} successfully analyzed · "
        f"{max(result.panel_size - result.captured_sources, 0)} unavailable · "
        f"{result.captured_sectors} analyzed sectors\n\n"
        f"WHY IT SURFACED TODAY\n"
        f"{winner.source_count} independent sources across {winner.sector_count} sectors"
        f"{f'—including {sectors}' if sectors else ''}.\n"
        f"Supporting sources included {supporting}.\n\n"
        f"{baseline}\n\n"
        f"RUNNERS-UP\n{runners}\n\n"
        "The algorithm chooses the color. It does not get replaced for being ugly.\n\n"
        "Pantone Challenger is an independent computational art project and is not "
        "affiliated with or endorsed by Pantone LLC. Company marks identify monitored "
        "sources and do not imply endorsement.\n\n"
        "#PantoneChallenger #ColorTrends #MarketingTrends #CreativeTechnology"
    )

def build_review_summary(result: DailyResult) -> str:
    assert result.winner and result.winner_name
    winner = result.winner
    source_rows = []
    for index, name in enumerate(winner.source_names):
        sector = (
            winner.source_sectors[index].replace("_", " ")
            if index < len(winner.source_sectors)
            else "commercial source"
        )
        source_rows.append(f"- **{name}** — {sector}")
    runner_rows = []
    for index, candidate in enumerate(result.runners_up[:3]):
        runner_rows.append(
            f"- **#{index + 2} {_runner_name(result, index, candidate)}** "
            f"`{candidate.hex}` — {candidate.source_count} sources, "
            f"{candidate.sector_count} sectors, score {candidate.score:.1f}"
        )
    recurrence = result.recurrence
    recurrence_rows = [
        "## Year-to-date recurrence",
        "",
        _recurrence_sentence(result),
    ]
    if recurrence:
        recurrence_rows.extend(
            [
                "",
                f"- **Color family:** {recurrence.family_name} `{recurrence.representative_hex}`",
                f"- **Winning dates:** {', '.join(recurrence.matching_dates)}",
                f"- **Current / longest streak:** {recurrence.current_streak} / {recurrence.longest_streak} days",
                f"- **Unique companies across those wins:** {recurrence.unique_company_count} / {recurrence.panel_company_count}",
                f"- **Sectors across those wins:** {human_sector_list(recurrence.sectors, limit=0)}",
                f"- **Matching rule:** OKLab distance ≤ {recurrence.distance_threshold:.3f}; exact HEX matches are not required.",
            ]
        )
    return "\n".join(
        [
            f"# Yesterday’s Challenger — {result.date}",
            "",
            "![Winner social card](feed-post.png)",
            "",
            "## Coverage",
            "",
            "| Company pages monitored | Successfully analyzed | Unavailable | Analyzed sectors | Winner support |",
            "|---:|---:|---:|---:|---:|",
            f"| {result.panel_size} | {result.captured_sources} | "
            f"{max(result.panel_size - result.captured_sources, 0)} | {result.captured_sectors} | "
            f"{winner.source_count} sources / {winner.sector_count} sectors |",
            "",
            *recurrence_rows,
            "",
            f"## Winner: {result.winner_name} `{winner.hex}`",
            "",
            "### Supporting sources",
            *source_rows,
            "",
            "## Runners-up",
            *runner_rows,
            "",
            "## Story assets",
            "",
            "![Supporting companies](story-02-evidence.png)",
            "",
            "![Why it won](story-03-why-it-won.png)",
            "",
            "![Runners-up](story-04-runners-up.png)",
            "",
            "> Review the capture report and observations before approving. "
            "Merging the pull request approves the measured result; it does not change "
            "the algorithmic winner.",
        ]
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
    (output_dir / "review-summary.md").write_text(
        build_review_summary(result), encoding="utf-8"
    )
    return outputs
