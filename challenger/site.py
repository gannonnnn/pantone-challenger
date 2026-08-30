from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from typing import Any

from .models import Source


STYLE = """
:root{--ink:#171717;--paper:#f4f0e7;--line:#d8d1c4;--card:#fbf9f4;--muted:#6d6961}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:Arial,Helvetica,sans-serif}
a{color:inherit}
header,main,footer{max-width:1180px;margin:auto;padding:28px}
header{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid var(--line)}
.brand{font-weight:800;letter-spacing:.04em}.sub{font-size:.78rem;letter-spacing:.12em}
.hero{padding:70px 28px 55px}.hero h1{font-size:clamp(3rem,9vw,7rem);line-height:.88;margin:.15em 0}
.kicker{text-transform:uppercase;font-weight:700;letter-spacing:.11em}
.swatch{border-radius:28px;min-height:420px;padding:42px;display:flex;flex-direction:column;justify-content:space-between}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:18px;margin-top:24px}
.stat{border-top:1px solid currentColor;padding-top:14px}.stat strong{font-size:2rem;display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:16px}
.tile{aspect-ratio:1;border-radius:18px;padding:18px;text-decoration:none;display:flex;flex-direction:column;justify-content:space-between}
.logo-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:16px}
.logo-card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px;min-height:155px;display:flex;flex-direction:column;justify-content:space-between}
.logo-card img{display:block;width:100%;height:76px;object-fit:contain;margin-bottom:12px}
.logo-card small{color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.runner-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.runner{border-radius:20px;overflow:hidden;background:var(--card);border:1px solid var(--line)}
.runner-color{min-height:180px;padding:20px;display:flex;justify-content:space-between;align-items:flex-end}
.runner-copy{padding:18px}.runner-copy h3{margin:.1em 0}.runner-copy p{color:var(--muted);line-height:1.45}
section{padding:45px 28px}h2{font-size:2.1rem}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:13px;border-bottom:1px solid var(--line)}
.note{max-width:780px;font-size:1.13rem;line-height:1.55}.muted{color:var(--muted)}
footer{border-top:1px solid var(--line);font-size:.88rem;line-height:1.5}
@media(max-width:760px){.stats{grid-template-columns:1fr 1fr}.runner-grid{grid-template-columns:1fr}.swatch{min-height:350px}.sub{display:none}}
"""


def _contrast(hex_value: str) -> str:
    value = hex_value.lstrip("#")
    red, green, blue = [int(value[index:index + 2], 16) / 255 for index in (0, 2, 4)]
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return "#111111" if luminance > 0.58 else "#f7f4ed"


