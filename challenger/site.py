from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from typing import Any

from .models import Source


STYLE = """
:root{--ink:#171717;--paper:#f4f0e7;--line:#d8d1c4}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:Arial,Helvetica,sans-serif}
a{color:inherit}
header,main,footer{max-width:1180px;margin:auto;padding:28px}
header{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid var(--line)}
.brand{font-weight:800;letter-spacing:.04em}.sub{font-size:.78rem;letter-spacing:.12em}
.hero{padding:70px 28px 55px}.hero h1{font-size:clamp(3rem,9vw,7rem);line-height:.88;margin:.15em 0}
.kicker{text-transform:uppercase;font-weight:700;letter-spacing:.11em}
.swatch{border-radius:28px;min-height:420px;padding:42px;display:flex;flex-direction:column;justify-content:space-between}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:24px}
.stat{border-top:1px solid currentColor;padding-top:14px}.stat strong{font-size:2rem;display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:16px}
.tile{aspect-ratio:1;border-radius:18px;padding:18px;text-decoration:none;display:flex;flex-direction:column;justify-content:space-between}
section{padding:45px 28px}h2{font-size:2.1rem}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:13px;border-bottom:1px solid var(--line)}
.note{max-width:780px;font-size:1.13rem;line-height:1.55}
footer{border-top:1px solid var(--line);font-size:.88rem;line-height:1.5}
@media(max-width:650px){.stats{grid-template-columns:1fr}.swatch{min-height:350px}.sub{display:none}}
"""


def _contrast(hex_value: str) -> str:
    value = hex_value.lstrip("#")
    r, g, b = [int(value[i:i+2], 16) / 255 for i in (0, 2, 4)]
    lum = 0.2126*r + 0.7152*g + 0.0722*b
    return "#111111" if lum > 0.58 else "#f7f4ed"


