from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


OVERLAY_WORDS = {
    "cookie",
    "privacy preferences",
    "privacy notice",
    "accept all",
    "reject all",
    "manage consent",
    "verification",
    "verify you are human",
    "press and hold",
    "access denied",
    "enable javascript",
    "sign in",
    "log in",
    "subscribe",
    "newsletter",
    "special offer",
    "limited time offer",
    "choose your location",
    "select your region",
}


def content_hash(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def perceptual_hash(path: str | Path, size: int = 16) -> str:
    image = Image.open(path).convert("L").resize((size, size), Image.Resampling.LANCZOS)
    arr = np.asarray(image, dtype=float)
    # Difference hash, robust to resizing and minor compression.
    diff = arr[:, 1:] > arr[:, :-1]
    bits = "".join("1" if x else "0" for x in diff.flatten())
    return f"{int(bits, 2):0{math.ceil(len(bits)/4)}x}"


def hash_distance(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()


def region_metrics(path: str | Path) -> dict[str, float]:
    image = Image.open(path).convert("RGB")
    image.thumbnail((600, 600), Image.Resampling.LANCZOS)
    arr = np.asarray(image, dtype=float) / 255.0
    gray = np.asarray(image.convert("L"), dtype=float) / 255.0
    hist = np.histogram(gray, bins=64, range=(0, 1), density=False)[0].astype(float)
    probs = hist / max(1.0, hist.sum())
    probs = probs[probs > 0]
    entropy = float(-(probs * np.log2(probs)).sum() / 6.0)
    edges = np.asarray(image.convert("L").filter(ImageFilter.FIND_EDGES), dtype=float) / 255.0
    edge_density = float((edges > 0.12).mean())
    channel_std = float(arr.std(axis=(0, 1)).mean())
    near_white = float((gray > 0.97).mean())
    near_black = float((gray < 0.03).mean())
    return {
        "entropy": entropy,
        "edge_density": edge_density,
        "channel_std": channel_std,
        "near_white_share": near_white,
        "near_black_share": near_black,
    }


def image_rejection_reason(path: str | Path, *, min_width: int = 280, min_height: int = 180) -> str:
    image = Image.open(path)
    w, h = image.size
    if w < min_width or h < min_height:
        return "region_too_small"
    if h / max(w, 1) < 0.10 or w / max(h, 1) < 0.10:
        return "loading_strip_or_sliver"
    metrics = region_metrics(path)
    if metrics["near_white_share"] > 0.985 or metrics["near_black_share"] > 0.985:
        return "nearly_blank_region"
    if metrics["entropy"] < 0.06 and metrics["edge_density"] < 0.015:
        return "low_information_placeholder"
    if metrics["channel_std"] < 0.008 and metrics["edge_density"] < 0.01:
        return "flat_placeholder"
    return ""


def text_looks_like_overlay(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    if not normalized:
        return False
    matches = sum(1 for word in OVERLAY_WORDS if word in normalized)
    return matches >= 1 and len(normalized) < 1800


def intersection_over_union(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    union = aw * ah + bw * bh - inter
    return inter / union if union else 0.0


def dedupe_regions(regions: list[dict], *, iou_threshold: float = 0.82, phash_threshold: int = 8) -> list[dict]:
    accepted: list[dict] = []
    for candidate in sorted(regions, key=lambda r: (r.get("confidence", 0), r.get("area", 0)), reverse=True):
        duplicate = False
        for existing in accepted:
            if intersection_over_union(tuple(candidate["bbox"]), tuple(existing["bbox"])) >= iou_threshold:
                duplicate = True
                break
            if candidate.get("perceptual_hash") and existing.get("perceptual_hash"):
                if hash_distance(candidate["perceptual_hash"], existing["perceptual_hash"]) <= phash_threshold:
                    duplicate = True
                    break
        if not duplicate:
            accepted.append(candidate)
    return accepted


def trim_and_fit_logo(
    source: str | Path,
    box: tuple[int, int],
    *,
    max_upscale: float = 2.0,
    padding_ratio: float = 0.16,
    min_source_side: int = 48,
) -> Image.Image | None:
    """Return a contained logo image or None when text fallback is safer.

    This intentionally rejects favicon-size rasters and never uses cover/crop behavior.
    """
    image = Image.open(source).convert("RGBA")
    if min(image.size) < min_source_side:
        return None
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox:
        image = image.crop(bbox)
    if min(image.size) < min_source_side:
        return None
    box_w, box_h = box
    available = (max(1, int(box_w * (1 - 2 * padding_ratio))), max(1, int(box_h * (1 - 2 * padding_ratio))))
    scale = min(available[0] / image.width, available[1] / image.height, max_upscale)
    target = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
    image = image.resize(target, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", box, (0, 0, 0, 0))
    x = (box_w - image.width) // 2
    y = (box_h - image.height) // 2
    canvas.alpha_composite(image, (x, y))
    return canvas


def swatch_center_matches(path: str | Path, expected_hex: str, xy: tuple[int, int], tolerance: int = 1) -> bool:
    from challenger.color import hex_to_rgb

    pixel = Image.open(path).convert("RGB").getpixel(xy)
    expected = hex_to_rgb(expected_hex)
    return all(abs(int(pixel[i]) - int(expected[i])) <= tolerance for i in range(3))
