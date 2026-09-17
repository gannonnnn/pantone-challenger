"""Keep publishers, creators, items and campaigns distinct."""
from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def canonical_url(value: str) -> str:
    parsed = urlsplit(value)
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path,
                      urlencode(sorted(query)), ""))


def observation_identity(source, region, *, item_adapter: bool) -> dict:
    meta = region.metadata or {}
    item_url = canonical_url(region.page_url)
    item_id = str(meta.get("item_id") or item_url or region.region_id)
    explicit_creator = str(meta.get("creator_id") or "").strip()
    verified = bool(explicit_creator and meta.get("identity_verified") is True)
    if item_adapter:
        # Unknown creators are grouped at the publisher, never split by item URL.
        creator = f"{source.platform or source.id}:{explicit_creator}" if verified else ""
        actor = creator or f"publisher:{source.id}"
        name = str(meta.get("creator_name") or source.name) if verified else source.name
    else:
        creator = source.creator_id or source.id
        actor, name, verified = creator, source.name, True
    return {
        "actor_id": actor, "actor_name": name, "creator_id": creator,
        "publisher_id": source.id, "registry_source_id": source.id,
        "item_id": item_id, "campaign_id": str(meta.get("campaign_id") or ""),
        "identity_verified": verified,
        "identity_basis": "source_metadata" if verified else "conservative_publisher_group",
        "item_key": hashlib.sha256(item_id.encode()).hexdigest()[:20],
    }
