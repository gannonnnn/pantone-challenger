"""A linked Color Trail from admitted observations, with no origin/causality claim."""
from __future__ import annotations

import html
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from challenger.baseline import observation_shares
from challenger.color import hex_to_oklab


def color_trail(archive: Path, hex_value: str, through_date: str, compatibility_key: str) -> list[dict]:
    rows = []
    if not compatibility_key:
        return rows
    lab = hex_to_oklab(hex_value)
    for day in sorted(archive.glob('????-??-??')):
        if day.name > through_date:
            continue
        try:
            manifest = json.loads((day / 'manifest.json').read_text())
            if (manifest.get('baseline_eligible') is not True or manifest.get('state') == 'blocked'
                    or manifest.get('baseline_compatibility_key') != compatibility_key):
                continue
            if manifest.get('schema_version') == 2:
                verification = json.loads((day / 'temporal-semantic-integrity.json').read_text())
                expected = manifest.get('validated_sha256', {}).get('observations.json')
                if (verification.get('passed') is not True
                        or hashlib.sha256((day / 'observations.json').read_bytes()).hexdigest() != expected):
                    continue
            observations = [o for o in json.loads((day / 'observations.json').read_text())
                            if o.get('metadata', {}).get('baseline_eligible') is True]
        except (ValueError, OSError, TypeError):
            continue
        shares = observation_shares(observations, lab)
        matching = {key for key, share in shares.items() if share > 0}
        evidence = {}
        for obs in observations:
            if obs['source_id'] not in matching:
                continue
            # Check this specific image, not merely another item from the same actor.
            if observation_shares([obs], lab).get(obs['source_id'], 0) <= 0:
                continue
            url = obs.get('region', {}).get('page_url', '')
            if urlsplit(url).scheme not in {'http', 'https'}:
                url = ''
            key = (obs['source_id'], url)
            evidence[key] = {'source': obs.get('source_name', ''), 'url': url,
                             'domain': obs.get('domain', ''), 'published_at': obs.get('region', {}).get('published_at', ''),
                             'captured_at': obs.get('captured_at', '')}
        rows.append({'date': day.name, 'matching_groups': len(matching), 'observed_groups': len(shares),
                     'state': manifest['state'], 'evidence': list(evidence.values())})
    return rows


def write_trail(archive: Path, result: dict, dest: Path) -> None:
    colors = result.get('challenger', [])
    sections = []
    payload = {}
    for candidate in colors:
        color = candidate['hex']
        rows = color_trail(archive, color, result['date'], result.get('baseline_compatibility_key', ''))
        payload[color] = rows
        rendered = []
        for row in rows:
            links = []
            for e in row['evidence'][:12]:
                label = html.escape(e['source'])
                links.append(f'<a href="{html.escape(e["url"], quote=True)}" rel="noreferrer">{label}</a>' if e['url'] else label)
            rendered.append(f'<tr><td>{row["date"]}</td><td>{row["matching_groups"]} / {row["observed_groups"]}</td><td>{html.escape(row["state"])}</td><td>{", ".join(links)}</td></tr>')
        sections.append(f'<h2>{html.escape(color)}</h2><table><thead><tr><th>Observed</th><th>Matching / observed groups</th><th>Record</th><th>Evidence</th></tr></thead><tbody>{"".join(rendered)}</tbody></table>')
    page = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Color Trail — Pantone Challenger</title><link rel="stylesheet" href="../../assets/site.css"><style>table{width:100%;border-collapse:collapse}td,th{text-align:left;vertical-align:top;border-bottom:1px solid #ccc;padding:12px;overflow-wrap:anywhere}@media(max-width:600px){table{font-size:12px}td,th{padding:6px}}</style></head><body><main class="wrap"><a href="./">Back to this result</a><h1>Color Trail</h1><p>Appearances within the monitored sample, through this result's date. Counts describe each day's observed sample; use the result's paired comparison to assess growth. A first observation does not establish origin or influence.</p>''' + ''.join(sections) + '<p><a href="color-trail.json">Download evidence records</a></p></main></body></html>'
    (dest / 'trail.html').write_text(page)
    (dest / 'color-trail.json').write_text(json.dumps(payload, indent=2))
