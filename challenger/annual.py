from __future__ import annotations

import json
import os
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from .colors import contrast_text_color, hex_from_oklab, oklab_from_hex
from .models import Source
from .recurrence import (
    cluster_ready_results,
    color_family_name,
    human_sector_list,
    load_ready_results,
)
from .render import FEED_SIZE, INK, LINE, MUTED, OFF_WHITE, _draw_wrapped, _fit_font, _font


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _winner_lab(result: dict[str, Any]) -> tuple[float, float, float]:
    winner = result.get("winner") or {}
    raw = winner.get("oklab")
    if isinstance(raw, list) and len(raw) == 3:
        return tuple(float(value) for value in raw)
    return oklab_from_hex(str(winner["hex"]))


def _longest_streak(values: list[str]) -> int:
    days = sorted(date.fromisoformat(value) for value in values)
    if not days:
        return 0
    current = longest = 1
    for previous, following in zip(days, days[1:]):
        if following == previous + timedelta(days=1):
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def _family_summary(
    cluster: list[dict[str, Any]],
    panel_size: int,
    family_id: str,
) -> dict[str, Any]:
    results = cluster
    labs = np.asarray([_winner_lab(result) for result in results], dtype=float)
    representative = tuple(float(value) for value in np.mean(labs, axis=0))
    source_names: dict[str, str] = {}
    sector_counter: Counter[str] = Counter()
    scores: list[float] = []
    analyzed: list[int] = []
    supporting_company_days = 0
    peak_result: dict[str, Any] | None = None

    for result in results:
        winner = result["winner"]
        ids = list(winner.get("source_ids") or [])
        names = list(winner.get("source_names") or [])
        for index, source_id in enumerate(ids):
            source_names[str(source_id)] = str(names[index] if index < len(names) else source_id)
        for sector in winner.get("sectors") or []:
            sector_counter[str(sector)] += 1
        supporting_company_days += int(winner.get("source_count", len(ids)) or 0)
        score = float(winner.get("score", 0.0) or 0.0)
        scores.append(score)
        analyzed.append(int(result.get("captured_sources", 0) or 0))
        if peak_result is None or score > float(peak_result["winner"].get("score", 0.0)):
            peak_result = result

    dates = [str(result["date"]) for result in results]
    sectors = [
        key for key, _ in sorted(
            sector_counter.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    return {
        "family_id": family_id,
        "family_name": color_family_name(representative),
        "representative_hex": hex_from_oklab(representative),
        "representative_oklab": list(representative),
        "winning_days": len(results),
        "dates": dates,
        "first_win_date": min(dates),
        "latest_win_date": max(dates),
        "longest_streak": _longest_streak(dates),
        "unique_company_count": len(source_names),
        "unique_company_ids": sorted(source_names),
        "unique_company_names": [source_names[key] for key in sorted(source_names)],
        "panel_company_count": panel_size,
        "supporting_company_days": supporting_company_days,
        "sectors": sectors,
        "sector_count": len(sectors),
        "sector_day_counts": dict(sector_counter),
        "average_score": round(sum(scores) / max(len(scores), 1), 2),
        "peak_score": round(max(scores, default=0.0), 2),
        "peak_date": str(peak_result["date"]) if peak_result else None,
        "average_analyzed_company_pages": round(sum(analyzed) / max(len(analyzed), 1), 1),
    }


def build_annual_summary(
    *,
    archive_root: Path,
    year: int,
    sources: list[Source],
    distance_threshold: float,
) -> dict[str, Any]:
    results = load_ready_results(archive_root, year=year)
    if not results:
        raise ValueError(f"No approved daily results exist for {year}")

    panel_size = len(sources)
    families = [
        _family_summary(cluster, panel_size, f"family-{index:03d}")
        for index, cluster in enumerate(
            cluster_ready_results(results, distance_threshold),
            start=1,
        )
    ]
    families.sort(
        key=lambda item: (
            item["winning_days"],
            item["unique_company_count"],
            item["sector_count"],
            item["average_score"],
        ),
        reverse=True,
    )

    date_to_family: dict[str, dict[str, Any]] = {}
    family_by_id = {family["family_id"]: family for family in families}
    for family in families:
        for value in family["dates"]:
            date_to_family[value] = family
    monthly: list[dict[str, Any]] = []
    for month in range(1, 13):
        month_results = [
            result for result in results if date.fromisoformat(result["date"]).month == month
        ]
        if not month_results:
            continue
        counts: Counter[str] = Counter(
            date_to_family[result["date"]]["family_id"] for result in month_results
        )
        winning_family_id, winning_days = counts.most_common(1)[0]
        family = family_by_id[winning_family_id]
        monthly.append(
            {
                "month": month,
                "family_name": family["family_name"],
                "representative_hex": family["representative_hex"],
                "winning_days": winning_days,
                "approved_days": len(month_results),
            }
        )

    analyzed = [int(result.get("captured_sources", 0) or 0) for result in results]
    all_company_ids = {
        str(source_id)
        for result in results
        for source_id in (result.get("winner") or {}).get("source_ids", [])
    }
    top = families[0]
    longest = max(families, key=lambda item: (item["longest_streak"], item["winning_days"]))
    widest_companies = max(
        families,
        key=lambda item: (item["unique_company_count"], item["winning_days"]),
    )
    widest_sectors = max(
        families,
        key=lambda item: (item["sector_count"], item["winning_days"]),
    )
    return {
        "year": year,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": {
            "description": (
                "Daily winners are grouped into perceptually similar color families using "
                "complete-link OKLab matching: every shade in a family must remain "
                "within the fixed distance threshold of every other shade."
            ),
            "distance_threshold": distance_threshold,
        },
        "approved_days": len(results),
        "first_approved_date": min(result["date"] for result in results),
        "latest_approved_date": max(result["date"] for result in results),
        "distinct_color_families": len(families),
        "panel_company_count": panel_size,
        "average_analyzed_company_pages": round(sum(analyzed) / max(len(analyzed), 1), 1),
        "average_panel_coverage_percent": round(
            100 * sum(analyzed) / max(len(analyzed) * panel_size, 1),
            1,
        ),
        "unique_companies_supporting_any_winner": len(all_company_ids),
        "most_frequent_family": top,
        "longest_streak_family": longest,
        "widest_company_reach_family": widest_companies,
        "widest_sector_reach_family": widest_sectors,
        "monthly_leaders": monthly,
        "families": families,
        "daily_colors": [
            {
                "date": result["date"],
                "name": result.get("winner_name") or result["winner"]["hex"],
                "hex": result["winner"]["hex"],
                "family_name": date_to_family[result["date"]]["family_name"],
            }
            for result in results
        ],
    }


def _annual_markdown(summary: dict[str, Any]) -> str:
    top = summary["most_frequent_family"]
    longest = summary["longest_streak_family"]
    widest = summary["widest_company_reach_family"]
    lines = [
        f"# {summary['year']} Year in Color",
        "",
        f"Pantone Challenger published **{summary['approved_days']} approved daily results** "
        f"between {summary['first_approved_date']} and {summary['latest_approved_date']}.",
        "",
        "## Headline findings",
        "",
        f"- **Most frequent daily winner:** {top['family_name']} `{top['representative_hex']}` — "
        f"{top['winning_days']} days",
        f"- **Longest consecutive run:** {longest['family_name']} — "
        f"{longest['longest_streak']} days",
        f"- **Widest company reach:** {widest['family_name']} — "
        f"{widest['unique_company_count']} of {summary['panel_company_count']} companies",
        f"- **Average daily panel coverage:** {summary['average_analyzed_company_pages']} of "
        f"{summary['panel_company_count']} company pages "
        f"({summary['average_panel_coverage_percent']}%)",
        "",
        "## Most frequent color families",
        "",
        "| Rank | Color family | Representative | Winning days | Longest streak | Unique companies | Sectors |",
        "|---:|---|---|---:|---:|---:|---:|",
    ]
    for index, family in enumerate(summary["families"][:12], start=1):
        lines.append(
            f"| {index} | {family['family_name']} | `{family['representative_hex']}` | "
            f"{family['winning_days']} | {family['longest_streak']} | "
            f"{family['unique_company_count']} / {family['panel_company_count']} | "
            f"{family['sector_count']} |"
        )
    lines.extend(["", "## Monthly leaders", ""])
    for item in summary["monthly_leaders"]:
        month_name = date(summary["year"], item["month"], 1).strftime("%B")
        lines.append(
            f"- **{month_name}:** {item['family_name']} `{item['representative_hex']}` — "
            f"{item['winning_days']} of {item['approved_days']} approved days"
        )
    lines.extend(
        [
            "",
            "## Method note",
            "",
            summary["method"]["description"]
            + f" The threshold was {summary['method']['distance_threshold']:.3f}. "
            "Creative daily color names are not used to determine whether two days match.",
        ]
    )
    return "\n".join(lines)


def _render_year_summary(summary: dict[str, Any], output: Path) -> None:
    image = Image.new("RGB", FEED_SIZE, OFF_WHITE)
    draw = ImageDraw.Draw(image)
    draw.text((64, 58), "PANTONE CHALLENGER", font=_font(28, bold=True), fill=INK)
    draw.text((64, 102), "THE COMMERCIAL COLOR INDEX", font=_font(17), fill=INK)
    draw.text((64, 185), f"{summary['year']} YEAR IN COLOR", font=_font(61, bold=True), fill=INK)
    draw.text(
        (64, 260),
        f"{summary['approved_days']} approved days · {summary['distinct_color_families']} color families · "
        f"{summary['average_panel_coverage_percent']}% average panel coverage",
        font=_font(19, bold=True),
        fill=MUTED,
    )

    top = summary["most_frequent_family"]
    box = (64, 330, 1016, 790)
    draw.rounded_rectangle(box, radius=42, fill=top["representative_hex"])
    text = contrast_text_color(top["representative_hex"])
    draw.text((104, 375), "MOST FREQUENT DAILY WINNER", font=_font(18, bold=True), fill=text)
    name_font = _fit_font(draw, top["family_name"].upper(), 830, 78, 46, bold=True)
    draw.text((104, 465), top["family_name"].upper(), font=name_font, fill=text)
    draw.text((104, 580), top["representative_hex"], font=_font(34, bold=True), fill=text)
    top_detail = (
        f"{top['winning_days']} WINNING DAYS · {top['unique_company_count']} / "
        f"{top['panel_company_count']} COMPANIES · {top['sector_count']} SECTORS"
    )
    draw.text(
        (104, 665),
        top_detail,
        font=_fit_font(draw, top_detail, 830, 20, 16, bold=True),
        fill=text,
    )

    draw.text((64, 850), "THE NEXT FOUR", font=_font(18, bold=True), fill=MUTED)
    families = summary["families"][1:5]
    width = 226
    gap = 16
    for index, family in enumerate(families):
        left = 64 + index * (width + gap)
        draw.rounded_rectangle(
            (left, 895, left + width, 1210),
            radius=28,
            fill=family["representative_hex"],
        )
        foreground = contrast_text_color(family["representative_hex"])
        draw.text((left + 20, 925), f"#{index + 2}", font=_font(19, bold=True), fill=foreground)
        family_font = _fit_font(draw, family["family_name"].upper(), width - 40, 25, 17, bold=True)
        _draw_wrapped(
            draw,
            family["family_name"].upper(),
            (left + 20, 1000),
            max_width=width - 40,
            font=family_font,
            fill=foreground,
            spacing=3,
            max_lines=3,
        )
        draw.text(
            (left + 20, 1145),
            f"{family['winning_days']} DAYS",
            font=_font(17, bold=True),
            fill=foreground,
        )
    draw.text(
        (64, 1284),
        "MOST FREQUENT DAILY WINNERS IN THE DECLARED COMMERCIAL PANEL",
        font=_font(16, bold=True),
        fill=MUTED,
    )
    image.save(output, quality=95)


def _render_color_grid(summary: dict[str, Any], output: Path) -> None:
    image = Image.new("RGB", FEED_SIZE, OFF_WHITE)
    draw = ImageDraw.Draw(image)
    draw.text((64, 58), "PANTONE CHALLENGER", font=_font(28, bold=True), fill=INK)
    draw.text((64, 102), f"{summary['year']} · EVERY APPROVED DAILY WINNER", font=_font(17), fill=INK)
    draw.text((64, 180), "A YEAR IN COLOR", font=_font(61, bold=True), fill=INK)

    colors = summary["daily_colors"]
    columns = 20
    gap = 5
    left = 64
    top = 300
    usable_width = 952
    tile = (usable_width - gap * (columns - 1)) // columns
    rows = (len(colors) + columns - 1) // columns
    max_height = 860
    if rows:
        tile = min(tile, max(12, (max_height - gap * (rows - 1)) // rows))
    for index, item in enumerate(colors):
        row, column = divmod(index, columns)
        x = left + column * (tile + gap)
        y = top + row * (tile + gap)
        draw.rounded_rectangle((x, y, x + tile, y + tile), radius=max(2, tile // 6), fill=item["hex"])

    footer_y = min(top + rows * (tile + gap) + 70, 1180)
    draw.line((64, footer_y, 1016, footer_y), fill=LINE, width=2)
    draw.text(
        (64, footer_y + 35),
        f"{summary['approved_days']} APPROVED DAYS",
        font=_font(25, bold=True),
        fill=INK,
    )
    coverage_detail = (
        f"{summary['distinct_color_families']} PERCEPTUAL COLOR FAMILIES · "
        f"{summary['average_analyzed_company_pages']} OF {summary['panel_company_count']} "
        "COMPANY PAGES ANALYZED ON AN AVERAGE DAY"
    )
    draw.text(
        (64, footer_y + 86),
        coverage_detail,
        font=_fit_font(draw, coverage_detail, 950, 18, 13, bold=True),
        fill=MUTED,
    )
    image.save(output, quality=95)


def write_annual_package(
    *,
    archive_root: Path,
    year: int,
    sources: list[Source],
    distance_threshold: float,
) -> Path:
    summary = build_annual_summary(
        archive_root=archive_root,
        year=year,
        sources=sources,
        distance_threshold=distance_threshold,
    )
    output = archive_root / "yearly" / str(year)
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "annual-summary.json", summary)
    (output / "annual-summary.md").write_text(_annual_markdown(summary), encoding="utf-8")
    _render_year_summary(summary, output / "year-in-color.png")
    _render_color_grid(summary, output / "year-color-grid.png")
    return output
