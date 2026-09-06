from __future__ import annotations

from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from challenger.color import contrast_ratio, readable_text_color
from challenger.image_quality import trim_and_fit_logo
from challenger.models import PublicationState


BG = "#F6F1E9"
INK = "#161616"
MUTED = "#6B655E"
CARD = "#FFFDF9"
BORDER = "#D8D0C5"
ACCENT = "#C9FF47"


def render_daily(result, output_dir: str | Path, source_map: dict, settings: dict) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = []
    if result.state == PublicationState.BASELINE_ONLY:
        files.append(_render_baseline(result, out / "baseline-summary.png"))
        _write_text_assets(result, out)
        return files
    if not result.challenger:
        files.append(_render_review(result, out / "review-summary.png"))
        _write_text_assets(result, out)
        return files
    files.append(_render_feed(result, out / "feed-post.png"))
    files.append(_render_color_story(result, out / "story-01-color.png"))
    files.append(_render_evidence(result, out / "story-02-evidence.png", source_map))
    files.append(_render_why(result, out / "story-03-why-it-won.png"))
    files.append(_render_runners(result, out / "story-04-runners-up.png"))
    files.append(_render_signal_map(result, out / "story-05-signal-map.png"))
    files.append(_render_context(result, out / "story-06-context.png"))
    _write_text_assets(result, out)
    return files


def _canvas(size=(1080, 1350)):
    return Image.new("RGB", size, BG)


def _font(size: int, bold: bool = False):
    options = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for option in options:
        if Path(option).exists():
            return ImageFont.truetype(option, size)
    return ImageFont.load_default()


def _text(draw, xy, text, size, *, bold=False, fill=INK, anchor=None):
    draw.text(xy, text, font=_font(size, bold), fill=fill, anchor=anchor)


def _wrap(draw, text: str, font, width: int, max_lines: int = 3) -> list[str]:
    words = text.split()
    lines = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
            if len(lines) >= max_lines - 1:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(" ".join(lines).split()) < len(words):
        lines[-1] = lines[-1].rstrip(".") + "…"
    return lines


def _header(draw, date: str, subtitle: str = "THE OPEN CULTURAL COLOR INDEX"):
    _text(draw, (70, 52), "PANTONE CHALLENGER", 30, bold=True)
    _text(draw, (70, 91), subtitle, 15)
    _text(draw, (1010, 70), date.upper(), 17, bold=True, fill=MUTED, anchor="ra")


def _status_banner(draw, state, width=940):
    if state == PublicationState.READY:
        return
    label = "INTERNAL CALIBRATION — DO NOT POST" if state == PublicationState.REVIEW_ONLY else state.value.upper().replace("_", " ")
    draw.rounded_rectangle((70, 118, 70 + width, 164), radius=12, fill="#FFF1B8")
    _text(draw, (90, 141), label, 17, bold=True, anchor="lm")


