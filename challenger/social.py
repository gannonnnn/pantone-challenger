from __future__ import annotations

import json
import os
from pathlib import Path

import httpx


class SocialPublishingError(RuntimeError):
    pass


def publish_approved_day(
    date: str,
    platform: str,
    archive_dir: str | Path = "archive",
    public_base_url: str | None = None,
    dry_run: bool = True,
) -> dict:
    day_dir = Path(archive_dir) / date
    result = json.loads((day_dir / "result.json").read_text(encoding="utf-8"))
    if result.get("state") != "ready":
        raise SocialPublishingError("Only approved ready results may be published.")
    image_path = day_dir / "feed-post.png"
    caption = (day_dir / "caption.txt").read_text(encoding="utf-8").strip()
    if dry_run:
        return {"platform": platform, "date": date, "image": str(image_path), "caption": caption, "dry_run": True}
    if platform == "bluesky":
        return _publish_bluesky(image_path, caption)
    if platform == "instagram":
        if not public_base_url:
            raise SocialPublishingError("Instagram publishing requires PUBLIC_BASE_URL.")
        return _publish_instagram(date, caption, public_base_url)
    raise SocialPublishingError(f"Unsupported platform: {platform}")


def _publish_bluesky(image_path: Path, caption: str) -> dict:
    handle = os.environ.get("BLUESKY_HANDLE")
    password = os.environ.get("BLUESKY_APP_PASSWORD")
    if not handle or not password:
        raise SocialPublishingError("BLUESKY_HANDLE and BLUESKY_APP_PASSWORD are required.")
    client = httpx.Client(timeout=30)
    session = client.post(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        json={"identifier": handle, "password": password},
    )
    session.raise_for_status()
    auth = session.json()
    token = auth["accessJwt"]
    mime = "image/png"
    blob = client.post(
        "https://bsky.social/xrpc/com.atproto.repo.uploadBlob",
        headers={"Authorization": f"Bearer {token}", "Content-Type": mime},
        content=image_path.read_bytes(),
    )
    blob.raise_for_status()
    record = {
        "$type": "app.bsky.feed.post",
        "text": caption[:300],
        "createdAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat().replace("+00:00", "Z"),
        "embed": {
            "$type": "app.bsky.embed.images",
            "images": [{"alt": caption[:1000], "image": blob.json()["blob"]}],
        },
    }
    created = client.post(
        "https://bsky.social/xrpc/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {token}"},
        json={"repo": auth["did"], "collection": "app.bsky.feed.post", "record": record},
    )
    created.raise_for_status()
    return created.json()


def _publish_instagram(date: str, caption: str, public_base_url: str) -> dict:
    user_id = os.environ.get("INSTAGRAM_USER_ID")
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    graph_version = os.environ.get("META_GRAPH_VERSION")
    if not user_id or not token:
        raise SocialPublishingError("INSTAGRAM_USER_ID and INSTAGRAM_ACCESS_TOKEN are required.")
    if not graph_version:
        raise SocialPublishingError("META_GRAPH_VERSION must be set to a currently supported official Graph API version.")
    base = f"https://graph.facebook.com/{graph_version}"
    image_url = f"{public_base_url.rstrip('/')}/days/{date}/feed-post.png"
    client = httpx.Client(timeout=30)
    container = client.post(
        f"{base}/{user_id}/media",
        data={"image_url": image_url, "caption": caption, "access_token": token},
    )
    container.raise_for_status()
    creation_id = container.json()["id"]
    published = client.post(
        f"{base}/{user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": token},
    )
    published.raise_for_status()
    return published.json()
