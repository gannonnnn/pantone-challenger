from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from challenger.serialize import clean


def write_json(path: str | Path, payload) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(clean(payload), indent=2, sort_keys=False), encoding="utf-8")


def write_summary(path: str | Path, result) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Pantone Challenger — {result.date}",
        "",
        f"**State:** `{result.state.value}`  ",
        f"**Coverage:** {result.sources_with_eligible_evidence} / {result.panel_declared} active sources  ",
        f"**Domains:** {result.domains_covered}  ",
        f"**Industry sectors:** {result.sectors_covered}  ",
        f"**Signal stages:** {result.stages_covered}  ",
        f"**Historical baseline:** {result.baseline_days} prior valid days  ",
        f"**Color provenance:** `{result.reports.get('color_truth', 'not checked')}` — {result.reports.get('color_truth_swatches_checked', '0')} extracted swatches independently verified against decoded source pixels  ",
        "",
    ]
    if result.challenger:
        heading = "Co-Challengers" if len(result.challenger) > 1 else "Challenger"
        lines.extend([f"## {heading}", ""])
        for c in result.challenger:
            integrity = c.color_integrity or {}
            lines.append(
                f"- **{c.creative_name}** `{c.hex}` — {c.source_count} sources, {c.domain_count} domains, "
                f"{c.stage_count} stages, emergence {c.emergence_score:.1f}, state `{c.trend_state.value}`; "
                f"display HEX observed: `{bool(integrity.get('display_hex_is_observed'))}`; "
                f"cluster diameter: `{float(integrity.get('cluster_diameter', 0.0)):.3f}`"
            )
        lines.append("")
    elif result.state.value == "baseline_only":
        lines.extend(["## No converged Challenger today", "", "The observations are still useful for the historical baseline.", ""])
    if result.undercurrent:
        c = result.undercurrent
        lines.append(f"**Undercurrent:** {c.creative_name} `{c.hex}` ({c.undercurrent_score:.1f})  ")
    if result.mainstream_leader:
        c = result.mainstream_leader
        lines.append(f"**Mainstream leader:** {c.creative_name} `{c.hex}` ({c.mainstream_score:.1f})  ")
    lines.extend(["", f"**Palette regime:** {result.palette_regime.dominant_regime}  "])
    if result.palette_pair:
        lines.append(f"**Leading color pair:** {' + '.join(result.palette_pair['colors'])}  ")
    if result.blocking_reasons:
        lines.extend(["", "## Blocking reasons", ""] + [f"- {r}" for r in result.blocking_reasons])
    if result.review_reasons:
        lines.extend(["", "## Review notes", ""] + [f"- {r}" for r in result.review_reasons])
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_contact_sheet(path: str | Path, candidates, title: str) -> None:
    evidence = []
    for candidate in candidates:
        for item in candidate.evidence[:8]:
            evidence.append((candidate, item))
    cols = 2
    card_w, card_h = 720, 360
    margin = 50
    rows = max(1, (len(evidence) + cols - 1) // cols)
    canvas = Image.new("RGB", (cols * card_w + (cols + 1) * margin, 180 + rows * card_h + (rows + 1) * margin), "#F6F1E9")
    draw = ImageDraw.Draw(canvas)
    font_b = _font(36, bold=True)
    font_m = _font(23, bold=True)
    font_s = _font(18)
    draw.text((margin, 48), title, fill="#161616", font=font_b)
    for index, (candidate, item) in enumerate(evidence):
        row, col = divmod(index, cols)
        x = margin + col * (card_w + margin)
        y = 130 + margin + row * (card_h + margin)
        draw.rounded_rectangle((x, y, x + card_w, y + card_h), radius=26, fill="#FFFFFF", outline="#D9D0C3", width=2)
        image_box = (x + 20, y + 20, x + 300, y + card_h - 20)
        try:
            region = Image.open(item.region_path).convert("RGB")
            region.thumbnail((image_box[2] - image_box[0], image_box[3] - image_box[1]), Image.Resampling.LANCZOS)
            px = image_box[0] + ((image_box[2] - image_box[0]) - region.width) // 2
            py = image_box[1] + ((image_box[3] - image_box[1]) - region.height) // 2
            canvas.paste(region, (px, py))
        except Exception:  # noqa: BLE001
            draw.rectangle(image_box, fill="#EEE8DF")
        sx, sy = x + 330, y + 35
        draw.rounded_rectangle((sx, sy, sx + 90, sy + 90), radius=16, fill=item.local_hex, outline="#BDB5AA", width=2)
        draw.text((sx + 110, sy), item.source_name[:28], fill="#161616", font=font_m)
        draw.text((sx + 110, sy + 40), f"{item.domain} · {item.signal_stage}", fill="#5C5750", font=font_s)
        draw.text((sx, sy + 120), f"Local match: {item.local_hex}", fill="#161616", font=font_s)
        draw.text((sx, sy + 152), f"Cluster distance: {item.distance_to_candidate:.3f}", fill="#161616", font=font_s)
        draw.text((sx, sy + 184), f"Creative share: {item.local_share:.1%}", fill="#161616", font=font_s)
        draw.text((sx, sy + 216), f"Evidence confidence: {item.evidence_confidence:.0%}", fill="#161616", font=font_s)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, quality=92)


