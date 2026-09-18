"""Item-scoped dates and opt-in ranked-chart observations. Never invent a date."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from dateutil.parser import parse

MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
TEXT_DATE = re.compile(
    rf"\b(?:{MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,|\s)\s*20\d{{2}}|\d{{1,2}}\s+{MONTH}\.?\s+20\d{{2}})\b",
    re.I,
)
DATE_RANGE = re.compile(
    rf"\b({MONTH})\.?\s+(\d{{1,2}})(?:,?\s+(20\d{{2}}))?\s*[–—-]\s*({MONTH})?\.?\s*(\d{{1,2}}),?\s+(20\d{{2}})\b",
    re.I,
)


def full_date(value: str) -> str:
    value = str(value or "").strip()
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}(?:$|[T ])", value):
            return date.fromisoformat(value[:10]).isoformat()
        match = TEXT_DATE.search(value)
        if match:
            return parse(match.group(), fuzzy=False).date().isoformat()
    except (ValueError, OverflowError):
        pass
    return ""


def normalized_url(value: str) -> str:
    p = urlsplit(value)
    return f"{p.scheme.lower()}://{p.netloc.lower()}{p.path.rstrip('/')}"


def _links(soup, base: str) -> list[str]:
    links = []
    for a in soup.select("a[href]"):
        url = urljoin(base, a["href"])
        if urlsplit(url).scheme in {"http", "https"} and normalized_url(url) != normalized_url(
            base
        ):
            links.append(url)
    return sorted(set(links))


def inspect_dates(
    markup: str, page_url: str, *, event_type: str = "", detail: bool = False
) -> dict:
    """Parse one card, or a matched detail document. A listing's dates are not inherited."""
    soup = BeautifulSoup(markup, "html.parser")
    item_links = _links(soup, page_url)
    result = {
        "kind": "undated",
        "published_at": "",
        "source_url": page_url,
        "item_url": item_links[0] if len(item_links) == 1 else "",
        "html_sha256": hashlib.sha256(markup.encode()).hexdigest(),
        "date_status": "missing",
        "scope": "detail" if detail else "card",
    }
    text = soup.get_text(" ", strip=True)
    exhibition = "exhibit" in event_type
    starts, ends, raw, methods = [], [], [], []
    # Dates on a multi-item block cannot be assigned to every image in the block.
    if not detail and len(item_links) > 1:
        result["date_status"] = "multiple_items"
        return result
    articles = soup.select("article")
    scoped = (
        (articles[0] if len(articles) == 1 else BeautifulSoup("", "html.parser"))
        if detail
        else soup
    )
    for node in list(scoped.select('time, [itemprop="dateModified"], .updated, .modified')):
        if node.name is None:
            continue
        marker = " ".join(node.get("class", [])) + node.get("itemprop", "")
        if re.search(r"updated|modified", marker, re.I):
            node.decompose()
    for node in scoped.select(
        '[itemprop="datePublished"], [itemprop="startDate"], [itemprop="endDate"]'
    ):
        value = node.get("content") or node.get("datetime") or node.get_text(" ", strip=True)
        parsed = full_date(value)
        raw.append(value)
        if parsed:
            (ends if node.get("itemprop") == "endDate" else starts).append(parsed)
            methods.append("itemprop:" + node["itemprop"])
    if detail:
        for node in soup.select(
            'meta[property="article:published_time"], meta[name="datePublished"]'
        ):
            value = node.get("content", "")
            raw.append(value)
            if full_date(value):
                starts.append(full_date(value))
                methods.append("publication_meta")

        def records(value):
            if isinstance(value, list):
                for item in value:
                    yield from records(item)
            elif isinstance(value, dict):
                yield value
                yield from records(value.get("@graph", []))

        for script in soup.select('script[type="application/ld+json"]')[:10]:
            try:
                data = json.loads(script.get_text())
            except (ValueError, TypeError):
                continue
            for record in records(data):
                types = record.get("@type", [])
                types = [types] if isinstance(types, str) else types
                if not isinstance(types, list) or not all(isinstance(t, str) for t in types):
                    continue
                if not set(types) & {
                    "Article",
                    "NewsArticle",
                    "BlogPosting",
                    "Event",
                    "ExhibitionEvent",
                    "CreativeWork",
                }:
                    continue
                record_url = (
                    record.get("url") or record.get("mainEntityOfPage") or record.get("@id", "")
                )
                if isinstance(record_url, dict):
                    record_url = record_url.get("@id", "")
                if not isinstance(record_url, str) or normalized_url(
                    urljoin(page_url, record_url)
                ) != normalized_url(page_url):
                    continue
                for key, dest in [
                    ("datePublished", starts),
                    ("startDate", starts),
                    ("endDate", ends),
                ]:
                    value = str(record.get(key, ""))
                    raw.append(value)
                    if full_date(value):
                        dest.append(full_date(value))
                        methods.append("jsonld:" + key)
    if not starts:
        times = [
            node
            for node in scoped.select("time[datetime]")
            if not re.search(
                r"updated|modified",
                " ".join(node.get("class", [])) + node.get("itemprop", ""),
                re.I,
            )
        ]
        for node in times:
            value = node.get("datetime", "")
            raw.append(value)
            if full_date(value):
                starts.append(full_date(value))
                methods.append("time:datetime")
        # Visible, explicit dates are used only within the selected card or article.
        body = scoped
        visible = body.get_text(" ", strip=True) if body else ""
        if not starts and exhibition:
            ranges = list(DATE_RANGE.finditer(visible))
            for match in ranges:
                m1, d1, y1, m2, d2, y2 = match.groups()
                a, b = full_date(f"{m1} {d1}, {y1 or y2}"), full_date(f"{m2 or m1} {d2}, {y2}")
                if a and b and a <= b:
                    starts.append(a)
                    ends.append(b)
                    raw.append(match.group())
                    methods.append("visible_event_range")
                else:
                    result["date_status"] = "ambiguous"
                    return result
        if not starts:
            for match in TEXT_DATE.finditer(visible):
                starts.append(full_date(match.group()))
                raw.append(match.group())
                methods.append("visible_full_date")
    starts, ends = sorted(set(filter(None, starts))), sorted(set(filter(None, ends)))
    result.update(raw_dates=raw[:12], context_text=text[:1200], methods=sorted(set(methods)))
    if len(starts) == 1 and len(ends) <= 1 and (not ends or starts[0] <= ends[0]):
        result.update(
            kind="exhibition" if exhibition else "publication",
            published_at=starts[0],
            event_end=ends[0] if ends else "",
            date_status="explicit",
        )
    elif starts:
        result["date_status"] = "ambiguous"
    return result


