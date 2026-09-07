"""Pantone Challenger V1.5.2 temporal and semantic integrity gate.

This module runs after the existing V1.5.1 collection/scoring pipeline and before
any review pull request is opened.  It is intentionally conservative: it never
invents a replacement winner.  It verifies whether the proposed result is
current, semantically usable, sufficiently coherent, and honestly described.
When evidence fails, it downgrades or blocks the day and writes detailed audit
artifacts instead of allowing a polished but misleading social package.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, MutableMapping, Sequence
from urllib.parse import urlparse

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover - project normally depends on Pillow
    Image = None
    ImageDraw = None
    ImageFont = None

HEX_RE = re.compile(r"^#?[0-9A-Fa-f]{6}$")
URL_DATE_PATTERNS = (
    re.compile(r"(?<!\d)(20\d{2})[-_/](0?[1-9]|1[0-2])[-_/](0?[1-9]|[12]\d|3[01])(?!\d)"),
    re.compile(r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)"),
)
DATE_KEY_PARTS = (
    "published", "created", "updated", "modified", "opened", "starts",
    "start_date", "listed", "acquired", "digitized", "event_at", "event_date",
    "publication_date", "release_date", "opening_date",
)
NON_CONTENT_DATE_KEYS = {
    "date", "target_date", "cultural_date", "capture_date", "run_date",
    "observed_at", "retrieved_at", "fetched_at", "collected_at", "generated_at",
    "first_seen", "last_seen", "last_changed",
}
SOURCE_KEYS = ("source_id", "source", "source_name", "company_id", "company", "actor_id", "actor_name")
HEX_KEYS = ("local_hex", "matched_hex", "evidence_hex", "swatch_hex", "display_hex", "hex", "color")
REGION_KEYS = ("region_path", "screenshot_path", "image_path", "crop_path", "evidence_path", "path")
URL_KEYS = ("source_url", "url", "page_url", "item_url", "canonical_url", "link")

DEFAULT_CONFIG: dict[str, Any] = {
    "methodology_version": "1.5.2",
    "baseline_days_required": 7,
    "review_min_sources": 24,
    "public_min_sources": 30,
    "candidate_min_sources": 6,
    "candidate_min_domains": 4,
    "current_item_default_max_age_days": 2,
    "current_listing_max_age_days": 3,
    "exhibition_max_age_days": 45,
    "muted_chroma_threshold": 0.075,
    "muted_cluster_max_diameter": 0.032,
    "chromatic_cluster_max_diameter": 0.045,
    "candidate_match_distance": 0.055,
    "tie_score_delta": 2.5,
    "minimum_total_color_share": 0.020,
    "minimum_component_share": 0.005,
    "muted_minimum_total_color_share": 0.040,
    "muted_minimum_component_share": 0.010,
    "proof_pixel_distance": 0.035,
    "proof_max_dimension": 240,
    "historical_or_context_events": [
        "historical", "historically_resurfaced", "digitized", "archive", "collection",
        "newly_digitized", "catalog", "permanent_collection", "reference",
    ],
    "dated_discovery_events": [
        "newly_created", "newly_exhibited", "newly_published", "newly_listed",
        "newly_promoted", "launch", "release", "exhibition_opening", "degree_show",
        "art_fair", "open_studio", "grant_recipient", "new_arrival",
    ],
    "overlay_terms": [
        "cookie", "privacy", "consent", "verify", "verification", "captcha", "press and hold",
        "sign in", "log in", "subscribe", "newsletter", "accept all", "manage preferences",
        "terms of use", "enable javascript", "access denied", "are you a human",
    ],
}


@dataclass
class CandidateInfo:
    name: str = "Unknown candidate"
    hex: str = ""
    score: float | None = None
    source_count: int | None = None
    domain_count: int | None = None
    sector_count: int | None = None
    cluster_diameter: float | None = None
    neutral: bool = False
    eligible: bool = False
    evidence_count: int = 0


@dataclass
class AuditedCluster:
    display_hex: str
    score: float
    source_count: int
    domain_count: int
    stage_count: int
    scale_count: int
    panel_count: int
    cluster_diameter: float
    source_ids: list[str]
    domains: list[str]
    stages: list[str]
    local_hexes: list[str]
    eligible: bool


@dataclass
class EvidenceFinding:
    source_id: str
    source_name: str
    local_hex: str
    domain: str = "unknown"
    stage: str = "unknown"
    scale: str = "unknown"
    panel: str = "unknown"
    event_type: str = "unknown"
    source_url: str = ""
    region_path: str = ""
    temporal_status: str = "unknown"
    semantic_status: str = "unknown"
    supports_challenger: bool = False
    explicit_dates: list[str] = field(default_factory=list)
    url_dates: list[str] = field(default_factory=list)
    first_seen: str = ""
    last_seen: str = ""
    last_changed: str = ""
    total_color_share: float | None = None
    largest_component_share: float | None = None
    distance_to_candidate: float | None = None
    reasons: list[str] = field(default_factory=list)
    fingerprint: str = ""


@dataclass
class IntegrityReport:
    methodology_version: str
    target_date: str
    original_state: str
    final_state: str
    baseline_days: int
    coverage_analyzed: int | None
    coverage_active: int | None
    challenger: CandidateInfo
    reasons: list[str]
    warnings: list[str]
    temporal_counts: dict[str, int]
    semantic_counts: dict[str, int]
    source_breakdown: dict[str, dict[str, int]]
    eligible_candidate_sources: list[str]
    excluded_candidate_sources: dict[str, list[str]]
    tie: dict[str, Any]
    audited_challenger: AuditedCluster | None
    audited_ranking: list[AuditedCluster]
    evidence: list[EvidenceFinding]
    generated_at: str


def _load_config(root: Path) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    path = root / "config" / "temporal_semantic_integrity.json"
    if path.exists():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                cfg.update(value)
        except (OSError, json.JSONDecodeError):
            pass
    return cfg


def normalize_hex(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not HEX_RE.match(value):
        return ""
    return "#" + value.lstrip("#").upper()


def _first(record: Mapping[str, Any], keys: Sequence[str], default: Any = "") -> Any:
    lower = {str(k).lower(): v for k, v in record.items()}
    for key in keys:
        if key.lower() in lower and lower[key.lower()] not in (None, "", [], {}):
            return lower[key.lower()]
    return default


def _as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")


def _walk(value: Any) -> Iterator[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _load_json_documents(paths: Iterable[Path]) -> list[tuple[Path, Any]]:
    docs: list[tuple[Path, Any]] = []
    seen: set[Path] = set()
    for base in paths:
        if not base.exists():
            continue
        candidates = [base] if base.is_file() else list(base.rglob("*.json"))
        for path in candidates:
            try:
                rp = path.resolve()
            except OSError:
                rp = path
            if rp in seen:
                continue
            seen.add(rp)
            try:
                docs.append((path, json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
    return docs


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        try:
            ts = float(value)
            if ts > 10_000_000_000:
                ts /= 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc).date()
        except (ValueError, OSError, OverflowError):
            return None
    text = str(value).strip()
    if not text:
        return None
    cleaned = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(text).date()
    except (TypeError, ValueError, OverflowError):
        return None


def _dates_from_url(url: str) -> list[date]:
    found: list[date] = []
    if not url:
        return found
    for pattern in URL_DATE_PATTERNS:
        for match in pattern.finditer(url):
            try:
                found.append(date(int(match.group(1)), int(match.group(2)), int(match.group(3))))
            except ValueError:
                continue
    return sorted(set(found))


def _record_dates(record: Mapping[str, Any]) -> tuple[list[date], list[date]]:
    explicit: list[date] = []
    urls: list[date] = []
    for key, value in record.items():
        key_l = str(key).lower()
        if (
            isinstance(value, (str, int, float, datetime, date))
            and key_l not in NON_CONTENT_DATE_KEYS
            and any(part in key_l for part in DATE_KEY_PARTS)
        ):
            parsed = _parse_date(value)
            if parsed:
                explicit.append(parsed)
        if key_l in URL_KEYS or "url" in key_l or key_l == "link":
            if isinstance(value, str):
                urls.extend(_dates_from_url(value))
    return sorted(set(explicit)), sorted(set(urls))


def _srgb_to_linear(x: float) -> float:
    x /= 255.0
    return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4


def rgb_to_oklab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = (_srgb_to_linear(float(v)) for v in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = math.copysign(abs(l) ** (1 / 3), l), math.copysign(abs(m) ** (1 / 3), m), math.copysign(abs(s) ** (1 / 3), s)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = normalize_hex(value)
    if not value:
        return (0, 0, 0)
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def hex_to_oklab(value: str) -> tuple[float, float, float]:
    return rgb_to_oklab(hex_to_rgb(value))


def oklab_distance(left: str, right: str) -> float:
    a = hex_to_oklab(left)
    b = hex_to_oklab(right)
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def chroma(value: str) -> float:
    _, a, b = hex_to_oklab(value)
    return math.sqrt(a * a + b * b)


def is_neutral(value: str, threshold: float = 0.035) -> bool:
    return chroma(value) < threshold


def _candidate_from_summary(text: str) -> CandidateInfo:
    info = CandidateInfo()
    section = text
    match = re.search(r"(?ims)^#{1,3}\s*Challenger\s*$([\s\S]*?)(?=^#{1,3}\s|\Z)", text)
    if match:
        section = match.group(1)
    line_match = re.search(r"(?im)^\s*[-*]\s*(?:\*\*)?([^#\n—]+?)\s+(#[0-9A-Fa-f]{6})\b([^\n]*)", section)
    if not line_match:
        line_match = re.search(r"(?im)^\s*Candidate:\s*([^#\n]+?)\s+(#[0-9A-Fa-f]{6})\b([^\n]*)", text)
    if line_match:
        info.name = re.sub(r"[*_`]", "", line_match.group(1)).strip(" :-")
        info.hex = normalize_hex(line_match.group(2))
        tail = line_match.group(3)
        sm = re.search(r"(?:score|emergence)\s+([0-9.]+)", tail, re.I)
        if sm:
            info.score = _as_float(sm.group(1))
        src = re.search(r"(\d+)\s+sources?", tail, re.I)
        dom = re.search(r"(\d+)\s+domains?", tail, re.I)
        sec = re.search(r"(\d+)\s+sectors?", tail, re.I)
        dia = re.search(r"cluster\s+diameter\s*[:=]?\s*`?([0-9.]+)", tail, re.I)
        info.source_count = _as_int(src.group(1)) if src else None
        info.domain_count = _as_int(dom.group(1)) if dom else None
        info.sector_count = _as_int(sec.group(1)) if sec else None
        info.cluster_diameter = _as_float(dia.group(1)) if dia else None
    info.neutral = is_neutral(info.hex) if info.hex else False
    return info


def _coverage_from_summary(text: str) -> tuple[int | None, int | None]:
    match = re.search(r"Coverage:\s*(\d+)\s*/\s*(\d+)", text, re.I)
    return (_as_int(match.group(1)), _as_int(match.group(2))) if match else (None, None)


def _baseline_from_summary(text: str) -> int:
    patterns = (
        r"Historical baseline:\s*(\d+)\s+prior valid days",
        r"baseline[^\n]*?(\d+)\s*/\s*7",
        r"baseline_days[^0-9]*(\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1))
    return 0


def _state_from_summary(text: str, state_path: Path) -> str:
    if state_path.exists():
        try:
            value = state_path.read_text(encoding="utf-8").strip()
            if value:
                return value
        except OSError:
            pass
    match = re.search(r"State:\s*`?([a-z_]+)`?", text, re.I)
    return match.group(1).lower() if match else "unknown"


def _looks_like_evidence(record: Mapping[str, Any]) -> bool:
    source = _first(record, SOURCE_KEYS)
    color = normalize_hex(_first(record, HEX_KEYS))
    if not source or not color:
        return False
    keys = {str(k).lower() for k in record}
    return bool(keys.intersection(set(REGION_KEYS))) or any(
        term in keys for term in ("distance_to_candidate", "local_share", "matched_share", "region_confidence", "candidate_hex")
    )


def _evidence_records(docs: Sequence[tuple[Path, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for origin, doc in docs:
        for raw in _walk(doc):
            if not _looks_like_evidence(raw):
                continue
            record = dict(raw)
            record["__origin_file"] = str(origin)
            source = str(_first(record, SOURCE_KEYS))
            local_hex = normalize_hex(_first(record, HEX_KEYS))
            region = str(_first(record, REGION_KEYS))
            url = str(_first(record, URL_KEYS))
            key = hashlib.sha256(f"{source}|{local_hex}|{region}|{url}".encode()).hexdigest()
            if key in seen:
                continue
            seen.add(key)
            records.append(record)
    return records


def _source_records(docs: Sequence[tuple[Path, Any]]) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for origin, doc in docs:
        for raw in _walk(doc):
            source = _first(raw, SOURCE_KEYS)
            if not source:
                continue
            source_id = _slug(_first(raw, ("source_id", "company_id", "actor_id"), source)) or _slug(source)
            if not source_id:
                continue
            item = records.setdefault(source_id, {"source_id": source_id, "source_name": str(source)})
            for key_group, dest in (
                (("domain", "cultural_domain"), "domain"),
                (("signal_stage", "stage"), "stage"),
                (("scale_class", "scale"), "scale"),
                (("panel_type", "panel"), "panel"),
                (("sector", "industry_sector"), "sector"),
            ):
                value = _first(raw, key_group)
                if value and dest not in item:
                    item[dest] = str(value)
            item.setdefault("origin", str(origin))
    return list(records.values())



def _source_metadata_index(docs: Sequence[tuple[Path, Any]]) -> dict[str, dict[str, Any]]:
    """Collect parent/source metadata that may live outside nested evidence records."""
    index: dict[str, dict[str, Any]] = {}
    useful_keys = {
        "source_id", "source_name", "company_id", "company", "actor_id", "actor_name",
        "domain", "cultural_domain", "signal_stage", "stage", "scale_class", "scale",
        "panel_type", "panel", "sector", "industry_sector", "event_type", "event",
        "content_type", "source_url", "url", "page_url", "item_url", "canonical_url",
        "published_at", "published_date", "created_at", "updated_at", "event_date",
        "listed_at", "opened_at", "content_hash", "image_hash", "region_hash",
    }
    for origin, doc in docs:
        for raw in _walk(doc):
            source = _first(raw, SOURCE_KEYS)
            if not source:
                continue
            source_id = _slug(_first(raw, ("source_id", "company_id", "actor_id"), source))
            source_name_key = _slug(_first(raw, ("source_name", "company", "actor_name", "source"), source))
            for key in {source_id, source_name_key}:
                if not key:
                    continue
                item = index.setdefault(key, {"__origin_file": str(origin)})
                for raw_key, value in raw.items():
                    if str(raw_key).lower() in useful_keys and value not in (None, "", [], {}):
                        item.setdefault(str(raw_key), value)
    return index

def _candidate_records(docs: Sequence[tuple[Path, Any]]) -> list[CandidateInfo]:
    candidates: list[CandidateInfo] = []
    seen: set[str] = set()
    for _, doc in docs:
        for raw in _walk(doc):
            value = normalize_hex(_first(raw, ("display_hex", "candidate_hex", "hex", "color")))
            if not value:
                continue
            score = _as_float(_first(raw, ("emergence_score", "challenger_score", "score", "total_score"), None))
            source_count = _as_int(_first(raw, ("source_count", "company_count", "independent_sources", "sources"), None))
            if source_count is None:
                source_list = _first(raw, ("source_ids", "sources", "companies", "evidence"), [])
                if isinstance(source_list, list):
                    source_count = len(source_list)
            domain_count = _as_int(_first(raw, ("domain_count", "domains"), None))
            if domain_count is None:
                domains = _first(raw, ("domain_ids", "domains"), [])
                if isinstance(domains, list):
                    domain_count = len(set(map(str, domains)))
            if score is None and source_count is None:
                continue
            name = str(_first(raw, ("display_name", "name", "creative_name", "family_label"), value))
            key = f"{value}|{score}|{source_count}|{domain_count}"
            if key in seen:
                continue
            seen.add(key)
            candidates.append(CandidateInfo(
                name=name,
                hex=value,
                score=score,
                source_count=source_count,
                domain_count=domain_count,
                sector_count=_as_int(_first(raw, ("sector_count", "sectors"), None)),
                cluster_diameter=_as_float(_first(raw, ("cluster_diameter", "diameter", "max_distance"), None)),
                neutral=is_neutral(value),
            ))
    return candidates


def _resolve_region_path(root: Path, target_date: date, record: Mapping[str, Any]) -> Path | None:
    raw = str(_first(record, REGION_KEYS)).strip()
    candidates: list[Path] = []
    if raw:
        path = Path(raw)
        candidates.extend((path, root / path, root / ".work" / path, root / "archive" / path))
    origin = Path(str(record.get("__origin_file", "")))
    if raw and origin:
        candidates.append(origin.parent / raw)
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    if raw:
        name = Path(raw).name
        search_bases = (root / ".work", root / "archive" / target_date.isoformat())
        for base in search_bases:
            if base.exists():
                matches = list(base.rglob(name))
                if matches:
                    return matches[0]
    return None


def _fingerprint(path: Path | None, record: Mapping[str, Any]) -> str:
    for key in ("content_hash", "image_hash", "sha256", "pixel_hash", "region_hash", "phash"):
        value = record.get(key)
        if value:
            return str(value)
    digest = hashlib.sha256()
    if path and path.exists():
        try:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except OSError:
            pass
    digest.update(json.dumps({
        "source": _first(record, SOURCE_KEYS),
        "url": _first(record, URL_KEYS),
        "hex": _first(record, HEX_KEYS),
        "region": _first(record, REGION_KEYS),
    }, sort_keys=True, default=str).encode())
    return digest.hexdigest()


def _mask_component_stats(path: Path, target_hex: str, cfg: Mapping[str, Any]) -> tuple[float, float] | None:
    if Image is None:
        return None
    try:
        with Image.open(path) as opened:
            image = opened.convert("RGBA")
            max_dim = int(cfg["proof_max_dimension"])
            scale = min(1.0, max_dim / max(image.size))
            if scale < 1:
                image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))))
            target = hex_to_oklab(target_hex)
            pixels = list(image.getdata())
    except (OSError, ValueError):
        return None
    width, height = image.size
    mask = bytearray(width * height)
    valid = 0
    matching = 0
    tolerance = float(cfg["proof_pixel_distance"])
    for idx, (r, g, b, a) in enumerate(pixels):
        if a < 32:
            continue
        valid += 1
        lab = rgb_to_oklab((r, g, b))
        distance = math.sqrt(sum((x - y) ** 2 for x, y in zip(lab, target)))
        if distance <= tolerance:
            mask[idx] = 1
            matching += 1
    if valid == 0:
        return (0.0, 0.0)
    visited = bytearray(width * height)
    largest = 0
    for idx, flag in enumerate(mask):
        if not flag or visited[idx]:
            continue
        visited[idx] = 1
        queue: deque[int] = deque([idx])
        size = 0
        while queue:
            current = queue.popleft()
            size += 1
            y, x = divmod(current, width)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        nxt = ny * width + nx
                        if mask[nxt] and not visited[nxt]:
                            visited[nxt] = 1
                            queue.append(nxt)
        largest = max(largest, size)
    return matching / valid, largest / valid


def _load_prior_ledger(root: Path, target: date) -> dict[str, Any]:
    combined: dict[str, Any] = {"sources": {}}
    archive = root / "archive"
    if not archive.exists():
        return combined
    dated: list[tuple[date, Path]] = []
    for path in archive.glob("*/temporal-ledger.json"):
        try:
            d = date.fromisoformat(path.parent.name)
        except ValueError:
            continue
        if d < target:
            dated.append((d, path))
    for _, path in sorted(dated):
        try:
            ledger = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for source_id, value in ledger.get("sources", {}).items():
            combined["sources"][source_id] = value
    return combined


def _region_ledger_key(record: Mapping[str, Any]) -> str:
    explicit = _first(record, ("region_id", "frame_id", "selector_hint"), "")
    if explicit:
        return _slug(explicit) or hashlib.sha256(str(explicit).encode()).hexdigest()[:16]
    region = str(_first(record, REGION_KEYS)).strip()
    if region:
        return _slug(Path(region).stem) or hashlib.sha256(region.encode()).hexdigest()[:16]
    stable = f"{_first(record, URL_KEYS)}|{_first(record, HEX_KEYS)}"
    return hashlib.sha256(stable.encode()).hexdigest()[:16]


def _temporal_status(
    record: Mapping[str, Any], target: date, prior: Mapping[str, Any], fingerprint: str, cfg: Mapping[str, Any]
) -> tuple[str, list[str], list[date], list[date], str, str, str]:
    explicit, url_dates = _record_dates(record)
    all_dates = sorted(set(explicit + url_dates))
    reasons: list[str] = []
    event = _slug(_first(record, ("event_type", "event", "content_type"), "unknown"))
    domain = _slug(_first(record, ("domain", "cultural_domain"), "unknown"))
    stage = _slug(_first(record, ("signal_stage", "stage"), "unknown"))
    panel = _slug(_first(record, ("panel_type", "panel"), "unknown"))
    scale = _slug(_first(record, ("scale_class", "scale"), "unknown"))
    source_id = _slug(_first(record, ("source_id", "company_id", "actor_id"), _first(record, SOURCE_KEYS)))
    prior_source = prior.get("sources", {}).get(source_id, {}) if isinstance(prior, Mapping) else {}
    region_key = _region_ledger_key(record)
    prior_region = {}
    if isinstance(prior_source, Mapping):
        regions = prior_source.get("regions", {})
        if isinstance(regions, Mapping):
            prior_region = regions.get(region_key, {}) or {}
    prior_record = prior_region if isinstance(prior_region, Mapping) and prior_region else prior_source
    prior_fingerprint = str(prior_record.get("fingerprint", "")) if isinstance(prior_record, Mapping) else ""
    first_seen = str(prior_record.get("first_seen", target.isoformat())) if prior_fingerprint == fingerprint else target.isoformat()
    last_changed = str(prior_record.get("last_changed", target.isoformat())) if prior_fingerprint == fingerprint else target.isoformat()
    last_seen = target.isoformat()

    future = [d for d in all_dates if d > target]
    if future:
        reasons.append("Evidence is dated after the requested cultural date: " + ", ".join(d.isoformat() for d in future))
        return "rejected_future", reasons, explicit, url_dates, first_seen, last_seen, last_changed

    overlay_text = " ".join(str(v) for k, v in record.items() if isinstance(v, str) and k != "__origin_file").lower()
    if any(term in overlay_text for term in cfg["overlay_terms"]):
        reasons.append("Evidence metadata resembles an overlay, consent, login, or verification interface.")
        return "rejected_overlay", reasons, explicit, url_dates, first_seen, last_seen, last_changed

    historical_events = {_slug(value) for value in cfg["historical_or_context_events"]}
    dated_discovery_events = {_slug(value) for value in cfg["dated_discovery_events"]}
    historical = event in historical_events
    discovery = panel == "discovery" or scale in {"grassroots", "independent"}
    creation_like = stage == "creation" or event in dated_discovery_events

    if historical:
        if not all_dates:
            reasons.append("Historical or catalog material has no current dated resurfacing event.")
            return "context_only_historical", reasons, explicit, url_dates, first_seen, last_seen, last_changed
        current_dates = [d for d in all_dates if 0 <= (target - d).days <= int(cfg["current_item_default_max_age_days"])]
        if not current_dates:
            reasons.append("Historical material is not tied to a current event window.")
            return "context_only_historical", reasons, explicit, url_dates, first_seen, last_seen, last_changed

    if not all_dates:
        if discovery or creation_like or domain == "art":
            reasons.append("Discovery, creation, or art evidence needs a dated cultural event.")
            return "context_only_undated", reasons, explicit, url_dates, first_seen, last_seen, last_changed
        if prior_fingerprint and prior_fingerprint == fingerprint:
            reasons.append("Undated benchmark creative is unchanged; it can inform baseline or mainstream usage only.")
            return "baseline_only_unchanged", reasons, explicit, url_dates, first_seen, last_seen, last_changed
        if prior_fingerprint and prior_fingerprint != fingerprint:
            reasons.append("Undated benchmark creative changed since its prior fingerprint; the change is current distribution evidence.")
            return "eligible_changed_today", reasons, explicit, url_dates, first_seen, last_seen, last_changed
        reasons.append("Undated benchmark creative may seed calibration but cannot prove emergence until a prior fingerprint exists.")
        return "calibration_only_undated", reasons, explicit, url_dates, first_seen, last_seen, last_changed

    most_recent = max(d for d in all_dates if d <= target)
    age = (target - most_recent).days
    max_age = int(cfg["current_item_default_max_age_days"])
    if "exhibition" in event or event in {"art-fair", "art_fair", "open-studio", "open_studio", "degree-show", "degree_show"}:
        max_age = int(cfg["exhibition_max_age_days"])
    elif "list" in event or "marketplace" in domain or event in {"new-arrival", "new_arrival"}:
        max_age = int(cfg["current_listing_max_age_days"])
    if age > max_age:
        if discovery or creation_like or domain == "art":
            reasons.append(f"Dated evidence is {age} days old; the allowed current window is {max_age} days.")
            return "context_only_stale", reasons, explicit, url_dates, first_seen, last_seen, last_changed
        reasons.append(f"Benchmark creative is {age} days old and can inform baseline or mainstream usage only.")
        return "baseline_only_stale", reasons, explicit, url_dates, first_seen, last_seen, last_changed

    reasons.append(f"Evidence date is within the {max_age}-day current window.")
    return "eligible_current", reasons, explicit, url_dates, first_seen, last_seen, last_changed


def _source_breakdown(records: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    output: dict[str, dict[str, int]] = {}
    for dimension in ("domain", "stage", "scale", "panel", "sector"):
        by_source: dict[str, str] = {}
        for record in records:
            source_id = str(record.get("source_id") or record.get("source_name") or "")
            value = _slug(record.get(dimension, "unknown")) or "unknown"
            if source_id:
                by_source[source_id] = value
        output[dimension] = dict(sorted(Counter(by_source.values()).items(), key=lambda item: (-item[1], item[0])))
    return output


def _candidate_evidence(
    root: Path,
    target: date,
    records: Sequence[Mapping[str, Any]],
    challenger: CandidateInfo,
    prior: Mapping[str, Any],
    cfg: Mapping[str, Any],
    metadata_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[EvidenceFinding]:
    output: list[EvidenceFinding] = []
    seen: set[tuple[str, str, str]] = set()
    metadata_index = metadata_index or {}
    for original_record in records:
        record = dict(original_record)
        source_probe = _slug(_first(record, ("source_id", "company_id", "actor_id"), _first(record, SOURCE_KEYS)))
        name_probe = _slug(_first(record, ("source_name", "company", "actor_name", "source"), ""))
        inherited = metadata_index.get(source_probe) or metadata_index.get(name_probe) or {}
        for inherited_key, inherited_value in inherited.items():
            if inherited_key not in record and inherited_value not in (None, "", [], {}):
                record[inherited_key] = inherited_value
        local_hex = normalize_hex(_first(record, HEX_KEYS))
        if not local_hex:
            continue
        if challenger.hex:
            distance = _as_float(_first(record, ("distance_to_candidate", "candidate_distance", "distance"), None))
            if distance is None:
                distance = oklab_distance(local_hex, challenger.hex)
            if distance > float(cfg["candidate_match_distance"]):
                continue
        else:
            distance = 0.0
        source_name = str(_first(record, ("source_name", "company", "actor_name", "source"), "Unknown source"))
        source_id = _slug(_first(record, ("source_id", "company_id", "actor_id"), source_name))
        region_value = str(_first(record, REGION_KEYS))
        key = (source_id, local_hex, region_value)
        if key in seen:
            continue
        seen.add(key)
        path = _resolve_region_path(root, target, record)
        fingerprint = _fingerprint(path, record)
        temporal, temporal_reasons, explicit, url_dates, first_seen, last_seen, last_changed = _temporal_status(
            record, target, prior, fingerprint, cfg
        )
        stats = _mask_component_stats(path, local_hex, cfg) if path else None
        total = _as_float(_first(record, ("local_share", "matched_share", "color_share", "total_color_share"), None))
        component = _as_float(_first(record, ("largest_component_share", "component_share", "largest_component_ratio"), None))
        if stats:
            total, component = stats
        muted = chroma(local_hex) < float(cfg["muted_chroma_threshold"])
        min_total = float(cfg["muted_minimum_total_color_share"] if muted else cfg["minimum_total_color_share"])
        min_component = float(cfg["muted_minimum_component_share"] if muted else cfg["minimum_component_share"])
        semantic = "eligible"
        semantic_reasons: list[str] = []
        if total is None or component is None:
            semantic = "unverified_region_substance"
            semantic_reasons.append("No resolvable evidence image or connected-area metrics were available.")
        elif total < min_total:
            semantic = "incidental_low_share"
            semantic_reasons.append(f"Matched color covers {total:.2%}; at least {min_total:.2%} is required.")
        elif component < min_component:
            semantic = "incidental_fragmented"
            semantic_reasons.append(f"Largest connected patch covers {component:.2%}; at least {min_component:.2%} is required.")
        else:
            semantic_reasons.append(
                f"Matched color covers {total:.2%}; largest connected patch covers {component:.2%}."
            )
        supports = temporal.startswith("eligible_") and semantic == "eligible"
        output.append(EvidenceFinding(
            source_id=source_id,
            source_name=source_name,
            local_hex=local_hex,
            domain=_slug(_first(record, ("domain", "cultural_domain"), "unknown")) or "unknown",
            stage=_slug(_first(record, ("signal_stage", "stage"), "unknown")) or "unknown",
            scale=_slug(_first(record, ("scale_class", "scale"), "unknown")) or "unknown",
            panel=_slug(_first(record, ("panel_type", "panel"), "unknown")) or "unknown",
            event_type=_slug(_first(record, ("event_type", "event", "content_type"), "unknown")) or "unknown",
            source_url=str(_first(record, URL_KEYS)),
            region_path=str(path or region_value),
            temporal_status=temporal,
            semantic_status=semantic,
            supports_challenger=supports,
            explicit_dates=[d.isoformat() for d in explicit],
            url_dates=[d.isoformat() for d in url_dates],
            first_seen=first_seen,
            last_seen=last_seen,
            last_changed=last_changed,
            total_color_share=total,
            largest_component_share=component,
            distance_to_candidate=distance,
            reasons=temporal_reasons + semantic_reasons,
            fingerprint=fingerprint,
        ))
    return output



def _cluster_medoid(findings: Sequence[EvidenceFinding]) -> str:
    unique = sorted({item.local_hex for item in findings if item.local_hex})
    if not unique:
        return ""
    source_weight: Counter[str] = Counter(item.local_hex for item in findings)
    return min(
        unique,
        key=lambda value: sum(oklab_distance(value, other) * source_weight[other] for other in unique),
    )


def _cluster_diameter_hex(values: Sequence[str]) -> float:
    unique = sorted(set(values))
    diameter = 0.0
    for index, left in enumerate(unique):
        for right in unique[index + 1:]:
            diameter = max(diameter, oklab_distance(left, right))
    return diameter


def _audited_clusters(findings: Sequence[EvidenceFinding], cfg: Mapping[str, Any]) -> list[AuditedCluster]:
    """Build a conservative independent ranking from integrity-approved local swatches.

    Complete-link clustering prevents a chain of nearby colors from drifting into one
    broad cluster. Each source contributes at most one record per cluster.
    """
    eligible_findings = [
        item for item in findings
        if item.temporal_status.startswith("eligible_") and item.semantic_status == "eligible"
    ]
    eligible_findings.sort(
        key=lambda item: (
            item.total_color_share or 0.0,
            item.largest_component_share or 0.0,
            item.source_id,
        ),
        reverse=True,
    )
    groups: list[list[EvidenceFinding]] = []
    for item in eligible_findings:
        item_muted = chroma(item.local_hex) < float(cfg["muted_chroma_threshold"])
        placed = False
        for group in groups:
            group_muted = all(chroma(member.local_hex) < float(cfg["muted_chroma_threshold"]) for member in group)
            if item_muted != group_muted:
                continue
            limit = float(cfg["muted_cluster_max_diameter"] if item_muted else cfg["chromatic_cluster_max_diameter"])
            if all(oklab_distance(item.local_hex, member.local_hex) <= limit for member in group):
                group.append(item)
                placed = True
                break
        if not placed:
            groups.append([item])

    output: list[AuditedCluster] = []
    for group in groups:
        # Keep one strongest observation per independent source.
        by_source: dict[str, EvidenceFinding] = {}
        for item in group:
            current = by_source.get(item.source_id)
            item_strength = (item.total_color_share or 0.0) + (item.largest_component_share or 0.0)
            current_strength = ((current.total_color_share or 0.0) + (current.largest_component_share or 0.0)) if current else -1.0
            if current is None or item_strength > current_strength:
                by_source[item.source_id] = item
        items = list(by_source.values())
        source_ids = sorted(by_source)
        domains = sorted({item.domain for item in items if item.domain and item.domain != "unknown"})
        stages = sorted({item.stage for item in items if item.stage and item.stage != "unknown"})
        scales = sorted({item.scale for item in items if item.scale and item.scale != "unknown"})
        panels = sorted({item.panel for item in items if item.panel and item.panel != "unknown"})
        local_hexes = [item.local_hex for item in items]
        substance_values = [
            min(1.0, ((item.total_color_share or 0.0) / 0.18 + (item.largest_component_share or 0.0) / 0.08) / 2)
            for item in items
        ]
        substance = sum(substance_values) / len(substance_values) if substance_values else 0.0
        score = (
            40.0 * min(len(source_ids) / 15.0, 1.0)
            + 25.0 * min(len(domains) / 8.0, 1.0)
            + 15.0 * min(len(stages) / 3.0, 1.0)
            + 8.0 * min(len(scales) / 4.0, 1.0)
            + 5.0 * min(len(panels) / 2.0, 1.0)
            + 7.0 * substance
        )
        display_hex = _cluster_medoid(items)
        output.append(AuditedCluster(
            display_hex=display_hex,
            score=round(score, 4),
            source_count=len(source_ids),
            domain_count=len(domains),
            stage_count=len(stages),
            scale_count=len(scales),
            panel_count=len(panels),
            cluster_diameter=round(_cluster_diameter_hex(local_hexes), 6),
            source_ids=source_ids,
            domains=domains,
            stages=stages,
            local_hexes=sorted(set(local_hexes)),
            eligible=(
                len(source_ids) >= int(cfg["candidate_min_sources"])
                and len(domains) >= int(cfg["candidate_min_domains"])
                and not is_neutral(display_hex)
            ),
        ))
    return sorted(output, key=lambda item: (item.eligible, item.score, item.source_count), reverse=True)


def _audited_tie(ranking: Sequence[AuditedCluster], cfg: Mapping[str, Any]) -> dict[str, Any]:
    eligible = [item for item in ranking if item.eligible]
    if len(eligible) < 2:
        return {
            "is_tie": False,
            "reason": "Fewer than two temporally and semantically eligible chromatic clusters qualified.",
            "eligible_candidates": [asdict(item) for item in eligible[:5]],
        }
    first, second = eligible[0], eligible[1]
    delta = abs(first.score - second.score)
    return {
        "is_tie": delta <= float(cfg["tie_score_delta"]),
        "score_delta": round(delta, 4),
        "threshold": float(cfg["tie_score_delta"]),
        "first": asdict(first),
        "second": asdict(second),
        "reason": "Tie evaluated only after temporal, semantic, neutral, source, and domain eligibility filters.",
        "eligible_candidates": [asdict(item) for item in eligible[:5]],
    }

def _tie_analysis(candidates: Sequence[CandidateInfo], challenger: CandidateInfo, cfg: Mapping[str, Any]) -> dict[str, Any]:
    eligible: list[CandidateInfo] = []
    for candidate in candidates:
        candidate.eligible = bool(
            candidate.hex
            and not candidate.neutral
            and candidate.score is not None
            and (candidate.source_count or 0) >= int(cfg["candidate_min_sources"])
            and (candidate.domain_count or 0) >= int(cfg["candidate_min_domains"])
        )
        if candidate.eligible:
            eligible.append(candidate)
    eligible.sort(key=lambda c: c.score or float("-inf"), reverse=True)
    if challenger.hex and not any(c.hex == challenger.hex for c in eligible):
        copy = CandidateInfo(**asdict(challenger))
        copy.eligible = bool(
            not copy.neutral
            and copy.score is not None
            and (copy.source_count or 0) >= int(cfg["candidate_min_sources"])
            and (copy.domain_count or 0) >= int(cfg["candidate_min_domains"])
        )
        if copy.eligible:
            eligible.append(copy)
            eligible.sort(key=lambda c: c.score or float("-inf"), reverse=True)
    if len(eligible) < 2:
        return {"is_tie": False, "reason": "Fewer than two eligible chromatic candidates qualified.", "eligible_candidates": [asdict(c) for c in eligible[:5]]}
    first, second = eligible[0], eligible[1]
    delta = abs((first.score or 0) - (second.score or 0))
    return {
        "is_tie": delta <= float(cfg["tie_score_delta"]),
        "score_delta": round(delta, 4),
        "threshold": float(cfg["tie_score_delta"]),
        "first": asdict(first),
        "second": asdict(second),
        "reason": "Tie evaluated only after candidate eligibility and neutral filtering.",
        "eligible_candidates": [asdict(c) for c in eligible[:5]],
    }


def _write_ledger(root: Path, target: date, evidence: Sequence[EvidenceFinding]) -> dict[str, Any]:
    sources: dict[str, Any] = {}
    for item in evidence:
        source = sources.setdefault(item.source_id, {
            "source_name": item.source_name,
            "first_seen": item.first_seen,
            "last_seen": item.last_seen,
            "last_changed": item.last_changed,
            "regions": {},
        })
        region_key = _slug(Path(item.region_path).stem) if item.region_path else hashlib.sha256(
            f"{item.source_url}|{item.local_hex}".encode()
        ).hexdigest()[:16]
        region_key = region_key or hashlib.sha256(f"{item.source_id}|{item.local_hex}".encode()).hexdigest()[:16]
        source["regions"][region_key] = {
            "fingerprint": item.fingerprint,
            "first_seen": item.first_seen,
            "last_seen": item.last_seen,
            "last_changed": item.last_changed,
            "temporal_status": item.temporal_status,
            "semantic_status": item.semantic_status,
            "local_hex": item.local_hex,
            "region_path": item.region_path,
        }
        source["last_seen"] = max(str(source.get("last_seen", "")), item.last_seen)
        if item.last_changed > str(source.get("last_changed", "")):
            source["last_changed"] = item.last_changed
        # Flat fields are retained for compatibility with the first V1.5.2 ledger.
        if item.supports_challenger or "fingerprint" not in source:
            source["fingerprint"] = item.fingerprint
            source["local_hex"] = item.local_hex
    ledger = {
        "methodology_version": "1.5.2",
        "target_date": target.isoformat(),
        "sources": sources,
    }
    path = root / "archive" / target.isoformat() / "temporal-ledger.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, sort_keys=True), encoding="utf-8")
    return ledger


def _watermark_internal(path: Path, label: str) -> None:
    if Image is None or ImageDraw is None:
        return
    try:
        with Image.open(path) as opened:
            image = opened.convert("RGBA")
    except OSError:
        return
    height = max(54, int(image.height * 0.055))
    overlay = Image.new("RGBA", (image.width, height), (20, 20, 20, 230))
    draw = ImageDraw.Draw(overlay)
    font = None
    for candidate in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
        if Path(candidate).exists():
            try:
                font = ImageFont.truetype(candidate, max(18, int(height * 0.34))) if ImageFont else None
                break
            except OSError:
                pass
    text = label.upper()
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text(((image.width - (bbox[2] - bbox[0])) / 2, (height - (bbox[3] - bbox[1])) / 2 - bbox[1]), text, fill=(255, 255, 255, 255), font=font)
    image.alpha_composite(overlay, (0, 0))
    image.convert("RGB").save(path, quality=95)


def _protect_assets(root: Path, target: date, state: str) -> None:
    archive = root / "archive" / target.isoformat()
    if not archive.exists():
        return
    image_patterns = ("feed*.png", "story*.png", "social*.png", "*post*.png")
    assets: list[Path] = []
    for pattern in image_patterns:
        assets.extend(archive.glob(pattern))
    if state == "blocked":
        quarantine = root / ".work" / target.isoformat() / "quarantined-social-assets"
        quarantine.mkdir(parents=True, exist_ok=True)
        for path in sorted(set(assets)):
            try:
                shutil.move(str(path), str(quarantine / path.name))
            except OSError:
                pass
        for path in archive.glob("caption*.txt"):
            try:
                shutil.move(str(path), str(quarantine / path.name))
            except OSError:
                pass
        (archive / "NO_PUBLIC_ASSETS.txt").write_text(
            "V1.5.2 integrity checks blocked this day. Any generated social assets were quarantined.\n",
            encoding="utf-8",
        )
    elif state in {"review_only", "baseline_only"}:
        for path in sorted(set(assets)):
            _watermark_internal(path, "INTERNAL CALIBRATION — DO NOT POST")
        (archive / "INTERNAL_ONLY.txt").write_text(
            "This result is calibration or baseline material and is not approved for social posting.\n",
            encoding="utf-8",
        )


def _format_breakdown(values: Mapping[str, int]) -> str:
    if not values:
        return "No structured records found"
    return ", ".join(f"{name.replace('-', ' ').title()}: {count}" for name, count in values.items())


def _integrity_markdown(report: IntegrityReport) -> str:
    c = report.challenger
    lines = [
        "## V1.5.2 temporal and semantic integrity",
        "",
        f"**Final state:** `{report.final_state}`  ",
        f"**Methodology:** `{report.methodology_version}`  ",
        f"**Historical baseline:** {report.baseline_days}/7 prior valid days  ",
    ]
    if c.hex:
        lines.extend([
            f"**Pipeline candidate:** {c.name} `{c.hex}`  ",
            "**Trend interpretation:** " + (
                "Emergence can be evaluated against historical behavior.  "
                if report.baseline_days >= 7
                else "Calibration only; no emergence claim is made before seven prior valid days.  "
            ),
        ])
    if report.coverage_analyzed is not None and report.coverage_active is not None:
        lines.append(f"**Coverage:** {report.coverage_analyzed}/{report.coverage_active} active sources  ")
    if report.audited_challenger is not None:
        audited = report.audited_challenger
        lines.extend([
            f"**Integrity-audited candidate:** `{audited.display_hex}` — {audited.source_count} current sources, {audited.domain_count} domains, {audited.stage_count} stages  ",
            f"**Audited calibration breadth score:** {audited.score:.1f}  ",
        ])
    lines.extend(["", "### Integrity decision", ""])
    if report.reasons:
        lines.extend(f"- {reason}" for reason in report.reasons)
    else:
        lines.append("- No blocking integrity condition was found.")
    if report.warnings:
        lines.extend(["", "### Warnings", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)
    lines.extend([
        "",
        "### Source balance",
        "",
        f"- **Domains:** {_format_breakdown(report.source_breakdown.get('domain', {}))}",
        f"- **Signal stages:** {_format_breakdown(report.source_breakdown.get('stage', {}))}",
        f"- **Scale classes:** {_format_breakdown(report.source_breakdown.get('scale', {}))}",
        f"- **Panels:** {_format_breakdown(report.source_breakdown.get('panel', {}))}",
        "",
        "### Candidate evidence after integrity filtering",
        "",
        f"- **Eligible current sources:** {len(report.eligible_candidate_sources)}",
        f"- **Excluded or context-only sources:** {len(report.excluded_candidate_sources)}",
        f"- **Temporal statuses:** {_format_breakdown(report.temporal_counts)}",
        f"- **Semantic statuses:** {_format_breakdown(report.semantic_counts)}",
        "",
        "### Tie evaluation",
        "",
        f"- **Co-Challenger:** {'yes' if report.tie.get('is_tie') else 'no'}",
        f"- {report.tie.get('reason', 'Tie data unavailable.')}",
        "",
        "The detailed machine-readable report and temporal ledger are included with the private evidence artifact.",
    ])
    return "\n".join(lines).strip() + "\n"


def _rewrite_review_summary(path: Path, report: IntegrityReport) -> None:
    original = path.read_text(encoding="utf-8") if path.exists() else f"# Pantone Challenger — {report.target_date}\n"
    original = re.sub(
        r"(?is)\n## V1\.5\.2 temporal and semantic integrity\n.*\Z",
        "",
        original,
    ).rstrip() + "\n"
    if report.baseline_days < 7:
        original = re.sub(
            r"\bemergence\s+([0-9]+(?:\.[0-9]+)?)",
            rf"provisional calibration score \1",
            original,
            flags=re.I,
        )
        original = re.sub(
            r"(?im)^\s*[-*]\s*The leading score is close[^\n]*\n?",
            "",
            original,
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(original + "\n" + _integrity_markdown(report), encoding="utf-8")


def run_integrity(root: Path, target: date) -> IntegrityReport:
    cfg = _load_config(root)
    archive_dir = root / "archive" / target.isoformat()
    archive_dir.mkdir(parents=True, exist_ok=True)
    summary_path = archive_dir / "review-summary.md"
    state_path = archive_dir / "workflow-state.txt"
    summary = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""
    original_state = _state_from_summary(summary, state_path)
    challenger = _candidate_from_summary(summary)
    analyzed, active = _coverage_from_summary(summary)
    baseline_days = _baseline_from_summary(summary)

    doc_paths = [archive_dir, root / ".work", root / "data"]
    docs = _load_json_documents(doc_paths)
    evidence_records = _evidence_records(docs)
    source_records = _source_records(docs)
    metadata_index = _source_metadata_index(docs)
    candidate_records = _candidate_records(docs)
    if challenger.hex:
        matching = [c for c in candidate_records if c.hex == challenger.hex]
        if matching:
            source = max(matching, key=lambda c: (c.source_count or 0, c.score or 0))
            for field_name in ("score", "source_count", "domain_count", "sector_count", "cluster_diameter"):
                if getattr(challenger, field_name) is None:
                    setattr(challenger, field_name, getattr(source, field_name))

    prior = _load_prior_ledger(root, target)
    all_evidence = _candidate_evidence(root, target, evidence_records, CandidateInfo(), prior, cfg, metadata_index)
    evidence: list[EvidenceFinding] = []
    for item in all_evidence:
        if challenger.hex:
            distance = oklab_distance(item.local_hex, challenger.hex)
            if distance <= float(cfg["candidate_match_distance"]):
                item.distance_to_candidate = distance
                item.supports_challenger = (item.temporal_status.startswith("eligible_") and item.semantic_status == "eligible")
                evidence.append(item)
    _write_ledger(root, target, all_evidence)
    audited_ranking = _audited_clusters(all_evidence, cfg)
    audited_challenger = next((item for item in audited_ranking if item.eligible), None)

    eligible_sources = sorted({item.source_id for item in evidence if item.supports_challenger})
    excluded: dict[str, list[str]] = {}
    for item in evidence:
        if not item.supports_challenger:
            excluded.setdefault(item.source_id, []).extend(item.reasons)
    temporal_counts = dict(Counter(item.temporal_status for item in evidence))
    semantic_counts = dict(Counter(item.semantic_status for item in evidence))
    breakdown = _source_breakdown(source_records)
    challenger.evidence_count = len(evidence)
    challenger.neutral = is_neutral(challenger.hex) if challenger.hex else False

    reasons: list[str] = []
    warnings: list[str] = []
    if analyzed is not None and analyzed < int(cfg["review_min_sources"]):
        reasons.append(f"Only {analyzed} sources were analyzed; at least {cfg['review_min_sources']} are required even for internal review.")
    elif analyzed is not None and analyzed < int(cfg["public_min_sources"]):
        warnings.append(f"Coverage is {analyzed} sources; at least {cfg['public_min_sources']} are required for a public-ready day.")
    future_sources_all = sorted({item.source_name for item in all_evidence if item.temporal_status == "rejected_future"})
    future_sources = sorted({item.source_name for item in evidence if item.temporal_status == "rejected_future"})
    if future_sources:
        reasons.append("Future-dated evidence supported the provisional candidate: " + ", ".join(future_sources) + ".")
    elif future_sources_all:
        warnings.append("Future-dated observations were excluded before the audited ranking: " + ", ".join(future_sources_all) + ".")
    historical_sources = sorted({item.source_name for item in evidence if item.temporal_status.startswith("context_only_historical")})
    if historical_sources:
        warnings.append("Undated or stale historical material was moved to context-only: " + ", ".join(historical_sources) + ".")
    if challenger.hex and challenger.cluster_diameter is not None:
        muted = chroma(challenger.hex) < float(cfg["muted_chroma_threshold"])
        limit = float(cfg["muted_cluster_max_diameter"] if muted else cfg["chromatic_cluster_max_diameter"])
        if challenger.cluster_diameter > limit:
            reasons.append(
                f"The candidate cluster diameter is {challenger.cluster_diameter:.4f}; the {'muted' if muted else 'chromatic'} limit is {limit:.4f}. The cluster combines shades that are too visually broad."
            )
    if challenger.hex and audited_challenger is None:
        reasons.append("No temporally and semantically eligible chromatic cluster met the minimum source and domain breadth.")
    elif challenger.hex and audited_challenger is not None:
        audited_distance = oklab_distance(challenger.hex, audited_challenger.display_hex)
        if audited_distance > float(cfg["candidate_match_distance"]):
            reasons.append(
                f"The pipeline candidate `{challenger.hex}` does not match the integrity-audited leader `{audited_challenger.display_hex}` (OKLab distance {audited_distance:.4f}). A new public result must be recalculated rather than silently substituted."
            )

    if challenger.hex and len(eligible_sources) < int(cfg["candidate_min_sources"]):
        reasons.append(
            f"Only {len(eligible_sources)} independently current, substantial sources remain after temporal and semantic filtering; at least {cfg['candidate_min_sources']} are required."
        )
    incidental = sorted({item.source_name for item in evidence if item.semantic_status.startswith("incidental")})
    if incidental:
        warnings.append("Incidental or fragmented color support was excluded from: " + ", ".join(incidental) + ".")
    unverifiable = sorted({item.source_name for item in evidence if item.semantic_status == "unverified_region_substance"})
    if unverifiable:
        warnings.append("Connected-area substance could not be independently verified for: " + ", ".join(unverifiable) + ".")
    if baseline_days < int(cfg["baseline_days_required"]):
        warnings.append(
            f"Historical baseline is warming ({baseline_days}/{cfg['baseline_days_required']}); the displayed score is calibration breadth, not evidence of an upward trend."
        )

    tie = _audited_tie(audited_ranking, cfg) if audited_ranking else _tie_analysis(candidate_records, challenger, cfg)
    if tie.get("is_tie"):
        warnings.append("Two eligible chromatic candidates are within the configured tie threshold; review as possible co-Challengers.")

    if reasons:
        final_state = "blocked"
    elif not challenger.hex:
        final_state = "baseline_only" if (analyzed or 0) >= int(cfg["review_min_sources"]) else "blocked"
    elif baseline_days < int(cfg["baseline_days_required"]):
        final_state = "review_only"
    elif original_state in {"ready", "review_only", "baseline_only"}:
        final_state = original_state
    else:
        final_state = "review_only"

    report = IntegrityReport(
        methodology_version=str(cfg["methodology_version"]),
        target_date=target.isoformat(),
        original_state=original_state,
        final_state=final_state,
        baseline_days=baseline_days,
        coverage_analyzed=analyzed,
        coverage_active=active,
        challenger=challenger,
        reasons=reasons,
        warnings=warnings,
        temporal_counts=temporal_counts,
        semantic_counts=semantic_counts,
        source_breakdown=breakdown,
        eligible_candidate_sources=eligible_sources,
        excluded_candidate_sources={k: sorted(set(v)) for k, v in sorted(excluded.items())},
        tie=tie,
        audited_challenger=audited_challenger,
        audited_ranking=audited_ranking[:20],
        evidence=all_evidence,
        generated_at=datetime.now(tz=timezone.utc).isoformat(),
    )

    state_path.write_text(final_state + "\n", encoding="utf-8")
    report_path = archive_dir / "temporal-semantic-integrity.json"
    report_path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    _rewrite_review_summary(summary_path, report)
    _protect_assets(root, target, final_state)

    private_dir = root / ".work" / target.isoformat() / "integrity"
    private_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(report_path, private_dir / report_path.name)
    shutil.copy2(archive_dir / "temporal-ledger.json", private_dir / "temporal-ledger.json")
    (private_dir / "integrity-summary.md").write_text(_integrity_markdown(report), encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Enforce Pantone Challenger temporal and semantic integrity gates.")
    parser.add_argument("--date", required=True, help="Cultural date in YYYY-MM-DD format")
    parser.add_argument("--root", default=".", help="Repository root (default: current directory)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        target = date.fromisoformat(args.date)
    except ValueError:
        raise SystemExit("--date must use YYYY-MM-DD")
    root = Path(args.root).resolve()
    report = run_integrity(root, target)
    print(json.dumps({
        "date": report.target_date,
        "state": report.final_state,
        "eligible_candidate_sources": len(report.eligible_candidate_sources),
        "blocking_reasons": len(report.reasons),
        "report": str(root / "archive" / target.isoformat() / "temporal-semantic-integrity.json"),
    }, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