def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def write_color_proof_sheet(path: str | Path, candidates, title: str, *, threshold: float = 0.035) -> None:
    """Write a private reviewer sheet that proves where each matched color occurs.

    Original creative appears beside a proof view where non-matching pixels are
    muted. This is never a public social asset; it exists so a reviewer can see
    whether a claimed color came from campaign creative, a button, text, or UI.
    """

    from challenger.palette import color_match_overlay

    evidence = []
    for candidate in candidates[:4]:
        for item in candidate.evidence[:8]:
            evidence.append((candidate, item))
    cols = 1
    card_w, card_h = 1480, 380
    margin = 42
    rows = max(1, len(evidence))
    canvas = Image.new(
        "RGB",
        (cols * card_w + (cols + 1) * margin, 150 + rows * card_h + (rows + 1) * margin),
        "#F6F1E9",
    )
    draw = ImageDraw.Draw(canvas)
    font_b = _font(34, bold=True)
    font_m = _font(22, bold=True)
    font_s = _font(17)
    draw.text((margin, 42), title, fill="#161616", font=font_b)
    draw.text(
        (margin, 92),
        "Left: source crop. Right: only pixels matching the claimed local swatch remain in color.",
        fill="#5C5750",
        font=font_s,
    )
    for index, (candidate, item) in enumerate(evidence):
        x = margin
        y = 130 + margin + index * (card_h + margin)
        draw.rounded_rectangle(
            (x, y, x + card_w, y + card_h),
            radius=24,
            fill="#FFFFFF",
            outline="#D9D0C3",
            width=2,
        )
        original_box = (x + 20, y + 20, x + 470, y + card_h - 20)
        proof_box = (x + 500, y + 20, x + 950, y + card_h - 20)
        try:
            original = Image.open(item.region_path).convert("RGB")
            proof = color_match_overlay(
                item.region_path,
                item.local_oklab,
                threshold=threshold,
                max_side=520,
            )
            _paste_contained(canvas, original, original_box)
            _paste_contained(canvas, proof, proof_box)
        except Exception:  # noqa: BLE001
            draw.rectangle(original_box, fill="#EEE8DF")
            draw.rectangle(proof_box, fill="#EEE8DF")
        sx, sy = x + 985, y + 28
        draw.rounded_rectangle(
            (sx, sy, sx + 92, sy + 92),
            radius=14,
            fill=item.local_hex,
            outline="#BDB5AA",
            width=2,
        )
        draw.text((sx + 112, sy), item.source_name[:30], fill="#161616", font=font_m)
        draw.text(
            (sx + 112, sy + 38),
            f"{item.domain} · {item.signal_stage}",
            fill="#5C5750",
            font=font_s,
        )
        draw.text((sx, sy + 122), f"Observed local HEX: {item.local_hex}", fill="#161616", font=font_s)
        draw.text(
            (sx, sy + 155),
            f"Distance to displayed color: {item.distance_to_candidate:.3f}",
            fill="#161616",
            font=font_s,
        )
        draw.text(
            (sx, sy + 188),
            f"Area share: {item.local_share:.1%} · largest component: {item.largest_component_share:.1%}",
            fill="#161616",
            font=font_s,
        )
        draw.text(
            (sx, sy + 221),
            f"Spatial coverage: {item.spatial_coverage:.0%} · observed pixel: {'yes' if item.observed_pixel else 'NO'}",
            fill="#161616",
            font=font_s,
        )
        draw.text(
            (sx, sy + 254),
            f"Candidate display HEX source: {candidate.display_hex_source_id or 'unknown'}",
            fill="#5C5750",
            font=font_s,
        )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, quality=92)


def _paste_contained(canvas: Image.Image, source: Image.Image, box: tuple[int, int, int, int]) -> None:
    image = source.copy().convert("RGB")
    width, height = box[2] - box[0], box[3] - box[1]
    image.thumbnail((width, height), Image.Resampling.LANCZOS)
    background = Image.new("RGB", (width, height), "#EAE5DD")
    background.paste(image, ((width - image.width) // 2, (height - image.height) // 2))
    canvas.paste(background, (box[0], box[1]))
