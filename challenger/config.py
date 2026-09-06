from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from challenger.models import (
    Domain,
    PanelType,
    RightsMode,
    ScaleClass,
    SignalStage,
    SourceSpec,
)


ROOT = Path(__file__).resolve().parent.parent


def load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    with p.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_settings(path: str | Path = "config/settings.yml") -> dict[str, Any]:
    settings = load_yaml(path)
    settings.setdefault("methodology_version", "1.5.1")
    return settings


def load_sources(path: str | Path = "config/sources.yml") -> tuple[str, list[SourceSpec]]:
    data = load_yaml(path)
    version = str(data.get("registry_version", "unknown"))
    specs: list[SourceSpec] = []
    for raw in data.get("sources", []):
        try:
            spec = SourceSpec(
                id=str(raw["id"]),
                name=str(raw["name"]),
                enabled=bool(raw.get("enabled", True)),
                adapter=str(raw.get("adapter", "webpage")),
                domain=Domain(raw["domain"]),
                sector=str(raw.get("sector", raw["domain"])),
                signal_stage=SignalStage(raw["signal_stage"]),
                scale_class=ScaleClass(raw["scale_class"]),
                panel_type=PanelType(raw["panel_type"]),
                event_type=str(raw.get("event_type", "unspecified")),
                geography=str(raw.get("geography", "global")),
                rights_mode=RightsMode(raw.get("rights_mode", "analyze_only")),
                url=str(raw.get("url", "")),
                api_url=str(raw.get("api_url", "")),
                platform=str(raw.get("platform", raw.get("id", ""))),
                creator_id=str(raw.get("creator_id", raw.get("id", ""))),
                weight=float(raw.get("weight", 1.0)),
                max_items=int(raw.get("max_items", 8)),
                allowed_hosts=list(raw.get("allowed_hosts", [])),
                fallback_urls=list(raw.get("fallback_urls", [])),
                include_selectors=list(raw.get("include_selectors", [])),
                exclude_selectors=list(raw.get("exclude_selectors", [])),
                known_house_colors=list(raw.get("known_house_colors", [])),
                brand_mark_path=str(raw.get("brand_mark_path", "")),
                brand_mark_status=str(raw.get("brand_mark_status", "none")),
                query=str(raw.get("query", "")),
                token_env=str(raw.get("token_env", "")),
                api_key_env=str(raw.get("api_key_env", "")),
                options=dict(raw.get("options", {})),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f"Invalid source registry entry {raw.get('id', '<unknown>')}: {exc}") from exc
        specs.append(spec)
    validate_sources(specs)
    return version, specs


def validate_sources(specs: list[SourceSpec]) -> None:
    ids = [s.id for s in specs]
    duplicates = sorted({x for x in ids if ids.count(x) > 1})
    if duplicates:
        raise ValueError(f"Duplicate source IDs: {', '.join(duplicates)}")
    for s in specs:
        if s.adapter in {"webpage", "rss"} and not s.url:
            raise ValueError(f"{s.id}: adapter {s.adapter!r} requires url")
        if s.allowed_hosts and s.url:
            from urllib.parse import urlparse

            host = (urlparse(s.url).hostname or "").lower()
            if host and not any(host == h or host.endswith(f".{h}") for h in s.allowed_hosts):
                raise ValueError(f"{s.id}: URL host {host!r} is outside allowed_hosts")
        if s.brand_mark_status == "approved" and not s.brand_mark_path:
            raise ValueError(f"{s.id}: approved brand mark requires brand_mark_path")


def source_is_configured(spec: SourceSpec) -> bool:
    if spec.token_env and not os.getenv(spec.token_env):
        return False
    if spec.api_key_env and not os.getenv(spec.api_key_env):
        return False
    return True
