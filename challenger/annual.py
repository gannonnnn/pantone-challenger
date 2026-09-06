from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont



def build_annual_summary(archive_dir: str | Path, year: int, destination: str | Path | None = None) -> dict:
    archive = Path(archive_dir)
    out = Path(destination) if destination else archive / "yearly" / str(year)
    out.mkdir(parents=True, exist_ok=True)
    days = []
    for day_dir in sorted(archive.glob(f"{year}-??-??")):
        path = day_dir / "result.json"
        if not path.exists():
            continue
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if result.get("state") != "ready" or not result.get("challenger"):
            continue
        days.append(result)
    family_appearances = Counter()
    family_day_share = Counter()
    family_sources = defaultdict(set)
    family_domains = defaultdict(set)
    regimes_by_month = defaultdict(list)
    chroma_by_month = defaultdict(list)
    neutral_by_month = defaultdict(list)
    daily_colors = []
    undercurrents = Counter()
    mainstream = Counter()
    for result in days:
        winners = result.get("challenger", [])
        share = 1.0 / max(1, len(winners))
        for winner in winners:
            family = winner.get("family_label", "Unknown")
            family_appearances[family] += 1
            family_day_share[family] += share
            family_sources[family].update(e.get("source_id", "") for e in winner.get("evidence", []))
            family_domains[family].update(e.get("domain", "") for e in winner.get("evidence", []))
            daily_colors.append({"date": result["date"], "hex": winner.get("hex"), "family": family, "day_share": share})
        month = result["date"][:7]
        regime = result.get("palette_regime", {})
        regimes_by_month[month].append(regime.get("dominant_regime", "unknown"))
        chroma_by_month[month].append(float(regime.get("median_chroma", 0)))
        neutral_by_month[month].append(float(regime.get("neutral_share", 0)))
        if result.get("undercurrent"):
            undercurrents[result["undercurrent"].get("family_label", "Unknown")] += 1
        if result.get("mainstream_leader"):
            mainstream[result["mainstream_leader"].get("family_label", "Unknown")] += 1
    ranked = [
        {
            "family": family,
            "appearance_days": family_appearances[family],
            "leaderboard_day_share": round(family_day_share[family], 2),
            "unique_sources": len(family_sources[family]),
            "domains": sorted(x for x in family_domains[family] if x),
        }
        for family in sorted(family_appearances, key=lambda f: (family_day_share[f], family_appearances[f]), reverse=True)
    ]
    monthly = {}
    for month in sorted(regimes_by_month):
        monthly[month] = {
            "dominant_regime": Counter(regimes_by_month[month]).most_common(1)[0][0],
            "mean_median_chroma": round(sum(chroma_by_month[month]) / len(chroma_by_month[month]), 4),
            "mean_neutral_share": round(sum(neutral_by_month[month]) / len(neutral_by_month[month]), 4),
        }
    most_neutral = max(monthly, key=lambda m: monthly[m]["mean_neutral_share"], default=None)
    highest_chroma = max(monthly, key=lambda m: monthly[m]["mean_median_chroma"], default=None)
    summary = {
        "year": year,
        "approved_challenger_days": len(days),
        "ranked_color_families": ranked,
        "monthly_palette_regimes": monthly,
        "most_neutral_month": most_neutral,
        "highest_chroma_month": highest_chroma,
        "most_frequent_undercurrent": undercurrents.most_common(1)[0][0] if undercurrents else None,
        "most_frequent_mainstream_leader": mainstream.most_common(1)[0][0] if mainstream else None,
        "daily_colors": daily_colors,
    }
    (out / "annual-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _write_markdown(out / "annual-summary.md", summary)
    _render_year_card(out / "year-in-color.png", summary)
    _render_grid(out / "year-color-grid.png", summary)
    return summary


def _write_markdown(path: Path, summary: dict):
    lines = [
        f"# Pantone Challenger — {summary['year']} Year in Color",
        "",
        f"Approved Challenger days: **{summary['approved_challenger_days']}**",
        "",
        "## Recurring color families",
        "",
        "| Family | Appearance days | Leaderboard day-share | Unique sources | Domains |",
        "|---|---:|---:|---:|---|",
    ]
    for item in summary["ranked_color_families"]:
        lines.append(
            f"| {item['family']} | {item['appearance_days']} | {item['leaderboard_day_share']} | {item['unique_sources']} | {', '.join(item['domains'])} |"
        )
    lines.extend(
        [
            "",
            f"Most neutral month: **{summary['most_neutral_month'] or 'n/a'}**",
            f"Highest-chroma month: **{summary['highest_chroma_month'] or 'n/a'}**",
            f"Most frequent undercurrent: **{summary['most_frequent_undercurrent'] or 'n/a'}**",
            f"Most frequent mainstream leader: **{summary['most_frequent_mainstream_leader'] or 'n/a'}**",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _font(size, bold=False):
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _render_year_card(path: Path, summary: dict):
    image = Image.new("RGB", (1080, 1350), "#F6F1E9")
    draw = ImageDraw.Draw(image)
    draw.text((70, 65), "PANTONE CHALLENGER", font=_font(30, True), fill="#161616")
    draw.text((70, 112), "THE OPEN CULTURAL COLOR INDEX", font=_font(16), fill="#161616")
    draw.text((70, 230), f"{summary['year']} YEAR IN COLOR", font=_font(56, True), fill="#161616")
    top = summary["ranked_color_families"][:5]
    y = 390
    for index, item in enumerate(top, start=1):
        draw.rounded_rectangle((70, y, 1010, y + 130), radius=22, fill="#FFFDF9", outline="#D8D0C5", width=2)
        draw.text((105, y + 65), f"#{index}", font=_font(25, True), fill="#6B655E", anchor="lm")
        draw.text((185, y + 45), item["family"].upper(), font=_font(29, True), fill="#161616")
        draw.text((185, y + 86), f"{item['appearance_days']} appearance days · {item['leaderboard_day_share']} day-share", font=_font(17), fill="#6B655E")
        draw.text((960, y + 65), str(item["unique_sources"]), font=_font(36, True), fill="#161616", anchor="rm")
        y += 155
    draw.text((70, 1210), f"{summary['approved_challenger_days']} APPROVED CHALLENGER DAYS", font=_font(18, True), fill="#6B655E")
    image.save(path)


def _render_grid(path: Path, summary: dict):
    days = summary["daily_colors"]
    cell = 48
    cols = 20
    rows = max(1, (len(days) + cols - 1) // cols)
    image = Image.new("RGB", (cols * cell + 140, rows * cell + 220), "#F6F1E9")
    draw = ImageDraw.Draw(image)
    draw.text((55, 45), f"{summary['year']} DAILY CHALLENGER GRID", font=_font(34, True), fill="#161616")
    for i, day in enumerate(days):
        row, col = divmod(i, cols)
        x, y = 55 + col * cell, 130 + row * cell
        draw.rectangle((x, y, x + cell - 3, y + cell - 3), fill=day["hex"])
    image.save(path)
