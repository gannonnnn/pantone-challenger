from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image

from challenger.image_quality import content_hash, image_rejection_reason, perceptual_hash, region_metrics
from challenger.models import EvidenceRegion, SourceSpec


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def download_item_image(
    client: httpx.Client,
    image_url: str,
    destination: Path,
    *,
    allowed_hosts: list[str] | None = None,
    max_bytes: int = 15_000_000,
) -> tuple[bool, str]:
    host = (urlparse(image_url).hostname or "").lower()
    if allowed_hosts and not any(host == h or host.endswith(f".{h}") for h in allowed_hosts):
        return False, "unapproved_image_host"
    try:
        response = client.get(image_url, follow_redirects=True, timeout=30)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        return False, f"download_error:{type(exc).__name__}"
    content_type = response.headers.get("content-type", "").split(";")[0].lower()
    if content_type and content_type not in ALLOWED_IMAGE_TYPES:
        return False, "unsupported_content_type"
    if len(response.content) > max_bytes:
        return False, "image_too_large"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(response.content)
    try:
        with Image.open(destination) as image:
            image.verify()
    except Exception:  # noqa: BLE001
        destination.unlink(missing_ok=True)
        return False, "invalid_image"
    return True, ""


def evidence_region_from_item(
    source: SourceSpec,
    item: dict,
    path: Path,
    index: int,
) -> EvidenceRegion | None:
    rejection = image_rejection_reason(path)
    if rejection:
        return None
    with Image.open(path) as image:
        w, h = image.size
    metrics = region_metrics(path)
    return EvidenceRegion(
        source_id=source.id,
        frame_id=f"{source.id}-item-{index:03d}",
        region_id=f"{source.id}-item-{index:03d}",
        selector_hint="api_item_image",
        region_type="item_image",
        screenshot_path=str(path),
        bbox=(0, 0, w, h),
        viewport_area_ratio=1.0,
        image_area_ratio=1.0,
        text_density=0.0,
        entropy=metrics["entropy"],
        edge_density=metrics["edge_density"],
        confidence=0.90,
        eligible=True,
        page_url=str(item.get("url", "")),
        page_title=str(item.get("title", "")),
        published_at=str(item.get("published_at", "")),
        rights_mode=source.rights_mode.value,
        content_hash=content_hash(path),
        perceptual_hash=perceptual_hash(path),
    )
