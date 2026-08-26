from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image

from .models import Swatch


def srgb_to_linear(rgb: np.ndarray) -> np.ndarray:
    rgb = np.asarray(rgb, dtype=np.float64)
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(rgb: np.ndarray) -> np.ndarray:
    rgb = np.asarray(rgb, dtype=np.float64)
    return np.where(
        rgb <= 0.0031308,
        12.92 * rgb,
        1.055 * np.maximum(rgb, 0.0) ** (1.0 / 2.4) - 0.055,
    )


def rgb_to_oklab(rgb: np.ndarray) -> np.ndarray:
    linear = srgb_to_linear(np.asarray(rgb, dtype=np.float64))
    r, g, b = np.moveaxis(linear, -1, 0)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = np.cbrt(l), np.cbrt(m), np.cbrt(s)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b2 = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return np.stack([L, a, b2], axis=-1)


def oklab_to_rgb(lab: np.ndarray) -> np.ndarray:
    lab = np.asarray(lab, dtype=np.float64)
    L, a, b = np.moveaxis(lab, -1, 0)
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b2 = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return np.clip(linear_to_srgb(np.stack([r, g, b2], axis=-1)), 0.0, 1.0)


def oklab_to_oklch(lab: Iterable[float]) -> tuple[float, float, float]:
    L, a, b = (float(v) for v in lab)
    chroma = math.sqrt(a * a + b * b)
    hue = math.degrees(math.atan2(b, a)) % 360.0
    return L, chroma, hue


def hex_from_oklab(lab: Iterable[float]) -> str:
    rgb = oklab_to_rgb(np.asarray(list(lab), dtype=np.float64))
    values = np.rint(rgb * 255).astype(int).tolist()
    return "#" + "".join(f"{max(0, min(255, v)):02X}" for v in values)


def oklab_from_hex(value: str) -> tuple[float, float, float]:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Expected a six-digit hex color: {value!r}")
    rgb = np.array([int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])
    return tuple(float(v) for v in rgb_to_oklab(rgb))


def delta(lab1: Iterable[float], lab2: Iterable[float]) -> float:
    a = np.asarray(list(lab1), dtype=np.float64)
    b = np.asarray(list(lab2), dtype=np.float64)
    return float(np.linalg.norm(a - b))


def contrast_text_color(background_hex: str) -> str:
    value = background_hex.lstrip("#")
    rgb = np.array([int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])
    linear = srgb_to_linear(rgb)
    luminance = float(0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2])
    return "#111111" if luminance > 0.43 else "#F7F5F0"


def _weighted_kmeans(
    points: np.ndarray,
    weights: np.ndarray,
    k: int,
    *,
    seed: int,
    iterations: int = 18,
) -> tuple[np.ndarray, np.ndarray]:
    if len(points) == 0:
        raise ValueError("Cannot cluster an empty pixel set")
    k = max(1, min(k, len(points)))
    rng = np.random.default_rng(seed)
    probabilities = weights / np.maximum(weights.sum(), 1e-12)
    first = int(rng.choice(len(points), p=probabilities))
    centroids = [points[first]]
    closest = np.sum((points - centroids[0]) ** 2, axis=1)

    while len(centroids) < k:
        probs = closest * weights
        total = probs.sum()
        if total <= 1e-12:
            idx = int(rng.integers(0, len(points)))
        else:
            idx = int(rng.choice(len(points), p=probs / total))
        centroids.append(points[idx])
        candidate = np.sum((points - points[idx]) ** 2, axis=1)
        closest = np.minimum(closest, candidate)

    centers = np.asarray(centroids, dtype=np.float64)
    labels = np.zeros(len(points), dtype=np.int32)
    for _ in range(iterations):
        distances = np.sum((points[:, None, :] - centers[None, :, :]) ** 2, axis=2)
        new_labels = np.argmin(distances, axis=1)
        new_centers = centers.copy()
        for index in range(k):
            mask = new_labels == index
            if not np.any(mask):
                new_centers[index] = points[int(rng.choice(len(points), p=probabilities))]
                continue
            local_weights = weights[mask]
            new_centers[index] = np.average(points[mask], axis=0, weights=local_weights)
        shift = float(np.max(np.linalg.norm(new_centers - centers, axis=1)))
        centers, labels = new_centers, new_labels
        if shift < 0.0005:
            break
    return centers, labels