def ranked_snapshot(
    markup: str, page_url: str, title: str, policy: dict, captured_at: str
) -> dict | None:
    """Require an opted-in chart URL and at least three image/item/rank associations."""
    if policy.get("mode") != "ranked_snapshot":
        return None
    allowed = policy.get("urls", [])
    if normalized_url(page_url) not in {normalized_url(u) for u in allowed}:
        return None
    if not all(
        word.lower() in title.lower() for word in policy.get("title_words", ["top", "chart"])
    ):
        return None
    soup = BeautifulSoup(markup, "html.parser")
    prefixes = policy.get("item_path_prefixes", [])
    host = urlsplit(page_url).hostname

    def item_url(a):
        url = urljoin(page_url, a.get("href", ""))
        parts = urlsplit(url)
        return (
            url
            if parts.hostname == host and any(parts.path.startswith(p) for p in prefixes)
            else ""
        )

    items = {}
    for anchor in soup.select("a[href]"):
        url = item_url(anchor)
        if not url:
            continue
        parent = anchor
        for _ in range(6):
            parent = parent.parent
            if parent is None or parent.name in {"html", "body", "[document]"}:
                break
            urls = {item_url(a) for a in parent.select("a[href]")} - {""}
            if len(urls) > 1:
                break
            labels = parent.get_text("\n", strip=True).splitlines()
            ranks = {
                int(s.strip())
                for s in labels
                if re.fullmatch(r"\d{1,3}", s.strip()) and 1 <= int(s.strip()) <= 200
            }
            if urls == {url} and parent.select_one("img") and len(ranks) == 1:
                items[url] = {
                    "url": url,
                    "rank": next(iter(ranks)),
                    "label": parent.get_text(" ", strip=True)[:200],
                }
                break
    rows = sorted(items.values(), key=lambda x: x["rank"])
    if len(rows) < 3 or len({x["rank"] for x in rows}) != len(rows):
        return None
    return {
        "kind": "ranked_snapshot",
        "verified_by": "dom_ranked_chart_v1",
        "source_url": page_url,
        "observed_at": captured_at,
        "published_at": "",
        "scope": "region_dom",
        "items": rows[:100],
        "html_sha256": hashlib.sha256(markup.encode()).hexdigest(),
        "claim": "Ranked chart appearance observed at capture time; not a release date or proof of growth.",
    }


def snapshot_is_current(
    proof: dict, policy: dict, page_url: str, captured_at: str, run_date: str, timezone: str
) -> bool:
    try:
        urls = {normalized_url(u) for u in policy.get("urls", [])}
        rows = proof.get("items", [])
        moment = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        host = urlsplit(page_url).hostname
        prefixes = policy.get("item_path_prefixes", [])
        valid_rows = all(
            isinstance(r["rank"], int)
            and not isinstance(r["rank"], bool)
            and 1 <= r["rank"] <= 200
            and urlsplit(r["url"]).hostname == host
            and urlsplit(r["url"]).scheme == "https"
            and any(urlsplit(r["url"]).path.startswith(p) for p in prefixes)
            for r in rows
        )
        return (
            policy.get("mode") == "ranked_snapshot"
            and proof.get("verified_by") == "dom_ranked_chart_v1"
            and normalized_url(page_url) in urls
            and proof.get("source_url") == page_url
            and proof.get("observed_at") == captured_at
            and moment.tzinfo is not None
            and moment.astimezone(ZoneInfo(timezone)).date().isoformat() == run_date
            and bool(re.fullmatch(r"[0-9a-f]{64}", proof.get("html_sha256", "")))
            and valid_rows
            and len(rows) >= 3
            and len({r["url"] for r in rows}) == len(rows)
            and len({r["rank"] for r in rows}) == len(rows)
        )
    except (ValueError, TypeError, KeyError, AttributeError):
        return False
