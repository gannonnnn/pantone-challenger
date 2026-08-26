from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests

from .common import PublishError, load_publish_context, require_approval


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise PublishError(f"Required environment variable is missing: {name}")
    return value


def _request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    timeout: int = 45,
    **kwargs: Any,
) -> dict[str, Any]:
    response = session.request(method, url, timeout=timeout, **kwargs)
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text[:1000]}
    if not response.ok:
        raise PublishError(
            f"Meta API request failed ({response.status_code}): "
            f"{json.dumps(payload, ensure_ascii=False)}"
        )
    return payload


def _wait_for_container(
    session: requests.Session,
    base: str,
    creation_id: str,
    token: str,
) -> None:
    for _ in range(24):
        payload = _request_json(
            session,
            "GET",
            f"{base}/{creation_id}",
            params={"fields": "status_code,status", "access_token": token},
        )
        status = payload.get("status_code")
        if status == "FINISHED":
            return
        if status in {"ERROR", "EXPIRED"}:
            raise PublishError(f"Instagram media container failed: {payload}")
        time.sleep(5)
    raise PublishError("Instagram media container did not finish within two minutes")


def _public_asset_url(base_url: str, date_value: str, filename: str) -> str:
    return f"{base_url.rstrip('/')}/assets/{date_value}/{filename}"


def _verify_public_asset(session: requests.Session, url: str) -> None:
    last_status = 0
    last_content_type = ""
    for _ in range(12):
        response = session.get(url, timeout=30)
        last_status = response.status_code
        last_content_type = response.headers.get("content-type", "")
        if response.ok and last_content_type.startswith("image/"):
            return
        time.sleep(10)
    raise PublishError(
        f"The public social asset is not reachable as an image after two minutes: "
        f"{url} (HTTP {last_status}, {last_content_type or 'unknown content type'})"
    )


def _create_and_publish(
    session: requests.Session,
    *,
    base: str,
    user_id: str,
    token: str,
    image_url: str,
    caption: str | None = None,
    story: bool = False,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "image_url": image_url,
        "access_token": token,
    }
    if caption and not story:
        params["caption"] = caption
    if story:
        params["media_type"] = "STORIES"
    creation = _request_json(
        session,
        "POST",
        f"{base}/{user_id}/media",
        data=params,
    )
    creation_id = creation.get("id")
    if not creation_id:
        raise PublishError(f"Meta did not return a media container id: {creation}")
    _wait_for_container(session, base, creation_id, token)
    published = _request_json(
        session,
        "POST",
        f"{base}/{user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": token},
    )
    return {"creation_id": creation_id, "media_id": published.get("id")}


def publish_instagram(
    archive_root: Path,
    requested_date: str,
    *,
    approved: bool,
    include_stories: bool = False,
) -> Path:
    require_approval(approved)
    date_value, day_dir, result, package = load_publish_context(
        archive_root, requested_date
    )
    token = _required("INSTAGRAM_ACCESS_TOKEN")
    user_id = _required("INSTAGRAM_USER_ID")
    public_base_url = _required("PUBLIC_BASE_URL")
    graph_version = _required("META_GRAPH_VERSION")
    base = f"https://graph.facebook.com/{graph_version}"
    session = requests.Session()

    feed_name = package.get("feed_asset")
    if not feed_name:
        raise PublishError("No feed asset is present in the publishing package")
    feed_url = _public_asset_url(public_base_url, date_value, feed_name)
    _verify_public_asset(session, feed_url)
    caption = (day_dir / "caption.txt").read_text(encoding="utf-8")
    records: dict[str, Any] = {
        "platform": "instagram",
        "date": date_value,
        "feed": _create_and_publish(
            session,
            base=base,
            user_id=user_id,
            token=token,
            image_url=feed_url,
            caption=caption,
        ),
        "stories": [],
    }

    if include_stories:
        for filename in package.get("story_assets", []):
            story_url = _public_asset_url(public_base_url, date_value, filename)
            _verify_public_asset(session, story_url)
            records["stories"].append(
                {
                    "filename": filename,
                    **_create_and_publish(
                        session,
                        base=base,
                        user_id=user_id,
                        token=token,
                        image_url=story_url,
                        story=True,
                    ),
                }
            )

    output = day_dir / "published.json"
    output.write_text(json.dumps(records, indent=2), encoding="utf-8")
    return output
