from __future__ import annotations

import html
import json
import shutil
from pathlib import Path


CSS = """
:root{--paper:#f6f1e9;--ink:#161616;--muted:#6b655e;--card:#fffdf9;--line:#d8d0c5}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:Inter,Arial,sans-serif}
a{color:inherit}.wrap{max-width:1180px;margin:auto;padding:40px 24px 100px}header{display:flex;justify-content:space-between;gap:20px;align-items:baseline;border-bottom:1px solid var(--line);padding-bottom:22px}h1{font-size:clamp(2rem,6vw,5rem);line-height:.95;margin:50px 0 12px}.subtitle{font-size:1.1rem;color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:18px;margin-top:42px}.day{background:var(--card);border:1px solid var(--line);border-radius:18px;overflow:hidden;text-decoration:none}.swatch{height:170px}.meta{padding:16px}.meta strong{display:block;font-size:1.05rem}.meta span{font-size:.86rem;color:var(--muted)}.chips{display:flex;flex-wrap:wrap;gap:8px;margin:28px 0}.chip{border:1px solid var(--line);border-radius:999px;padding:8px 12px;background:var(--card)}.hero{display:grid;grid-template-columns:1.2fr .8fr;gap:28px;margin-top:42px}.hero-swatch{min-height:480px;border-radius:28px;padding:42px;display:flex;flex-direction:column;justify-content:flex-end}.panel{background:var(--card);border:1px solid var(--line);border-radius:24px;padding:28px}.metrics{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.metric{border-top:1px solid var(--line);padding-top:12px}.metric b{font-size:2rem;display:block}@media(max-width:800px){.hero{grid-template-columns:1fr}}
"""


def build_site(archive_dir: str | Path, destination: str | Path) -> Path:
    archive = Path(archive_dir)
    dest = Path(destination)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    days = []
    for day_dir in sorted((p for p in archive.glob("????-??-??") if p.is_dir()), reverse=True):
        path = day_dir / "result.json"
        if not path.exists():
            continue
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if result.get("state") != "ready":
            continue
        days.append((day_dir, result))
        _build_day(day_dir, result, dest / "days" / day_dir.name)
    (dest / "assets").mkdir(exist_ok=True)
    (dest / "assets" / "site.css").write_text(CSS, encoding="utf-8")
    cards = []
    for _, result in days:
        challenger = result.get("challenger", [])
        if not challenger:
            continue
        colors = [c["hex"] for c in challenger]
        gradient = colors[0] if len(colors) == 1 else f"linear-gradient(90deg,{','.join(colors)})"
        names = " + ".join(c.get("family_label", "Color") for c in challenger)
        cards.append(
            f'<a class="day" href="days/{result["date"]}/"><div class="swatch" style="background:{gradient}"></div>'
            f'<div class="meta"><strong>{html.escape(names)}</strong><span>{result["date"]} · {result.get("domains_covered",0)} domains</span></div></a>'
        )
    body = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Pantone Challenger</title><link rel="stylesheet" href="assets/site.css"></head><body><div class="wrap"><header><b>PANTONE CHALLENGER</b><span>THE OPEN CULTURAL COLOR INDEX</span></header><h1>How color moves<br>through culture.</h1><p class="subtitle">Daily evidence across creation, distribution, and attention—from independent signals to mainstream adoption.</p><div class="chips"><span class="chip">Undercurrents</span><span class="chip">Challengers</span><span class="chip">Ties welcome</span><span class="chip">No forced winner</span><a class="chip" href="methodology.html">Methodology</a></div><div class="grid">{''.join(cards) or '<p>No approved public days yet. Calibration is in progress.</p>'}</div></div></body></html>"""
    (dest / "index.html").write_text(body, encoding="utf-8")
    _write_methodology(dest)
    _write_feed(days, dest)
    return dest


def _build_day(source_dir: Path, result: dict, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name in ["feed-post.png", "story-01-color.png", "story-02-evidence.png", "story-03-why-it-won.png", "story-04-runners-up.png", "story-05-signal-map.png", "story-06-context.png"]:
        if (source_dir / name).exists():
            shutil.copy2(source_dir / name, dest / name)
    challenger = result.get("challenger", [])
    if not challenger:
        return
    primary = challenger[0]
    names = " + ".join(c.get("creative_name", c.get("family_label", "Color")) for c in challenger)
    colors = [c["hex"] for c in challenger]
    gradient = colors[0] if len(colors) == 1 else f"linear-gradient(90deg,{','.join(colors)})"
    evidence = primary.get("evidence", [])
    evidence_html = "".join(
        f'<li><b>{html.escape(e.get("source_name",""))}</b> — {html.escape(e.get("domain",""))} / {html.escape(e.get("signal_stage",""))} — local match <code>{e.get("local_hex","")}</code></li>'
        for e in evidence[:12]
    )
    body = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{html.escape(names)} — Pantone Challenger</title><link rel="stylesheet" href="../../assets/site.css"></head><body><div class="wrap"><header><a href="../../"><b>PANTONE CHALLENGER</b></a><span>{result['date']}</span></header><div class="hero"><div class="hero-swatch" style="background:{gradient};color:#111"><small>YESTERDAY’S CHALLENGER</small><h1>{html.escape(names)}</h1><b>{' + '.join(colors)}</b></div><div class="panel"><h2>Evidence</h2><div class="metrics"><div class="metric"><b>{result.get('sources_with_eligible_evidence',0)}</b>sources</div><div class="metric"><b>{result.get('domains_covered',0)}</b>domains</div><div class="metric"><b>{result.get('sectors_covered',0)}</b>sectors</div><div class="metric"><b>{result.get('stages_covered',0)}</b>stages</div><div class="metric"><b>{result.get('baseline_days',0)}</b>baseline days</div></div><p>Palette regime: <b>{html.escape(result.get('palette_regime',{}).get('dominant_regime',''))}</b></p></div></div><div class="panel" style="margin-top:28px"><h2>Traceable supporting sources</h2><ul>{evidence_html}</ul><p><a href="result.json">Machine-readable result</a></p></div></div></body></html>"""
    (dest / "index.html").write_text(body, encoding="utf-8")
    (dest / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


def _write_methodology(dest: Path) -> None:
    body = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Methodology — Pantone Challenger</title><link rel="stylesheet" href="assets/site.css"></head><body><div class="wrap"><header><a href="./"><b>PANTONE CHALLENGER</b></a><span>METHODOLOGY</span></header><h1>Measured, not declared.</h1><div class="panel"><p>Pantone Challenger samples declared sources across creation, distribution, and attention. It extracts colors only from eligible creative regions, gives each source a normalized vote, compares each source with its own history, balances benchmark and discovery panels, and permits ties or no winner.</p><p>Logos are attribution only. A displayed source must have a traceable local color swatch from sampled creative. Rights-restricted source imagery remains private.</p><p>The public claim is limited to the declared panel. It is not a measurement of the entire internet.</p></div></div></body></html>"""
    (dest / "methodology.html").write_text(body, encoding="utf-8")


def _write_feed(days, dest: Path) -> None:
    payload = [result for _, result in days]
    (dest / "feed.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