def _prepare_pixels(path: Path, max_pixels: int = 30000) -> tuple[np.ndarray, np.ndarray]:
    with Image.open(path) as source:
        image = source.convert("RGB")
        width, height = image.size
        left = int(width * 0.015)
        right = max(left + 1, int(width * 0.985))
        top = int(height * 0.055)
        bottom = max(top + 1, int(height * 0.98))
        image = image.crop((left, top, right, bottom))
        image.thumbnail((360, 300), Image.Resampling.LANCZOS)
        rgb = np.asarray(image, dtype=np.float64) / 255.0

    h, w, _ = rgb.shape
    yy, xx = np.mgrid[0:h, 0:w]
    xnorm = (xx + 0.5) / max(w, 1)
    ynorm = (yy + 0.5) / max(h, 1)
    center = np.exp(-(((xnorm - 0.5) / 0.58) ** 2 + ((ynorm - 0.50) / 0.62) ** 2))
    lab = rgb_to_oklab(rgb.reshape(-1, 3))
    L = lab[:, 0]
    chroma = np.linalg.norm(lab[:, 1:3], axis=1)

    # Remove only near-empty extremes. Ordinary neutrals remain eligible and
    # are handled transparently by the score's neutral penalty.
    keep = ~(((L > 0.975) | (L < 0.045)) & (chroma < 0.018))
    points = lab[keep]
    center_weights = center.reshape(-1)[keep]
    chroma_weight = 0.42 + 0.58 * np.minimum(chroma[keep] / 0.16, 1.0)
    weights = center_weights * chroma_weight

    if len(points) > max_pixels:
        digest = hashlib.sha256(path.read_bytes()).digest()
        seed = int.from_bytes(digest[:8], "big")
        rng = np.random.default_rng(seed)
        probs = weights / weights.sum()
        indices = rng.choice(len(points), size=max_pixels, replace=False, p=probs)
        points = points[indices]
        weights = weights[indices]

    return points, np.maximum(weights, 1e-8)


def merge_swatches(swatches: list[Swatch], distance_threshold: float) -> list[Swatch]:
    clusters: list[dict[str, object]] = []
    for swatch in sorted(swatches, key=lambda item: item.share, reverse=True):
        best_index = None
        best_distance = float("inf")
        for index, cluster in enumerate(clusters):
            current = delta(swatch.oklab, cluster["lab"])
            if current < best_distance:
                best_distance = current
                best_index = index
        if best_index is not None and best_distance <= distance_threshold:
            cluster = clusters[best_index]
            total = float(cluster["weight"]) + swatch.share
            cluster["lab"] = (
                np.asarray(cluster["lab"]) * float(cluster["weight"])
                + np.asarray(swatch.oklab) * swatch.share
            ) / total
            cluster["weight"] = total
        else:
            clusters.append({"lab": np.asarray(swatch.oklab), "weight": swatch.share})

    total_weight = sum(float(c["weight"]) for c in clusters) or 1.0
    merged: list[Swatch] = []
    for cluster in clusters:
        lab = tuple(float(v) for v in np.asarray(cluster["lab"]))
        share = float(cluster["weight"]) / total_weight
        merged.append(
            Swatch(
                hex=hex_from_oklab(lab),
                oklab=lab,
                oklch=oklab_to_oklch(lab),
                share=share,
            )
        )
    return sorted(merged, key=lambda item: item.share, reverse=True)


def extract_palette(
    paths: list[Path],
    *,
    clusters_per_frame: int = 8,
    max_swatches: int = 6,
    merge_distance: float = 0.045,
) -> list[Swatch]:
    all_swatches: list[Swatch] = []
    for path in paths:
        points, weights = _prepare_pixels(path)
        seed = int.from_bytes(hashlib.sha256(path.read_bytes()).digest()[:8], "big")
        centers, labels = _weighted_kmeans(points, weights, clusters_per_frame, seed=seed)
        frame_total = float(weights.sum()) or 1.0
        for index, center in enumerate(centers):
            mask = labels == index
            share = float(weights[mask].sum()) / frame_total if np.any(mask) else 0.0
            if share < 0.018:
                continue
            lab = tuple(float(v) for v in center)
            all_swatches.append(
                Swatch(
                    hex=hex_from_oklab(lab),
                    oklab=lab,
                    oklch=oklab_to_oklch(lab),
                    share=share / max(len(paths), 1),
                )
            )

    merged = merge_swatches(all_swatches, merge_distance)
    selected = merged[:max_swatches]
    total = sum(s.share for s in selected) or 1.0
    for swatch in selected:
        swatch.share = swatch.share / total
    return selected
