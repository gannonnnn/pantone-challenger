from __future__ import annotations

from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .colors import contrast_text_color
from .models import Candidate, CandidateEvidence, DailyResult
from .recurrence import human_sector_list


FEED_SIZE = (1080, 1350)
STORY_SIZE = (1080, 1920)
OFF_WHITE = "#F5F1E8"
PAPER = "#FBF9F4"
INK = "#171717"
MUTED = "#6D6A64"
LINE = "#D9D2C5"
WARNING = "#C44735"


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


def _draw_brand(draw: ImageDraw.ImageDraw, y: int, color: str) -> None:
    draw.text((74, y), "PANTONE CHALLENGER", font=_font(29, bold=True), fill=color)
    draw.text((74, y + 43), "THE COMMERCIAL COLOR INDEX", font=_font(18), fill=color)


def _draw_calibration_banner(draw: ImageDraw.ImageDraw, *, width: int, y: int = 0) -> None:
    draw.rectangle((0, y, width, y + 54), fill=WARNING)
    draw.text(
        (width // 2, y + 27),
        "INTERNAL CALIBRATION — NOT FOR POSTING",
        font=_font(18, bold=True),
        fill="#FFFFFF",
        anchor="mm",
    )


def _recurrence_headline(result: DailyResult) -> str:
    if result.status == "review_only":
        return f"INTERNAL CALIBRATION · DAY {result.calibration_day}"
    recurrence = result.recurrence
    if not recurrence:
        return "FIRST APPROVED WIN"
    unit = "DAY" if recurrence.winning_days == 1 else "DAYS"
    return f"{recurrence.winning_days} {unit} AS THE TOP COMMERCIAL COLOR IN {recurrence.year}"


def _recurrence_detail(result: DailyResult) -> str:
    if result.status == "review_only":
        return "NOT ADDED TO THE PUBLIC ARCHIVE OR YEAR-TO-DATE COUNTER"
    recurrence = result.recurrence
    if not recurrence:
        return "YEAR-TO-DATE HISTORY BEGINS WITH THIS APPROVED RESULT"
    return (
        f"{recurrence.family_name.upper()} · "
        f"{recurrence.unique_company_count} / {recurrence.panel_company_count} COMPANIES · "
        f"{recurrence.sector_count} SECTORS"
    )


def _recurrence_sentence(result: DailyResult) -> str:
    if result.status == "review_only":
        return (
            f"This is internal calibration day {result.calibration_day}. It does not count "
            "toward recurrence or the year-end summary until the method exits calibration."
        )
    recurrence = result.recurrence
    if not recurrence:
        return "This approved result begins the year-to-date color history."
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


def _coverage_items(result: DailyResult) -> list[tuple[str, str]]:
    assert result.winner
    return [
        (str(result.panel_size), "COMPANY PAGES\nMONITORED"),
        (str(result.captured_sources), "COMPANY PAGES\nWITH EVIDENCE"),
        (str(result.winner.source_count), "COMPANIES BEHIND\nWINNER"),
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


def _candidate_display_name(candidate: Candidate, fallback: str) -> str:
    if candidate.creative_name and candidate.family_label:
        return f"{candidate.creative_name} {candidate.family_label}"
    return fallback


def _draw_curated_mark(
    image: Image.Image,
    box: tuple[int, int, int, int],
    mark_path: Path | None,
) -> bool:
    if not mark_path or not mark_path.exists():
        return False
    try:
        with Image.open(mark_path) as opened:
            mark = opened.convert("RGBA")
    except OSError:
        return False
    alpha = mark.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        mark.close()
        return False
    mark = mark.crop(bbox)
    left, top, right, bottom = box
    available_width = right - left
    available_height = bottom - top
    scale = min(available_width / mark.width, available_height / mark.height, 2.0)
    if scale <= 0:
        mark.close()
        return False
    mark = mark.resize(
        (max(1, round(mark.width * scale)), max(1, round(mark.height * scale))),
        Image.Resampling.LANCZOS,
    )
    x = left + (available_width - mark.width) // 2
    y = top + (available_height - mark.height) // 2
    image.paste(mark, (x, y), mark)
    mark.close()
    return True


def render_feed(result: DailyResult, output: Path) -> None:
    assert result.winner and result.winner_name
    winner = result.winner
    image = Image.new("RGB", FEED_SIZE, OFF_WHITE)
    draw = ImageDraw.Draw(image)
    if result.status == "review_only":
        _draw_calibration_banner(draw, width=FEED_SIZE[0])
    _draw_brand(draw, 78 if result.status == "review_only" else 62, INK)

    draw.text((74, 196), "YESTERDAY’S CHALLENGER", font=_font(24, bold=True), fill=INK)
    draw.text(
        (1006, 198),
        _human_date(result.date).upper(),
        font=_font(17, bold=True),
        fill=MUTED,
        anchor="ra",
    )

    swatch_box = (70, 250, 1010, 915)
    draw.rounded_rectangle(swatch_box, radius=44, fill=winner.hex, outline=LINE, width=3)
    foreground = contrast_text_color(winner.hex)
    inverse = PAPER if foreground == "#111111" else INK
    inverse_text = contrast_text_color(inverse)
    draw.text((112, 300), "THE COLOR", font=_font(19, bold=True), fill=foreground)
    name_font = _fit_font(draw, result.winner_name.upper(), 840, 76, 42, bold=True)
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
    family = winner.family_label.upper() if winner.family_label else "COLOR FAMILY"
    draw.text((112, min(y + 22, 672)), family, font=_font(22, bold=True), fill=foreground)
    draw.text((112, min(y + 64, 714)), winner.hex, font=_font(34), fill=foreground)

    recurrence_box = (108, 740, 972, 876)
    draw.rounded_rectangle(recurrence_box, radius=28, fill=inverse)
    headline = _recurrence_headline(result)
    draw.text(
        (138, 770),
        headline,
        font=_fit_font(draw, headline, 800, 24, 17, bold=True),
        fill=inverse_text,
    )
    detail = _recurrence_detail(result)
    draw.text(
        (138, 821),
        detail,
        font=_fit_font(draw, detail, 800, 18, 12, bold=True),
        fill=inverse_text,
    )

    draw.text((74, 955), "TRACEABLE EVIDENCE", font=_font(18, bold=True), fill=MUTED)
    draw.line((74, 998, 1006, 998), fill=LINE, width=2)
    _draw_stat_row(draw, _coverage_items(result), y=1025, color=INK)
    draw.text(
        (74, 1242),
        f"CONFIDENCE: {winner.confidence.upper()} · "
        f"{winner.source_count} OF {result.captured_sources} EVIDENCE-BEARING COMPANY PAGES MATCHED",
        font=_font(15, bold=True),
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
    if result.status == "review_only":
        _draw_calibration_banner(draw, width=STORY_SIZE[0])
    _draw_brand(draw, 92 if result.status == "review_only" else 82, foreground)
    draw.text(
        (74, 370),
        "YESTERDAY’S\nCHALLENGER",
        font=_font(38, bold=True),
        fill=foreground,
        spacing=10,
    )
    name_font = _fit_font(draw, result.winner_name.upper(), 920, 96, 52, bold=True)
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
    draw.text((74, y + 34), winner.family_label.upper(), font=_font(25, bold=True), fill=foreground)
    draw.text((74, y + 82), winner.hex, font=_font(40), fill=foreground)

    recurrence_box = (54, 1215, 1026, 1480)
    draw.rounded_rectangle(recurrence_box, radius=38, fill=inverse)
    draw.text((92, 1262), "HISTORY STATUS", font=_font(18, bold=True), fill=panel_text)
    headline = _recurrence_headline(result)
    draw.text(
        (92, 1310),
        headline,
        font=_fit_font(draw, headline, 900, 35, 23, bold=True),
        fill=panel_text,
    )
    detail = _recurrence_detail(result)
    draw.text(
        (92, 1380),
        detail,
        font=_fit_font(draw, detail, 900, 20, 14, bold=True),
        fill=panel_text,
    )

    panel = (54, 1510, 1026, 1845)
    draw.rounded_rectangle(panel, radius=38, fill=inverse)
    draw.text((92, 1558), "WHAT WAS MEASURED", font=_font(19, bold=True), fill=panel_text)
    _draw_stat_row(draw, _coverage_items(result), y=1632, color=panel_text, left=92, right=990)
    draw.text((74, 1872), _human_date(result.date).upper(), font=_font(18, bold=True), fill=foreground)
    image.save(output, quality=95)


def _draw_evidence_card(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    evidence: CandidateEvidence,
    *,
    box: tuple[int, int, int, int],
    mark_path: Path | None,
) -> None:
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=25, fill=PAPER, outline=LINE, width=2)
    swatch_box = (left + 20, top + 24, left + 126, top + 130)
    draw.rounded_rectangle(swatch_box, radius=22, fill=evidence.local_hex, outline="#BDB5A8", width=3)
    draw.text(
        (left + 73, top + 144),
        evidence.local_hex,
        font=_font(13, bold=True),
        fill=MUTED,
        anchor="ma",
    )

    name_y = _draw_wrapped(
        draw,
        evidence.source_name,
        (left + 148, top + 25),
        max_width=245,
        font=_fit_font(draw, evidence.source_name, 245, 27, 19, bold=True),
        fill=INK,
        spacing=2,
        max_lines=2,
    )
    draw.text(
        (left + 148, max(name_y + 7, top + 91)),
        evidence.sector.replace("_", " ").upper(),
        font=_font(14, bold=True),
        fill=MUTED,
    )
    _draw_curated_mark(image, (right - 75, top + 22, right - 20, top + 72), mark_path)
    draw.text(
        (left + 148, top + 137),
        f"{evidence.local_share * 100:.1f}% MATCHED COLOR SHARE",
        font=_font(13, bold=True),
        fill=INK,
    )
    draw.text(
        (left + 148, top + 166),
        f"REGION CONFIDENCE {evidence.region_confidence:.0%}",
        font=_font(12, bold=True),
        fill=MUTED,
    )


def render_story_evidence(result: DailyResult, output: Path) -> None:
    assert result.winner and result.winner_name
    winner = result.winner
    image = Image.new("RGB", STORY_SIZE, OFF_WHITE)
    draw = ImageDraw.Draw(image)
    if result.status == "review_only":
        _draw_calibration_banner(draw, width=STORY_SIZE[0])

    header_top = 54 if result.status == "review_only" else 0
    draw.rectangle((0, header_top, STORY_SIZE[0], header_top + 270), fill=winner.hex)
    foreground = contrast_text_color(winner.hex)
    _draw_brand(draw, header_top + 46, foreground)
    draw.text((74, header_top + 173), result.winner_name.upper(), font=_font(29, bold=True), fill=foreground)
    draw.text((1006, header_top + 182), winner.hex, font=_font(23, bold=True), fill=foreground, anchor="ra")

    title_y = header_top + 320
    draw.text((74, title_y), "WHERE THE COLOR MATCH APPEARED", font=_font(45, bold=True), fill=INK)
    _draw_wrapped(
        draw,
        "Each card shows the local color measured inside that company’s sampled marketing creative. A logo is attribution only and is shown only when manually approved.",
        (74, title_y + 64),
        max_width=930,
        font=_font(18),
        fill=MUTED,
        spacing=4,
        max_lines=3,
    )

    visible = winner.evidence[:8]
    card_width = 448
    card_height = 210
    x_positions = (74, 558)
    top = title_y + 175
    row_gap = 20
    for index, evidence in enumerate(visible):
        row = index // 2
        column = index % 2
        left = x_positions[column]
        y = top + row * (card_height + row_gap)
        logo_relative = result.source_logos.get(evidence.source_id, "")
        logo_path = output.parent / logo_relative if logo_relative else None
        _draw_evidence_card(
            image,
            draw,
            evidence,
            box=(left, y, left + card_width, y + card_height),
            mark_path=logo_path,
        )

    footer_top = 1518
    draw.rounded_rectangle((74, footer_top, 1006, 1810), radius=30, fill=INK)
    _draw_stat_row(draw, _coverage_items(result), y=1565, color=OFF_WHITE, left=112, right=968)
    draw.text(
        (112, 1735),
        f"SHOWING {len(visible)} OF {winner.source_count} TRACEABLE COMPANY MATCHES",
        font=_font(16, bold=True),
        fill="#C8C4BC",
    )
    draw.text(
        (74, 1855),
        "Full source-region screenshots stay in the private review artifact.",
        font=_font(15),
        fill=MUTED,
    )
    image.save(output, quality=95)


def render_story_why(result: DailyResult, output: Path) -> None:
    assert result.winner and result.winner_name
    winner = result.winner
    image = Image.new("RGB", STORY_SIZE, "#111111")
    draw = ImageDraw.Draw(image)
    if result.status == "review_only":
        _draw_calibration_banner(draw, width=STORY_SIZE[0])
    _draw_brand(draw, 92 if result.status == "review_only" else 82, OFF_WHITE)

    draw.rounded_rectangle((74, 245, 254, 425), radius=34, fill=winner.hex, outline="#565656", width=2)
    draw.text((294, 258), "WHY IT SURFACED", font=_font(50, bold=True), fill=OFF_WHITE)
    draw.text((298, 340), result.winner_name.upper(), font=_font(21, bold=True), fill=winner.hex)
    draw.text((298, 378), f"{winner.family_label.upper()} · {winner.hex}", font=_font(18), fill="#B7B7B7")

    rows = [
        ("PANEL COVERAGE", f"{result.captured_sources} of {result.panel_size} company pages produced eligible creative evidence"),
        ("INDEPENDENT SUPPORT", f"{winner.source_count} companies across {winner.sector_count} sectors"),
        ("TRACEABILITY", f"{winner.evidence_region_count} source-linked creative regions"),
        ("EVIDENCE QUALITY", f"{winner.mean_evidence_confidence:.0%} mean region confidence"),
        ("CONCENTRATION", f"Top company {winner.top_source_weight:.0%} · top sector {winner.top_sector_weight:.0%}"),
        ("RANKING MARGIN", f"{winner.score_margin_to_next:.1f} points over the next qualified color"),
    ]
    if result.baseline_days >= 7:
        ratio = (winner.prevalence + 0.02) / (winner.baseline_prevalence + 0.02)
        rows.append(("MOMENTUM", f"{ratio:.2f}× its trailing baseline"))
    else:
        rows.append(("BASELINE", f"Internal calibration day {result.calibration_day}"))

    top = 480
    row_height = 155
    for index, (label, value) in enumerate(rows):
        y = top + index * row_height
        draw.text((74, y), label, font=_font(17, bold=True), fill="#A7A7A7")
        draw.text(
            (74, y + 40),
            value,
            font=_fit_font(draw, value, 900, 31, 22, bold=True),
            fill=OFF_WHITE,
        )
        draw.line((74, y + 112, 1006, y + 112), fill="#414141", width=2)

    draw.text(
        (74, 1620),
        f"CHALLENGER SCORE {winner.score:.1f} · CONFIDENCE {winner.confidence.upper()}",
        font=_font(27, bold=True),
        fill=winner.hex,
    )
    _draw_wrapped(
        draw,
        "The result can be rejected for weak or incorrect evidence. The reviewer cannot replace it with a prettier color.",
        (74, 1690),
        max_width=900,
        font=_font(21),
        fill=OFF_WHITE,
        spacing=9,
    )
    image.save(output, quality=95)


def _runner_name(result: DailyResult, index: int, candidate: Candidate) -> str:
    if index < len(result.runner_up_names):
        return result.runner_up_names[index]
    return _candidate_display_name(candidate, candidate.hex)


def render_story_runners(result: DailyResult, output: Path) -> None:
    image = Image.new("RGB", STORY_SIZE, OFF_WHITE)
    draw = ImageDraw.Draw(image)
    if result.status == "review_only":
        _draw_calibration_banner(draw, width=STORY_SIZE[0])
    _draw_brand(draw, 92 if result.status == "review_only" else 82, INK)
    draw.text((74, 245), "RUNNERS-UP", font=_font(60, bold=True), fill=INK)
    draw.text(
        (74, 325),
        "Only perceptually distinct colors with traceable cross-company evidence are shown.",
        font=_font(20),
        fill=MUTED,
    )

    candidates = result.runners_up[:3]
    top = 430
    height = 390
    gap = 45
    for index, candidate in enumerate(candidates):
        y = top + index * (height + gap)
        draw.rounded_rectangle((74, y, 1006, y + height), radius=34, fill=PAPER, outline=LINE, width=2)
        draw.rounded_rectangle(
            (96, y + 22, 382, y + height - 22),
            radius=28,
            fill=candidate.hex,
            outline="#AFA79A",
            width=4,
        )
        swatch_text = contrast_text_color(candidate.hex)
        draw.text((124, y + 55), f"#{index + 2}", font=_font(25, bold=True), fill=swatch_text)
        draw.text((124, y + 292), candidate.hex, font=_font(29, bold=True), fill=swatch_text)

        name = _runner_name(result, index, candidate)
        name_y = _draw_wrapped(
            draw,
            name.upper(),
            (424, y + 48),
            max_width=530,
            font=_fit_font(draw, name.upper(), 560, 40, 26, bold=True),
            fill=INK,
            spacing=4,
            max_lines=3,
        )
        draw.text(
            (424, max(name_y + 16, y + 185)),
            candidate.family_label.upper(),
            font=_font(18, bold=True),
            fill=MUTED,
        )
        draw.text(
            (424, y + 238),
            f"{candidate.source_count} COMPANIES · {candidate.sector_count} SECTORS",
            font=_font(18, bold=True),
            fill=MUTED,
        )
        draw.text(
            (424, y + 298),
            f"SCORE {candidate.score:.1f} · CONFIDENCE {candidate.confidence.upper()}",
            font=_font(19, bold=True),
            fill=INK,
        )

    if not candidates:
        _draw_wrapped(
            draw,
            "No other color met the minimum evidence and distinctness requirements today.",
            (74, 540),
            max_width=900,
            font=_font(35, bold=True),
            fill=INK,
            spacing=10,
        )
    elif len(candidates) < 3:
        plural = "s" if len(candidates) != 1 else ""
        draw.text(
            (74, top + len(candidates) * (height + gap) + 20),
            f"Only {len(candidates)} qualified runner-up color{plural} today.",
            font=_font(22, bold=True),
            fill=MUTED,
        )

    draw.text(
        (74, 1788),
        f"PANEL: {result.panel_size} MONITORED · {result.captured_sources} WITH EVIDENCE · "
        f"{result.captured_sectors} SECTORS",
        font=_font(17, bold=True),
        fill=MUTED,
    )
    image.save(output, quality=95)


def build_caption(result: DailyResult) -> str:
    assert result.winner and result.winner_name
    winner = result.winner
    evidence_names = ", ".join(item.source_name for item in winner.evidence[:8])
    if winner.source_count > 8:
        evidence_names += f", and {winner.source_count - 8} more"
    runner_lines = [
        f"#{index + 2} {_runner_name(result, index, candidate)} ({candidate.hex}) — "
        f"{candidate.source_count} companies / {candidate.sector_count} sectors"
        for index, candidate in enumerate(result.runners_up[:3])
    ]
    runners = "\n".join(runner_lines) or "No additional color met the public evidence threshold."
    prefix = "INTERNAL CALIBRATION — DO NOT POST\n\n" if result.status == "review_only" else ""
    return (
        f"{prefix}Yesterday’s Challenger was {result.winner_name} ({winner.hex}).\n\n"
        f"COLOR FAMILY\n{winner.family_label}\n\n"
        f"HISTORY\n{_recurrence_sentence(result)}\n\n"
        f"PANEL COVERAGE\n{result.panel_size} company pages monitored · "
        f"{result.captured_sources} produced eligible creative evidence · "
        f"{max(result.panel_size - result.captured_sources, 0)} unavailable or unusable · "
        f"{result.captured_sectors} sectors\n\n"
        f"TRACEABLE SUPPORT\n{winner.source_count} companies across {winner.sector_count} sectors. "
        f"Evidence included {evidence_names}.\n\n"
        f"RUNNERS-UP\n{runners}\n\n"
        "The algorithm selects the color. A reviewer can reject weak evidence but cannot replace the winner for aesthetics.\n\n"
        "Pantone Challenger is independent and is not affiliated with or endorsed by Pantone LLC."
    )


def build_review_summary(result: DailyResult) -> str:
    assert result.winner and result.winner_name
    winner = result.winner
    evidence_rows = [
        "| Company | Sector | Local swatch | Distance | Region confidence | Matched share |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for item in winner.evidence:
        evidence_rows.append(
            f"| {item.source_name} | {item.sector.replace('_', ' ')} | `{item.local_hex}` | "
            f"{item.distance_to_candidate:.3f} | {item.region_confidence:.0%} | "
            f"{item.local_share:.1%} |"
        )
    runner_rows = [
        f"- **#{index + 2} {_runner_name(result, index, candidate)}** `{candidate.hex}` — "
        f"{candidate.source_count} companies, {candidate.sector_count} sectors, "
        f"score {candidate.score:.1f}"
        for index, candidate in enumerate(result.runners_up[:3])
    ] or ["- No additional candidate met the runner-up requirements."]
    warnings = [f"- {warning}" for warning in result.quality_gate.warnings] or ["- None"]
    title = "Calibration Review" if result.status == "review_only" else "Yesterday’s Challenger"
    state_note = (
        "> **INTERNAL CALIBRATION — DO NOT POST.**"
        if result.status == "review_only"
        else "> Ready for human review; merging approves the measured result."
    )
    return "\n".join(
        [
            f"# {title} — {result.date}",
            "",
            state_note,
            "",
            "![Winner card](feed-post.png)",
            "",
            "## Publication state",
            "",
            f"- **State:** `{result.status}`",
            f"- **Confidence:** {winner.confidence}",
            f"- **Methodology / registry:** {result.methodology_version} / {result.registry_version}",
            "",
            "## Coverage",
            "",
            "| Monitored | With eligible evidence | Unavailable/unusable | Sectors | Winner support |",
            "|---:|---:|---:|---:|---:|",
            f"| {result.panel_size} | {result.captured_sources} | "
            f"{max(result.panel_size - result.captured_sources, 0)} | {result.captured_sectors} | "
            f"{winner.source_count} companies / {winner.sector_count} sectors |",
            "",
            "## Quality warnings",
            "",
            *warnings,
            "",
            f"## Winner: {result.winner_name} `{winner.hex}`",
            "",
            f"- **Color family:** {winner.family_label}",
            f"- **Score / margin:** {winner.score:.1f} / {winner.score_margin_to_next:.1f}",
            f"- **Top company / sector weight:** {winner.top_source_weight:.1%} / {winner.top_sector_weight:.1%}",
            f"- **Mean region confidence / color distance:** {winner.mean_evidence_confidence:.1%} / {winner.mean_evidence_distance:.3f}",
            "",
            "## Traceable source evidence",
            "",
            *evidence_rows,
            "",
            "![Local source swatches](story-02-evidence.png)",
            "",
            "## Runners-up",
            "",
            *runner_rows,
            "",
            "![Runner-up colors](story-04-runners-up.png)",
            "",
            "## Private review artifact",
            "",
            "The workflow artifact contains an evidence contact sheet with the sampled creative regions. It is not part of the public social package.",
        ]
    )


def _write_alt_text(result: DailyResult, output_dir: Path) -> list[Path]:
    assert result.winner and result.winner_name
    winner = result.winner
    files = {
        "feed-alt-text.txt": (
            f"A large {winner.family_label.lower()} color field labeled {result.winner_name}, "
            f"{winner.hex}. Pantone Challenger monitored {result.panel_size} company pages; "
            f"{result.captured_sources} produced eligible evidence, and {winner.source_count} "
            f"companies across {winner.sector_count} sectors supported the result."
        ),
        "story-01-alt-text.txt": (
            f"Full-screen color reveal for {result.winner_name}, {winner.hex}, with the "
            f"publication state {result.status}."
        ),
        "story-02-alt-text.txt": (
            "Evidence cards showing the local swatches measured in sampled marketing creative "
            f"from {winner.source_count} companies behind the winning color."
        ),
        "story-03-alt-text.txt": (
            f"Evidence summary for {result.winner_name}: {winner.source_count} companies, "
            f"{winner.sector_count} sectors, {winner.evidence_region_count} traceable regions, "
            f"and {winner.confidence.lower()} confidence."
        ),
        "story-04-alt-text.txt": (
            "Runner-up color swatches with their hexadecimal values, company counts, sector "
            "counts, and scores."
        ),
    }
    outputs: list[Path] = []
    for name, text in files.items():
        path = output_dir / name
        path.write_text(text, encoding="utf-8")
        outputs.append(path)
    return outputs


def render_evidence_contact_sheet(result: DailyResult, output: Path) -> None:
    if not result.winner:
        return
    evidence = result.winner.evidence[:12]
    width = 1600
    card_height = 310
    height = 150 + max(len(evidence), 1) * card_height
    image = Image.new("RGB", (width, height), "#E9E5DD")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 70), fill=WARNING)
    draw.text(
        (width // 2, 35),
        "PRIVATE REVIEW EVIDENCE — DO NOT POST OR REPUBLISH",
        font=_font(25, bold=True),
        fill="#FFFFFF",
        anchor="mm",
    )
    draw.text(
        (50, 95),
        f"{result.date} · {result.winner_name} · {result.winner.hex}",
        font=_font(26, bold=True),
        fill=INK,
    )
    for index, item in enumerate(evidence):
        top = 145 + index * card_height
        draw.rounded_rectangle(
            (40, top, width - 40, top + 280),
            radius=24,
            fill=PAPER,
            outline=LINE,
            width=2,
        )
        region_path = Path(item.region_path)
        if region_path.exists():
            try:
                with Image.open(region_path) as opened:
                    region = opened.convert("RGB")
                region.thumbnail((620, 230), Image.Resampling.LANCZOS)
                image.paste(region, (65, top + 25))
                region.close()
            except OSError:
                pass
        draw.rounded_rectangle(
            (720, top + 30, 840, top + 150),
            radius=20,
            fill=item.local_hex,
            outline="#AAA296",
            width=3,
        )
        draw.text((720, top + 172), item.local_hex, font=_font(19, bold=True), fill=INK)
        draw.text((880, top + 32), item.source_name, font=_font(30, bold=True), fill=INK)
        draw.text(
            (880, top + 78),
            item.sector.replace("_", " ").upper(),
            font=_font(18, bold=True),
            fill=MUTED,
        )
        draw.text((880, top + 125), f"Distance to winner: {item.distance_to_candidate:.3f}", font=_font(18), fill=INK)
        draw.text((880, top + 162), f"Region confidence: {item.region_confidence:.0%}", font=_font(18), fill=INK)
        draw.text((880, top + 199), f"Matched share: {item.local_share:.1%}", font=_font(18), fill=INK)
        draw.text((880, top + 236), item.source_url[:70], font=_font(14), fill=MUTED)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, quality=92)


def render_daily(result: DailyResult, output_dir: Path) -> list[Path]:
    if result.status == "blocked" or not result.winner:
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
    (output_dir / "review-summary.md").write_text(build_review_summary(result), encoding="utf-8")
    outputs.extend(_write_alt_text(result, output_dir))
    return outputs