def _render_feed(result, path: Path) -> Path:
    image = _canvas()
    draw = ImageDraw.Draw(image)
    _header(draw, result.date)
    _status_banner(draw, result.state)
    title_y = 205 if result.state != PublicationState.READY else 170
    label = "YESTERDAY’S CO-CHALLENGERS" if len(result.challenger) > 1 else "YESTERDAY’S CHALLENGER"
    _text(draw, (70, title_y), label, 27, bold=True)
    x1, y1, x2, y2 = 70, title_y + 55, 1010, 890
    colors = [c.hex for c in result.challenger]
    if len(colors) == 1:
        draw.rounded_rectangle((x1, y1, x2, y2), radius=42, fill=colors[0], outline=_swatch_border(colors[0]), width=3)
    else:
        mask = Image.new("L", image.size, 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle((x1, y1, x2, y2), radius=42, fill=255)
        split = (x2 - x1) // len(colors)
        field = Image.new("RGB", image.size, BG)
        fd = ImageDraw.Draw(field)
        for i, color in enumerate(colors):
            xa = x1 + i * split
            xb = x2 if i == len(colors) - 1 else x1 + (i + 1) * split
            fd.rectangle((xa, y1, xb, y2), fill=color)
        image.paste(field, mask=mask)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((x1, y1, x2, y2), radius=42, outline=BORDER, width=3)
    if len(result.challenger) == 1:
        c = result.challenger[0]
        text_color = readable_text_color(c.hex)
        _text(draw, (115, y1 + 65), c.family_label.upper(), 21, bold=True, fill=text_color)
        name_font = _font(48, True)
        lines = _wrap(draw, c.creative_name, name_font, 790, 3)
        for i, line in enumerate(lines):
            draw.text((115, y1 + 125 + i * 60), line, font=name_font, fill=text_color)
        _text(draw, (115, y1 + 125 + len(lines) * 68), c.hex, 34, fill=text_color)
        _text(draw, (115, y2 - 125), f"{c.trend_state.value.upper()} · EMERGENCE {c.emergence_score:.1f}", 20, bold=True, fill=text_color)
        _text(draw, (115, y2 - 82), "OBSERVED SOURCE COLOR · PIXEL VERIFIED", 15, bold=True, fill=text_color)
    else:
        for i, c in enumerate(result.challenger):
            center = x1 + (i + 0.5) * (x2 - x1) / len(result.challenger)
            text_color = readable_text_color(c.hex)
            _text(draw, (center, y1 + 120), c.family_label.upper(), 25, bold=True, fill=text_color, anchor="ma")
            _text(draw, (center, y1 + 175), c.hex, 25, fill=text_color, anchor="ma")
            _text(draw, (center, y2 - 105), f"{c.trend_state.value.upper()} {c.emergence_score:.1f}", 18, bold=True, fill=text_color, anchor="ma")
    y = 945
    _text(draw, (70, y), "TODAY’S SIGNAL COVERAGE", 18, bold=True, fill=MUTED)
    draw.line((70, y + 38, 1010, y + 38), fill=BORDER, width=2)
    metrics = [
        (result.sources_with_eligible_evidence, "SOURCES WITH\nEVIDENCE"),
        (result.domains_covered, "CULTURAL\nDOMAINS"),
        (result.sectors_covered, "INDUSTRY\nSECTORS"),
        (result.stages_covered, "SIGNAL\nSTAGES"),
        (result.discovery_sources, "DISCOVERY\nSOURCES"),
    ]
    for i, (value, label) in enumerate(metrics):
        x = 70 + i * 188
        _text(draw, (x, y + 70), str(value), 44, bold=True)
        for j, line in enumerate(label.split("\n")):
            _text(draw, (x, y + 123 + j * 20), line, 15, bold=True, fill=MUTED)
        if i < len(metrics) - 1:
            draw.line((x + 160, y + 65, x + 160, y + 175), fill=BORDER, width=2)
    _text(draw, (70, 1265), f"PALETTE REGIME: {result.palette_regime.dominant_regime.upper()}", 17, bold=True, fill=MUTED)
    image.save(path)
    return path


def _render_color_story(result, path: Path) -> Path:
    image = _canvas((1080, 1920))
    draw = ImageDraw.Draw(image)
    c = result.challenger[0]
    image.paste(c.hex, (0, 0, 1080, 1920))
    text_color = readable_text_color(c.hex)
    _text(draw, (70, 75), "PANTONE CHALLENGER", 30, bold=True, fill=text_color)
    _text(draw, (70, 120), "THE OPEN CULTURAL COLOR INDEX", 16, fill=text_color)
    if result.state != PublicationState.READY:
        _text(draw, (70, 200), "INTERNAL CALIBRATION — DO NOT POST", 19, bold=True, fill=text_color)
    _text(draw, (70, 500), "YESTERDAY’S CHALLENGER", 27, bold=True, fill=text_color)
    font = _font(60, True)
    lines = _wrap(draw, c.creative_name, font, 880, 3)
    for i, line in enumerate(lines):
        draw.text((70, 575 + i * 75), line, font=font, fill=text_color)
    _text(draw, (70, 830), c.hex, 42, fill=text_color)
    _text(draw, (70, 930), f"{c.source_count} SOURCES · {c.domain_count} DOMAINS · {c.sector_count} SECTORS · {c.stage_count} STAGES", 22, bold=True, fill=text_color)
    _text(draw, (70, 1010), f"TREND STATE: {c.trend_state.value.upper()}", 22, bold=True, fill=text_color)
    _text(draw, (70, 1780), result.date.upper(), 22, bold=True, fill=text_color)
    image.save(path)
    return path


def _render_evidence(result, path: Path, source_map: dict) -> Path:
    image = _canvas((1080, 1920))
    draw = ImageDraw.Draw(image)
    _header(draw, result.date)
    _text(draw, (70, 160), "WHERE THE SIGNAL APPEARED", 48, bold=True)
    _text(draw, (70, 225), "Each card shows a local color sampled from traceable creative—not a logo color.", 18, fill=MUTED)
    evidence = result.challenger[0].evidence[:8]
    card_w, card_h = 445, 315
    for i, item in enumerate(evidence):
        row, col = divmod(i, 2)
        x, y = 70 + col * 485, 300 + row * 355
        draw.rounded_rectangle((x, y, x + card_w, y + card_h), radius=28, fill=CARD, outline=BORDER, width=2)
        draw.rounded_rectangle((x + 25, y + 25, x + 125, y + 125), radius=20, fill=item.local_hex, outline=_swatch_border(item.local_hex), width=3)
        spec = source_map.get(item.source_id.split(":", 1)[0])
        logo_shown = False
        if spec and spec.brand_mark_status == "approved" and spec.brand_mark_path:
            logo_path = Path(spec.brand_mark_path)
            if not logo_path.is_absolute():
                logo_path = Path.cwd() / logo_path
            if logo_path.exists():
                fitted = trim_and_fit_logo(logo_path, (220, 72))
                if fitted is not None:
                    image.alpha_composite(fitted, (x + 190, y + 28)) if image.mode == "RGBA" else image.paste(fitted, (x + 190, y + 28), fitted)
                    logo_shown = True
        if not logo_shown:
            name_font = _font(25, True)
            for j, line in enumerate(_wrap(draw, item.source_name, name_font, 265, 2)):
                draw.text((x + 150, y + 32 + j * 30), line, font=name_font, fill=INK)
        _text(draw, (x + 25, y + 148), f"{item.domain.replace('_', ' ').upper()} · {item.sector.upper()} · {item.signal_stage.upper()}", 15, bold=True, fill=MUTED)
        _text(draw, (x + 25, y + 188), f"LOCAL MATCH {item.local_hex}", 17, bold=True)
        _text(draw, (x + 25, y + 220), f"AREA {item.local_share:.0%} · CONTIGUOUS {item.largest_component_share:.0%}", 14, bold=True, fill=MUTED)
        verified = "SOURCE PIXEL VERIFIED" if item.observed_pixel else "COLOR VERIFICATION FAILED"
        _text(draw, (x + 25, y + 250), verified, 14, bold=True, fill="#3E6B45" if item.observed_pixel else "#A2342B")
        _text(draw, (x + 25, y + 280), "LOGO/NAME = ATTRIBUTION ONLY", 12, bold=True, fill="#8A6550")
    _text(draw, (70, 1760), f"{result.sources_with_eligible_evidence} OF {result.panel_declared} ACTIVE SOURCES PRODUCED ELIGIBLE CREATIVE", 16, bold=True, fill=MUTED)
    _text(draw, (70, 1810), "Full source regions remain private unless their rights mode permits republication.", 15, fill=MUTED)
    image.save(path)
    return path


def _render_why(result, path: Path) -> Path:
    image = _canvas((1080, 1920))
    draw = ImageDraw.Draw(image)
    _header(draw, result.date)
    _text(draw, (70, 175), "WHY IT ROSE", 54, bold=True)
    c = result.challenger[0]
    rows = [
        ("EMERGENCE SCORE", f"{c.emergence_score:.1f}"),
        ("INDEPENDENT SOURCES", str(c.source_count)),
        ("CULTURAL DOMAINS", str(c.domain_count)),
        ("SIGNAL STAGES", str(c.stage_count)),
        ("NEWNESS", f"{c.novelty:.0%}"),
        ("ADOPTION VELOCITY", f"{c.adoption_velocity:.0%}"),
        ("SMALL + LARGE DIVERSITY", f"{c.small_large_diversity:.0%}"),
        ("TOP DOMAIN CONCENTRATION", f"{c.top_domain_weight:.0%}"),
        ("DISPLAY HEX OBSERVED", "YES" if c.color_integrity.get("display_hex_is_observed") else "NO"),
        ("COLOR CLUSTER DIAMETER", f"{float(c.color_integrity.get('cluster_diameter', 0.0)):.3f}"),
    ]
    y = 285
    for label, value in rows:
        draw.rounded_rectangle((70, y, 1010, y + 112), radius=22, fill=CARD, outline=BORDER, width=2)
        _text(draw, (105, y + 56), label, 17, bold=True, fill=MUTED, anchor="lm")
        _text(draw, (955, y + 56), value, 34, bold=True, anchor="rm")
        y += 128
    _text(draw, (70, 1605), "THE SYSTEM SEPARATES:", 18, bold=True, fill=MUTED)
    _text(draw, (70, 1650), f"UNDERCURRENT  {result.undercurrent.family_label if result.undercurrent else '—'}", 22, bold=True)
    _text(draw, (70, 1695), f"MAINSTREAM  {result.mainstream_leader.family_label if result.mainstream_leader else '—'}", 22, bold=True)
    _text(draw, (70, 1740), f"PALETTE REGIME  {result.palette_regime.dominant_regime.upper()}", 22, bold=True)
    _text(draw, (70, 1825), f"BASELINE: {result.baseline_days} PRIOR VALID DAYS", 16, bold=True, fill=MUTED)
    image.save(path)
    return path


def _render_runners(result, path: Path) -> Path:
    image = _canvas((1080, 1920))
    draw = ImageDraw.Draw(image)
    _header(draw, result.date)
    _text(draw, (70, 175), "RUNNERS-UP", 54, bold=True)
    _text(draw, (70, 245), "Only distinct, independently supported color clusters are shown.", 18, fill=MUTED)
    y = 335
    for rank, c in enumerate(result.runner_ups[:3], start=2):
        draw.rounded_rectangle((70, y, 1010, y + 390), radius=28, fill=CARD, outline=BORDER, width=2)
        swatch_box = (95, y + 25, 395, y + 365)
        draw.rounded_rectangle(swatch_box, radius=24, fill=c.hex, outline=_swatch_border(c.hex), width=4)
        tc = readable_text_color(c.hex)
        _text(draw, (125, y + 65), f"#{rank}", 26, bold=True, fill=tc)
        _text(draw, (125, y + 320), c.hex, 24, bold=True, fill=tc)
        font = _font(31, True)
        for i, line in enumerate(_wrap(draw, c.creative_name, font, 520, 3)):
            draw.text((440, y + 55 + i * 40), line, font=font, fill=INK)
        _text(draw, (440, y + 195), f"{c.source_count} SOURCES · {c.domain_count} DOMAINS · {c.stage_count} STAGES", 17, bold=True, fill=MUTED)
        _text(draw, (440, y + 245), f"EMERGENCE {c.emergence_score:.1f}", 20, bold=True)
        _text(draw, (440, y + 292), f"TREND {c.trend_state.value.upper()}", 18, bold=True, fill=MUTED)
        y += 440
    if not result.runner_ups:
        _text(draw, (70, 400), "No distinct runner-up passed today’s evidence gates.", 28, bold=True)
    _text(draw, (70, 1810), f"PANEL: {result.panel_declared} ACTIVE · {result.sources_with_eligible_evidence} WITH EVIDENCE · {result.domains_covered} DOMAINS", 15, bold=True, fill=MUTED)
    image.save(path)
    return path


def _render_signal_map(result, path: Path) -> Path:
    image = _canvas((1080, 1920))
    draw = ImageDraw.Draw(image)
    _header(draw, result.date)
    _text(draw, (70, 170), "HOW THE SIGNAL MOVED", 50, bold=True)
    evidence = result.challenger[0].evidence
    groups = [
        ("CULTURAL DOMAINS", Counter(e.domain for e in evidence)),
        ("INDUSTRY SECTORS", Counter(e.sector for e in evidence)),
        ("SIGNAL STAGES", Counter(e.signal_stage for e in evidence)),
        ("SOURCE SCALE", Counter(e.scale_class for e in evidence)),
        ("PANEL TYPE", Counter(e.panel_type for e in evidence)),
    ]
    y = 290
    for title, counts in groups:
        _text(draw, (70, y), title, 21, bold=True, fill=MUTED)
        y += 55
        total = max(1, sum(counts.values()))
        for label, count in counts.most_common(6):
            _text(draw, (70, y + 20), label.replace("_", " ").upper(), 18, bold=True)
            draw.rounded_rectangle((390, y, 930, y + 44), radius=20, fill="#E7E0D6")
            draw.rounded_rectangle((390, y, 390 + int(540 * count / total), y + 44), radius=20, fill=ACCENT)
            _text(draw, (965, y + 22), str(count), 18, bold=True, anchor="mm")
            y += 65
        y += 55
    image.save(path)
    return path


def _render_context(result, path: Path) -> Path:
    image = _canvas((1080, 1920))
    draw = ImageDraw.Draw(image)
    _header(draw, result.date)
    _text(draw, (70, 170), "THE WIDER COLOR FIELD", 50, bold=True)
    items = []
    if result.undercurrent:
        items.append(("UNDERCURRENT", result.undercurrent, "Early or independent signals"))
    if result.mainstream_leader:
        items.append(("MAINSTREAM LEADER", result.mainstream_leader, "Broad current usage, not necessarily new"))
    if result.usage_leader and all(result.usage_leader.hex != c.hex for _, c, _ in items):
        items.append(("RAW USAGE LEADER", result.usage_leader, "Most broadly visible in the sample"))
    y = 300
    for label, c, description in items[:3]:
        draw.rounded_rectangle((70, y, 1010, y + 400), radius=30, fill=CARD, outline=BORDER, width=2)
        draw.rounded_rectangle((95, y + 35, 350, y + 365), radius=24, fill=c.hex, outline=_swatch_border(c.hex), width=4)
        tc = readable_text_color(c.hex)
        _text(draw, (125, y + 75), c.family_label.upper(), 22, bold=True, fill=tc)
        _text(draw, (125, y + 320), c.hex, 22, bold=True, fill=tc)
        _text(draw, (395, y + 55), label, 18, bold=True, fill=MUTED)
        font = _font(31, True)
        for i, line in enumerate(_wrap(draw, c.creative_name, font, 540, 3)):
            draw.text((395, y + 100 + i * 42), line, font=font, fill=INK)
        _text(draw, (395, y + 245), description, 17, fill=MUTED)
        _text(draw, (395, y + 300), f"{c.source_count} SOURCES · {c.domain_count} DOMAINS", 18, bold=True)
        y += 450
    if result.palette_pair:
        colors = result.palette_pair["colors"]
        _text(draw, (70, 1680), "EMERGING PALETTE PAIR", 18, bold=True, fill=MUTED)
        for i, color in enumerate(colors[:2]):
            draw.rounded_rectangle((70 + i * 330, 1730, 350 + i * 330, 1840), radius=20, fill=color, outline=_swatch_border(color), width=3)
            _text(draw, (210 + i * 330, 1785), color, 20, bold=True, fill=readable_text_color(color), anchor="mm")
    image.save(path)
    return path


def _render_baseline(result, path: Path) -> Path:
    image = _canvas()
    draw = ImageDraw.Draw(image)
    _header(draw, result.date)
    _text(draw, (70, 220), "BASELINE DAY", 64, bold=True)
    _text(draw, (70, 310), "NO CONVERGED CHALLENGER", 34, bold=True)
    _text(draw, (70, 375), "The sample was useful, but no color passed the emergence gates.", 22, fill=MUTED)
    draw.rounded_rectangle((70, 500, 1010, 1000), radius=36, fill=CARD, outline=BORDER, width=2)
    _text(draw, (110, 585), f"{result.sources_with_eligible_evidence} / {result.panel_declared}", 76, bold=True)
    _text(draw, (110, 685), "ACTIVE SOURCES WITH ELIGIBLE CREATIVE", 22, bold=True, fill=MUTED)
    _text(draw, (110, 795), f"{result.domains_covered} DOMAINS · {result.stages_covered} SIGNAL STAGES", 30, bold=True)
    _text(draw, (110, 875), f"PALETTE REGIME: {result.palette_regime.dominant_regime.upper()}", 24, bold=True)
    _text(draw, (70, 1200), "This day can be merged to improve the historical baseline, but it produces no social post.", 18, fill=MUTED)
    image.save(path)
    return path


def _render_review(result, path: Path) -> Path:
    image = _canvas()
    draw = ImageDraw.Draw(image)
    _header(draw, result.date)
    _text(draw, (70, 220), "INTERNAL REVIEW", 64, bold=True)
    _text(draw, (70, 310), "NO PUBLIC COLOR PACKAGE", 34, bold=True)
    y = 430
    for reason in (result.blocking_reasons or result.review_reasons)[:6]:
        draw.rounded_rectangle((70, y, 1010, y + 110), radius=22, fill=CARD, outline=BORDER, width=2)
        font = _font(19)
        for i, line in enumerate(_wrap(draw, reason, font, 850, 2)):
            draw.text((100, y + 27 + i * 28), line, font=font, fill=INK)
        y += 135
    image.save(path)
    return path


def _write_text_assets(result, out: Path) -> None:
    if result.challenger:
        names = " + ".join(c.creative_name.title() for c in result.challenger)
        colors = " + ".join(c.hex for c in result.challenger)
        caption = (
            f"Yesterday’s Challenger: {names} ({colors}). "
            f"The signal appeared across {result.sources_with_eligible_evidence} eligible sources, "
            f"{result.domains_covered} cultural domains, and {result.stages_covered} signal stages. "
            f"Palette regime: {result.palette_regime.dominant_regime}. "
            "Measured within Pantone Challenger’s declared Open Cultural Color Index—not the entire internet. "
            "Independent project; not affiliated with Pantone."
        )
        alt = (
            f"A Pantone Challenger graphic showing {names}, {colors}, as the strongest emerging cultural color "
            f"signal for {result.date}. {result.sources_with_eligible_evidence} sources across "
            f"{result.domains_covered} domains produced eligible evidence."
        )
    else:
        caption = "No public Challenger was selected today. The observations were retained for calibration or diagnostic review."
        alt = caption
    (out / "caption.txt").write_text(caption + "\n", encoding="utf-8")
    (out / "feed-alt-text.txt").write_text(alt + "\n", encoding="utf-8")
    (out / "story-alt-text.txt").write_text(alt + "\n", encoding="utf-8")


def _swatch_border(hex_value: str) -> str:
    return "#B5ADA1" if contrast_ratio(hex_value, BG) < 1.45 else hex_value