def _load_results(archive_root: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not archive_root.exists():
        return results
    for path in sorted(archive_root.glob("*/result.json"), reverse=True):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if item.get("status") == "ready" and item.get("winner"):
            results.append(item)
    return results


def _page(title: str, body: str, home_href: str = "./") -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><meta name="description" content="A daily computational index of color across the commercial internet.">
<style>{STYLE}</style></head><body>
<header><a class="brand" href="{home_href}">PANTONE CHALLENGER</a><span class="sub">THE COMMERCIAL COLOR INDEX</span></header>
{body}
<footer><p>Pantone Challenger is an independent computational art project. It is not affiliated with, sponsored by, or endorsed by Pantone LLC. No Pantone color codes, swatches, or logos are used.</p>
<p>The index describes a declared panel of official marketing pages—not the entire internet. Methodology and source failures are published with each result.</p></footer>
</body></html>"""


def _archive_tile(result: dict[str, Any]) -> str:
    winner = result["winner"]
    color = winner["hex"]
    text = _contrast(color)
    date = result["date"]
    name = html.escape(result.get("winner_name") or color)
    return (
        f'<a class="tile" href="archive/{date}/" style="background:{color};color:{text}">'
        f'<strong>{html.escape(date)}</strong><span>{name}<br>{color}</span></a>'
    )


def _build_detail(result: dict[str, Any]) -> str:
    winner = result["winner"]
    color = winner["hex"]
    text = _contrast(color)
    reasons = result["quality_gate"].get("reasons", [])
    source_items = "".join(
        f"<li>{html.escape(name)}</li>" for name in winner.get("source_names", [])
    )
    body = f"""
<main>
<section class="swatch" style="background:{color};color:{text}">
<div><p class="kicker">Yesterday's Challenger · {html.escape(result['date'])}</p>
<h1>{html.escape(result.get('winner_name') or color)}</h1><p>{color}</p></div>
<div class="stats">
<div class="stat"><strong>{winner['source_count']}</strong>independent sources</div>
<div class="stat"><strong>{winner['sector_count']}</strong>commercial sectors</div>
<div class="stat"><strong>{winner['score']:.1f}</strong>Challenger Score</div>
</div></section>
<section><h2>What supported it</h2><p class="note">The winning cluster was selected after source-level baseline suppression, cross-source clustering, neutral-color penalties, and concentration checks.</p>
<ul>{source_items}</ul></section>
<section><h2>Evidence files</h2><p><a href="../../assets/{result['date']}/result.json">Result JSON</a> ·
<a href="../../assets/{result['date']}/observations.json">Observations JSON</a> ·
<a href="../../assets/{result['date']}/capture-report.json">Capture report</a></p></section>
</main>"""
    return _page(f"{result.get('winner_name')} — Pantone Challenger", body, "../../")


def build_site(archive_root: Path, site_root: Path, sources: list[Source]) -> None:
    results = _load_results(archive_root)
    if site_root.exists():
        shutil.rmtree(site_root)
    (site_root / "archive").mkdir(parents=True, exist_ok=True)
    (site_root / "assets").mkdir(parents=True, exist_ok=True)

    if results:
        latest = results[0]
        winner = latest["winner"]
        color = winner["hex"]
        text = _contrast(color)
        hero = f"""
<section class="hero"><p class="kicker">What color did the commercial internet use yesterday?</p>
<div class="swatch" style="background:{color};color:{text}">
<div><p class="kicker">{html.escape(latest['date'])} · YESTERDAY'S CHALLENGER</p>
<h1>{html.escape(latest.get('winner_name') or color)}</h1><p>{color}</p></div>
<div class="stats">
<div class="stat"><strong>{winner['source_count']}</strong>sources</div>
<div class="stat"><strong>{winner['sector_count']}</strong>sectors</div>
<div class="stat"><strong>{winner['score']:.1f}</strong>score</div>
</div></div></section>"""
    else:
        hero = """
<section class="hero"><p class="kicker">What color did the commercial internet use yesterday?</p>
<h1>THE FIRST LIVE RESULT IS PENDING.</h1>
<p class="note">The archive begins only after the real source panel passes its data-quality gate. No synthetic result is presented as a launch result.</p></section>"""

    tiles = "".join(_archive_tile(result) for result in results[:90])
    source_rows = "".join(
        f"<tr><td>{html.escape(source.name)}</td><td>{html.escape(source.sector.replace('_',' '))}</td>"
        f"<td><a href=\"{html.escape(source.url)}\" rel=\"nofollow\">official page</a></td></tr>"
        for source in sources
    )
    body = f"""{hero}
<main>
<section><h2>The archive</h2><div class="grid">{tiles or '<p>No approved live days yet.</p>'}</div></section>
<section><h2>The declared panel</h2><p class="note">Every enabled source is an official commercial or brand-owned page. Each brand receives one normalized vote per day regardless of how many visual elements appear on its page.</p>
<table><thead><tr><th>Source</th><th>Sector</th><th>Page</th></tr></thead><tbody>{source_rows}</tbody></table></section>
<section><h2>How it works</h2><p class="note">Each day the project browser-renders a balanced panel of marketing pages, extracts perceptually prominent colors, clusters similar shades in OKLab, suppresses colors that are ordinary for a particular brand, and rewards independent cross-sector spread. A quality gate blocks weak days. The algorithmic winner cannot be swapped out because it is unattractive.</p></section>
</main>"""
    (site_root / "index.html").write_text(
        _page("Pantone Challenger — The Commercial Color Index", body),
        encoding="utf-8",
    )

    for result in results:
        day = result["date"]
        detail_dir = site_root / "archive" / day
        detail_dir.mkdir(parents=True, exist_ok=True)
        (detail_dir / "index.html").write_text(_build_detail(result), encoding="utf-8")
        source_dir = archive_root / day
        asset_dir = site_root / "assets" / day
        asset_dir.mkdir(parents=True, exist_ok=True)
        for name in (
            "feed-post.png",
            "story-01-color.png",
            "story-02-evidence.png",
            "story-03-why-it-won.png",
            "story-04-runners-up.png",
            "caption.txt",
            "result.json",
            "observations.json",
            "capture-report.json",
            "manifest.json",
        ):
            src = source_dir / name
            if src.exists():
                shutil.copy2(src, asset_dir / name)

    (site_root / ".nojekyll").write_text("", encoding="utf-8")
    (site_root / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
