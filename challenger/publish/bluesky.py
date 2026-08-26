from __future__ import annotations

import json
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from PIL import Image

from .common import PublishError, load_publish_context, require_approval


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise PublishError(f"Required environment variable is missing: {name}")
    return value


def _post_json(session: requests.Session, url: str, payload: dict[str, Any], headers=None):
    response = session.post(url, json=payload, headers=headers or {}, timeout=45)
    if not response.ok:
        raise PublishError(f"Bluesky request failed ({response.status_code}): {response.text[:1000]}")
    return response.json()


def _short_caption(result: dict[str, Any]) -> str:
    winner = result["winner"]
    text = (
        f"Yesterday’s Challenger: {result['winner_name']} ({winner['hex']}). "
        f"{winner['source_count']} independent sources across "
        f"{winner['sector_count']} commercial sectors. "
        "The algorithm chooses the color—even when it is ugly."
    )
    return text[:300]


def publish_bluesky(
    archive_root: Path,
    requested_date: str,
    *,
    approved: bool,
) -> Path:
    require_approval(approved)
    date_value, day_dir, result, package = load_publish_context(
        archive_root, requested_date
    )
    handle = _required("BLUESKY_HANDLE")
    password = _required("BLUESKY_APP_PASSWORD")
    service = os.getenv("BLUESKY_SERVICE", "https://bsky.social").rstrip("/")
    session = requests.Session()
    auth = _post_json(
        session,
        f"{service}/xrpc/com.atproto.server.createSession",
        {"identifier": handle, "password": password},
    )
    token = auth["accessJwt"]
    did = auth["did"]
    image_path = day_dir / package["feed_asset"]
    mime = mimetypes.guess_type(image_path.name)[0] or "image/png"
    upload = session.post(
        f"{service}/xrpc/com.atproto.repo.uploadBlob",
        data=image_path.read_bytes(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": mime},
        timeout=60,
    )
    if not upload.ok:
        raise PublishError(f"Bluesky image upload failed: {upload.text[:1000]}")
    blob = upload.json()["blob"]
    with Image.open(image_path) as image:
        width, height = image.size
    record = {
        "$type": "app.bsky.feed.post",
        "text": _short_caption(result),
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "embed": {
            "$type": "app.bsky.embed.images",
            "images": [
                {
                    "alt": (
                        f"Pantone Challenger daily color card for {date_value}: "
                        f"{result['winner_name']} {result['winner']['hex']}."
                    ),
                    "image": blob,
                    "aspectRatio": {"width": width, "height": height},
                }
            ],
        },
    }
    created = _post_json(
        session,
        f"{service}/xrpc/com.atproto.repo.createRecord",
        {
            "repo": did,
            "collection": "app.bsky.feed.post",
            "record": record,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    output = day_dir / "published.json"
    output.write_text(
        json.dumps(
            {"platform": "bluesky", "date": date_value, "record": created},
            indent=2,
        ),
        encoding="utf-8",
    )
    return output