def _load_results(archive_root: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not archive_root.exists():
        return results
    for path in sorted(archive_root.glob("????-??-??/result.json"), reverse=True):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if item.get("status") == "ready" and item.get("winner"):
            results.append(item)
    return results


def _load_year_summaries(archive_root: Path) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for path in sorted(archive_root.glob("yearly/*/annual-summary.json"), reverse=True):
        try:
            summaries.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return summaries


def _page(title: str, body: str, home_href: str = "./") -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><meta name="description" content="A daily computational index of color across the commercial internet.">
<style>{STYLE}</style></head><body>
<header><a class="brand" href="{home_href}">PANTONE CHALLENGER</a><span class="sub">THE COMMERCIAL COLOR INDEX</span></header>
{body}
<footer><p>Pantone Challenger is an independent computational art project. It is not affiliated with, sponsored by, or endorsed by Pantone LLC. No Pantone color codes or Pantone-branded swatches are used.</p>
<p>Company marks identify monitored official marketing pages and do not imply endorsement. The index describes a declared panel—not the entire internet. Methodology, coverage, and source failures are published with each result.</p></footer>
</body></html>"""


def _review_summary(result: dict[str, Any]) -> dict[str, int]:
    winner = result.get("winner") or {}
    gate = result.get("quality_gate") or {}
    return result.get("review_summary") or {
        "company_pages_monitored": int(result.get("panel_size", 0)),
        "company_pages_analyzed": int(result.get("captured_sources", 0)),
        "company_pages_unavailable": max(
            int(result.get("panel_size", 0)) - int(result.get("captured_sources", 0)), 0
        ),
        "brands_supporting_winner": int(winner.get("source_count", 0)),
        "sectors_in_panel": int(gate.get("configured_sectors", 0)),
        "sectors_analyzed": int(result.get("captured_sectors", 0)),
        "sectors_supporting_winner": int(winner.get("sector_count", 0)),
    }


def _recurrence(result: dict[str, Any]) -> dict[str, Any]:
    value = result.get("recurrence")
    if isinstance(value, dict):
        return value
    winner = result.get("winner") or {}
    return {
        "year": int(str(result.get("date", "0000"))[:4] or 0),
        "family_name": result.get("winner_name") or "Color family",
        "winning_days": 1,
        "unique_company_count": int(winner.get("source_count", 0)),
        "panel_company_count": int(result.get("panel_size", 0)),
        "sector_count": int(winner.get("sector_count", 0)),
    }


def _archive_tile(result: dict[str, Any]) -> str:
    winner = result["winner"]
    color = winner["hex"]
    text = _contrast(color)
    day = result["date"]
    name = html.escape(result.get("winner_name") or color)
    recurrence = _recurrence(result)
    return (
        f'<a class="tile" href="archive/{day}/" style="background:{color};color:{text}">'
        f'<strong>{html.escape(day)}</strong><span>{name}<br>{color}<br>'
        f'{recurrence["winning_days"]} {html.escape(recurrence["family_name"])} win(s)</span></a>'
    )


def _logo_cards(result: dict[str, Any]) -> str:
    winner = result["winner"]
    logos = result.get("source_logos") or {}
    sectors = winner.get("source_sectors") or []
    cards: list[str] = []
    for index, (source_id, name) in enumerate(
        zip(winner.get("source_ids", []), winner.get("source_names", []))
    ):
        sector = sectors[index] if index < len(sectors) else "commercial source"
        logo = logos.get(source_id)
        image = (
            f'<img src="../../assets/{result["date"]}/{html.escape(logo)}" '
            f'alt="{html.escape(name)} brand mark">'
            if logo
            else ""
        )
        cards.append(
            f'<article class="logo-card">{image}<strong>{html.escape(name)}</strong>'
            f'<small>{html.escape(sector.replace("_", " "))}</small></article>'
        )
    return "".join(cards)


def _runner_cards(result: dict[str, Any]) -> str:
    names = result.get("runner_up_names") or []
    cards: list[str] = []
    for index, candidate in enumerate(result.get("runners_up", [])[:3]):
        color = candidate["hex"]
        text = _contrast(color)
        name = names[index] if index < len(names) else color
        cards.append(
            f'<article class="runner"><div class="runner-color" '
            f'style="background:{color};color:{text}"><strong>#{index + 2}</strong>'
            f'<strong>{color}</strong></div><div class="runner-copy">'
            f'<h3>{html.escape(name)}</h3><p>{candidate["source_count"]} supporting '
            f'sources · {candidate["sector_count"]} sectors · score '
            f'{candidate["score"]:.1f}</p></div></article>'
        )
    return "".join(cards)


def _build_detail(result: dict[str, Any]) -> str:
    winner = result["winner"]
    color = winner["hex"]
    text = _contrast(color)
    summary = _review_summary(result)
    recurrence = _recurrence(result)
    body = f"""
<main>
<section class="swatch" style="background:{color};color:{text}">
<div><p class="kicker">Yesterday's Challenger · {html.escape(result['date'])}</p>
<h1>{html.escape(result.get('winner_name') or color)}</h1><p>{color}</p></div>
<div class="stats">
<div class="stat"><strong>{summary['brands_supporting_winner']}</strong>supporting brands today</div>
<div class="stat"><strong>{summary['company_pages_analyzed']} / {summary['company_pages_monitored']}</strong>analyzed / monitored</div>
<div class="stat"><strong>{summary['sectors_supporting_winner']} / {summary['sectors_in_panel']}</strong>winner sectors / panel</div>
<div class="stat"><strong>{recurrence['winning_days']}</strong>{html.escape(recurrence['family_name'])} wins in {recurrence['year']}</div>
<div class="stat"><strong>{winner['score']:.1f}</strong>Challenger Score</div>
</div></section>
<section><h2>Year-to-date counter</h2><p class="note">This is day <strong>{recurrence['winning_days']}</strong> in {recurrence['year']} with <strong>{html.escape(recurrence['family_name'])}</strong> as the top color family in the monitored commercial panel. Across matching days, {recurrence['unique_company_count']} unique companies in the {recurrence['panel_company_count']}-company panel contributed across {recurrence['sector_count']} sectors.</p></section>
<section><h2>Why it surfaced</h2><p class="note">These official company pages independently contributed to the winning color cluster. Company marks are used only to identify the monitored source.</p>
<div class="logo-grid">{_logo_cards(result)}</div></section>
<section><h2>Runners-up</h2><div class="runner-grid">{_runner_cards(result)}</div></section>
<section><h2>Run coverage</h2><p class="note">The panel monitored {summary['company_pages_monitored']} company pages. {summary['company_pages_analyzed']} were successfully captured and analyzed; {summary['company_pages_unavailable']} were blocked, failed, or unusable. The winner was supported by {summary['brands_supporting_winner']} brands across {summary['sectors_supporting_winner']} sectors.</p></section>
<section><h2>Evidence files</h2><p><a href="../../assets/{result['date']}/result.json">Result JSON</a> ·
<a href="../../assets/{result['date']}/observations.json">Observations JSON</a> ·
<a href="../../assets/{result['date']}/capture-report.json">Capture report</a> ·
<a href="../../assets/{result['date']}/review-summary.md">Review summary</a></p></section>
</main>"""
    return _page(f"{result.get('winner_name')} — Pantone Challenger", body, "../../")


def _year_links(summaries: list[dict[str, Any]]) -> str:
    if not summaries:
        return ""
    links = "".join(
        (
            f'<a class="tile" href="year/{item["year"]}/" '
            'style="background:#171717;color:#f7f4ed">'
            f'<strong>{item["year"]} YEAR IN COLOR</strong>'
            f'<span>{item["approved_days"]} approved days<br>'
            f'{html.escape(item["most_frequent_family"]["family_name"])} led</span></a>'
        )
        for item in summaries
    )
    return f'<section><h2>Year-end summaries</h2><div class="grid">{links}</div></section>'


def _build_year_detail(summary: dict[str, Any]) -> str:
    top = summary["most_frequent_family"]
    text = _contrast(top["representative_hex"])
    rows = "".join(
        (
            f'<tr><td>{index}</td><td>{html.escape(item["family_name"])}</td>'
            f'<td><span style="display:inline-block;width:24px;height:24px;border-radius:6px;'
            f'background:{item["representative_hex"]};vertical-align:middle"></span> '
            f'{item["representative_hex"]}</td>'
            f'<td>{item["winning_days"]}</td><td>{item["longest_streak"]}</td>'
            f'<td>{item["unique_company_count"]} / {item["panel_company_count"]}</td>'
            f'<td>{item["sector_count"]}</td></tr>'
        )
        for index, item in enumerate(summary["families"][:12], start=1)
    )
    body = f"""
<main>
<section class="swatch" style="background:{top['representative_hex']};color:{text}">
<div><p class="kicker">{summary['year']} YEAR IN COLOR</p>
<h1>{html.escape(top['family_name'])}</h1><p>{top['representative_hex']}</p></div>
<div class="stats">
<div class="stat"><strong>{summary['approved_days']}</strong>approved days</div>
<div class="stat"><strong>{top['winning_days']}</strong>days led by {html.escape(top['family_name'])}</div>
<div class="stat"><strong>{top['unique_company_count']} / {top['panel_company_count']}</strong>company reach</div>
<div class="stat"><strong>{summary['average_panel_coverage_percent']}%</strong>average panel coverage</div>
</div></section>
<section><h2>Most frequent daily winners</h2><table><thead><tr><th>Rank</th><th>Family</th><th>Representative</th><th>Winning days</th><th>Longest streak</th><th>Companies</th><th>Sectors</th></tr></thead><tbody>{rows}</tbody></table></section>
<section><h2>Downloadable year-end assets</h2><p><a href="../../assets/yearly/{summary['year']}/year-in-color.png">Year-in-color card</a> · <a href="../../assets/yearly/{summary['year']}/year-color-grid.png">Daily color grid</a> · <a href="../../assets/yearly/{summary['year']}/annual-summary.json">Summary JSON</a> · <a href="../../assets/yearly/{summary['year']}/annual-summary.md">Summary report</a></p></section>
</main>"""
    return _page(f"{summary['year']} Year in Color — Pantone Challenger", body, "../../")


def build_site(archive_root: Path, site_root: Path, sources: list[Source]) -> None:
    results = _load_results(archive_root)
    year_summaries = _load_year_summaries(archive_root)
    if site_root.exists():
        shutil.rmtree(site_root)
    (site_root / "archive").mkdir(parents=True, exist_ok=True)
    (site_root / "year").mkdir(parents=True, exist_ok=True)
    (site_root / "assets").mkdir(parents=True, exist_ok=True)

    if results:
        latest = results[0]
        winner = latest["winner"]
        summary = _review_summary(latest)
        recurrence = _recurrence(latest)
        color = winner["hex"]
        text = _contrast(color)
        hero = f"""
<section class="hero"><p class="kicker">What color did the commercial internet use yesterday?</p>
<div class="swatch" style="background:{color};color:{text}">
<div><p class="kicker">{html.escape(latest['date'])} · YESTERDAY'S CHALLENGER</p>
<h1>{html.escape(latest.get('winner_name') or color)}</h1><p>{color}</p></div>
<div class="stats">
<div class="stat"><strong>{summary['brands_supporting_winner']}</strong>supporting brands today</div>
<div class="stat"><strong>{summary['company_pages_analyzed']} / {summary['company_pages_monitored']}</strong>analyzed / monitored</div>
<div class="stat"><strong>{summary['sectors_supporting_winner']} / {summary['sectors_in_panel']}</strong>winner sectors / panel</div>
<div class="stat"><strong>{recurrence['winning_days']}</strong>{html.escape(recurrence['family_name'])} wins in {recurrence['year']}</div>
<div class="stat"><strong>{winner['score']:.1f}</strong>score</div>
</div></div></section>"""
    else:
        hero = """
<section class="hero"><p class="kicker">What color did the commercial internet use yesterday?</p>
<h1>THE FIRST LIVE RESULT IS PENDING.</h1>
<p class="note">The archive begins only after the real source panel passes its data-quality gate. No synthetic result is presented as a launch result.</p></section>"""

    tiles = "".join(_archive_tile(result) for result in results[:90])
    source_rows = "".join(
        f"<tr><td>{html.escape(source.name)}</td>"
        f"<td>{html.escape(source.sector.replace('_', ' '))}</td>"
        f'<td><a href="{html.escape(source.url)}" rel="nofollow">official page</a></td></tr>'
        for source in sources
    )
    body = f"""{hero}
<main>
<section><h2>The archive</h2><div class="grid">{tiles or '<p>No approved live days yet.</p>'}</div></section>
{_year_links(year_summaries)}
<section><h2>The declared panel</h2><p class="note">Every enabled source is an official commercial or brand-owned page. Each brand receives one normalized vote per day regardless of how many visual elements appear on its page.</p>
<table><thead><tr><th>Source</th><th>Sector</th><th>Page</th></tr></thead><tbody>{source_rows}</tbody></table></section>
<section><h2>How it works</h2><p class="note">Each day the project browser-renders a balanced panel of marketing pages, extracts perceptually prominent colors, clusters similar shades in OKLab, suppresses colors that are ordinary for a particular brand, and rewards independent cross-sector spread. A separate perceptual match tracks how often the same color family wins during the year. A quality gate blocks weak days. The algorithmic winner cannot be swapped out because it is unattractive.</p></section>
</main>"""
    (site_root / "index.html").write_text(
        _page("Pantone Challenger — The Commercial Color Index", body),
        encoding="utf-8",
    )

    for result in results:
        day = result["date"]
        source_dir = archive_root / day
        detail_dir = site_root / "archive" / day
        detail_dir.mkdir(parents=True, exist_ok=True)
        (detail_dir / "index.html").write_text(_build_detail(result), encoding="utf-8")
        asset_dir = site_root / "assets" / day
        shutil.copytree(source_dir, asset_dir, dirs_exist_ok=True)

    for summary in year_summaries:
        year = str(summary["year"])
        detail_dir = site_root / "year" / year
        detail_dir.mkdir(parents=True, exist_ok=True)
        (detail_dir / "index.html").write_text(_build_year_detail(summary), encoding="utf-8")
        source_dir = archive_root / "yearly" / year
        asset_dir = site_root / "assets" / "yearly" / year
        shutil.copytree(source_dir, asset_dir, dirs_exist_ok=True)

    (site_root / ".nojekyll").write_text("", encoding="utf-8")
    (site_root / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
