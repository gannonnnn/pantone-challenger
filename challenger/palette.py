from __future__ import annotations

from collections import deque
from dataclasses import replace
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from challenger.color import (
    distance,
    hex_to_oklab,
    is_neutral,
    oklab_to_oklch,
    rgb_array_to_oklab,
    rgb_to_hex,
)
from challenger.models import Swatch


def _prepare_image(
    path: str | Path,
    *,
    max_side: int = 420,
    max_pixels: int = 30_000,
) -> tuple[Image.Image, np.ndarray]:
    """Load a source image without inventing colors in transparent padding.

    Transparent pixels are excluded from palette clustering.  They are painted
    white only in the returned RGB image so downstream PIL operations have a
    conventional canvas; the accompanying boolean mask remains authoritative.
    """

    rgba = Image.open(path).convert("RGBA")
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    if bbox:
        rgba = rgba.crop(bbox)
    if rgba.width < 1 or rgba.height < 1:
        raise ValueError(f"Image contains no visible pixels: {path}")

    scale = min(
        1.0,
        max_side / max(rgba.width, rgba.height),
        (max_pixels / max(1, rgba.width * rgba.height)) ** 0.5,
    )
    if scale < 1.0:
        size = (max(1, int(round(rgba.width * scale))), max(1, int(round(rgba.height * scale))))
        rgba = rgba.resize(size, Image.Resampling.LANCZOS)

    arr = np.asarray(rgba, dtype=np.uint8)
    valid = arr[..., 3] >= 32
    rgb = arr[..., :3].copy()
    rgb[~valid] = (255, 255, 255)
    return Image.fromarray(rgb, mode="RGB"), valid


def _visible_source_pixels(path: str | Path, max_pixels: int = 80_000) -> tuple[np.ndarray, np.ndarray]:
    """Return deterministic visible pixels sampled from the original source file."""

    rgba = Image.open(path).convert("RGBA")
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    if bbox:
        rgba = rgba.crop(bbox)
    arr = np.asarray(rgba, dtype=np.uint8)
    visible = arr[..., 3] >= 32
    pixels = arr[..., :3][visible]
    if len(pixels) > max_pixels:
        step = max(1, len(pixels) // max_pixels)
        pixels = pixels[::step][:max_pixels]
    return pixels, rgb_array_to_oklab(pixels) if len(pixels) else np.empty((0, 3))


def _kmeans(
    points: np.ndarray,
    k: int,
    *,
    iterations: int = 18,
) -> tuple[np.ndarray, np.ndarray]:
    """Deterministic k-means in OKLab.

    Farthest-point initialization covers chromatic minorities more reliably
    than luminance quantiles and avoids random run-to-run drift.
    """

    if len(points) == 0:
        return np.empty((0, 3)), np.empty((0,), dtype=int)
    k = max(1, min(k, len(points)))
    mean = points.mean(axis=0)
    first = int(np.argmin(((points - mean) ** 2).sum(axis=1)))
    centers = [points[first].astype(float)]
    min_d = ((points - centers[0]) ** 2).sum(axis=1)
    for _ in range(1, k):
        index = int(np.argmax(min_d))
        centers.append(points[index].astype(float))
        min_d = np.minimum(min_d, ((points - centers[-1]) ** 2).sum(axis=1))
    centers_arr = np.asarray(centers, dtype=float)
    labels = np.full(len(points), -1, dtype=np.int16)

    for _ in range(iterations):
        d = ((points[:, None, :] - centers_arr[None, :, :]) ** 2).sum(axis=2)
        new_labels = d.argmin(axis=1).astype(np.int16)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for i in range(k):
            member = points[labels == i]
            if len(member):
                centers_arr[i] = member.mean(axis=0)
    return centers_arr, labels


def _largest_component_share(mask: np.ndarray, denominator: int) -> float:
    if not mask.any() or denominator <= 0:
        return 0.0

    # Connectivity is measured on a small occupancy grid.  This preserves the
    # distinction between one substantial color field and many scattered UI
    # pixels without running a Python flood-fill over tens of thousands of
    # source pixels for every cluster.
    h, w = mask.shape
    scale = min(1.0, 88 / max(h, w))
    if scale < 1.0:
        size = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
        reduced = np.asarray(
            Image.fromarray((mask * 255).astype(np.uint8)).resize(size, Image.Resampling.BOX),
            dtype=np.uint8,
        ) >= 64
    else:
        reduced = mask
    rh, rw = reduced.shape
    seen = np.zeros_like(reduced, dtype=bool)
    largest = 0
    for y, x in zip(*np.nonzero(reduced), strict=False):
        if seen[y, x]:
            continue
        queue: deque[tuple[int, int]] = deque([(int(y), int(x))])
        seen[y, x] = True
        size_count = 0
        while queue:
            cy, cx = queue.popleft()
            size_count += 1
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if (
                    0 <= ny < rh
                    and 0 <= nx < rw
                    and reduced[ny, nx]
                    and not seen[ny, nx]
                ):
                    seen[ny, nx] = True
                    queue.append((ny, nx))
        largest = max(largest, size_count)
    return largest / max(1, rh * rw)


def _spatial_coverage(mask: np.ndarray, valid: np.ndarray, cells: int = 4) -> float:
    h, w = mask.shape
    occupied = 0
    possible = 0
    for gy in range(cells):
        y1, y2 = round(gy * h / cells), round((gy + 1) * h / cells)
        for gx in range(cells):
            x1, x2 = round(gx * w / cells), round((gx + 1) * w / cells)
            cell_valid = valid[y1:y2, x1:x2]
            denominator = int(cell_valid.sum())
            if denominator == 0:
                continue
            possible += 1
            present = int((mask[y1:y2, x1:x2] & cell_valid).sum())
            if present >= max(3, int(denominator * 0.02)):
                occupied += 1
    return occupied / possible if possible else 0.0


def _border_share(mask: np.ndarray, valid: np.ndarray) -> float:
    border = np.zeros_like(valid, dtype=bool)
    border[0, :] = True
    border[-1, :] = True
    border[:, 0] = True
    border[:, -1] = True
    valid_border = border & valid
    denominator = int(valid_border.sum())
    return float((mask & valid_border).sum() / denominator) if denominator else 0.0


def extract_palette(
    path: str | Path,
    colors: int = 7,
    neutral_chroma: float = 0.035,
) -> list[Swatch]:
    """Extract an auditable palette whose representative HEX values were observed.

    Clustering and distances use OKLab, but every returned HEX is an actual
    sampled source pixel nearest its cluster center.  This prevents the system
    from publishing an averaged color that never appeared in the creative.
    """

    image, valid = _prepare_image(path)
    source_rgb, source_labs = _visible_source_pixels(path)
    rgb = np.asarray(image, dtype=np.uint8)
    valid_rgb = rgb[valid]
    if len(valid_rgb) == 0:
        return []
    points = rgb_array_to_oklab(valid_rgb)
    centers, labels = _kmeans(points, colors)
    if len(centers) == 0:
        return []

    label_map = np.full(valid.shape, -1, dtype=np.int16)
    label_map[valid] = labels
    gray = np.asarray(image.convert("L"), dtype=float) / 255.0
    edges = np.asarray(image.convert("L").filter(ImageFilter.FIND_EDGES), dtype=float) / 255.0
    # Suppress artificial outer-border response produced by FIND_EDGES.
    if edges.size:
        edges[[0, -1], :] = 0
        edges[:, [0, -1]] = 0
    edge_total = float(edges[valid].sum()) or 1.0
    denominator = int(valid.sum())

    records: list[dict] = []
    for i, center in enumerate(centers):
        member_indices = np.flatnonzero(labels == i)
        if len(member_indices) == 0:
            continue
        if len(source_labs):
            source_index = int(np.argmin(((source_labs - center) ** 2).sum(axis=1)))
            representative_rgb = source_rgb[source_index]
            lab = tuple(float(x) for x in source_labs[source_index])
        else:
            member_labs = points[member_indices]
            nearest = member_indices[int(np.argmin(((member_labs - center) ** 2).sum(axis=1)))]
            representative_rgb = valid_rgb[nearest]
            lab = tuple(float(x) for x in points[nearest])
        hex_value = rgb_to_hex(representative_rgb)
        lch = oklab_to_oklch(lab)
        mask = label_map == i
        share = len(member_indices) / denominator
        edge_share = float(edges[mask].sum() / edge_total)
        component_share = _largest_component_share(mask, denominator)
        coverage = _spatial_coverage(mask, valid)
        border_share = _border_share(mask, valid)
        neutral = is_neutral(lch, neutral_chroma)
        structural = bool(
            neutral
            and (
                (share >= 0.30 and border_share >= 0.70)
                or (
                    share >= 0.18
                    and border_share >= 0.42
                    and edge_share <= max(0.08, share * 0.72)
                )
            )
        )
        adjusted_share = share * (0.12 if structural else 1.0)
        raw_salience = (
            0.40 * adjusted_share
            + 0.25 * edge_share
            + 0.20 * component_share
            + 0.15 * coverage
        )
        records.append(
            {
                "hex": hex_value,
                "oklab": lab,
                "oklch": lch,
                "share": share,
                "raw_salience": raw_salience,
                "is_neutral": neutral,
                "adjusted_share": adjusted_share,
                "largest_component_share": component_share,
                "spatial_coverage": coverage,
                "border_share": border_share,
                "observed_pixel": True,
                "structural_background": structural,
                "sampled_pixels": len(member_indices),
            }
        )

    salience_total = sum(r["raw_salience"] for r in records) or 1.0
    swatches = [
        Swatch(
            hex=r["hex"],
            oklab=r["oklab"],
            oklch=r["oklch"],
            share=r["share"],
            salience=r["raw_salience"] / salience_total,
            is_neutral=r["is_neutral"],
            adjusted_share=r["adjusted_share"],
            largest_component_share=r["largest_component_share"],
            spatial_coverage=r["spatial_coverage"],
            border_share=r["border_share"],
            observed_pixel=r["observed_pixel"],
            structural_background=r["structural_background"],
            sampled_pixels=r["sampled_pixels"],
        )
        for r in records
    ]
    swatches.sort(key=_swatch_rank, reverse=True)
    return _merge_nearby(swatches)


def _swatch_rank(swatch: Swatch) -> float:
    share = swatch.adjusted_share if swatch.adjusted_share is not None else swatch.share
    return (
        0.50 * share
        + 0.25 * swatch.salience
        + 0.15 * swatch.largest_component_share
        + 0.10 * swatch.spatial_coverage
    )


def _merge_nearby(swatches: list[Swatch], threshold: float = 0.022) -> list[Swatch]:
    """Merge only compact same-image clusters and retain an observed medoid HEX."""

    groups: list[list[Swatch]] = []
    for swatch in swatches:
        possible = [
            group
            for group in groups
            if all(distance(member.oklab, swatch.oklab) <= threshold for member in group)
        ]
        if possible:
            target = min(
                possible,
                key=lambda group: sum(distance(member.oklab, swatch.oklab) for member in group),
            )
            target.append(swatch)
        else:
            groups.append([swatch])

    merged: list[Swatch] = []
    for group in groups:
        if len(group) == 1:
            merged.append(group[0])
            continue
        weights = np.asarray([max(1, s.sampled_pixels) for s in group], dtype=float)
        labs = np.asarray([s.oklab for s in group], dtype=float)
        centroid = np.average(labs, axis=0, weights=weights)
        medoid_index = int(
            np.argmin(
                [
                    sum(distance(candidate.oklab, other.oklab) * weight for other, weight in zip(group, weights, strict=False))
                    for candidate in group
                ]
            )
        )
        representative = group[medoid_index]
        total_share = sum(s.share for s in group)
        adjusted = sum((s.adjusted_share if s.adjusted_share is not None else s.share) for s in group)
        merged.append(
            replace(
                representative,
                share=total_share,
                adjusted_share=adjusted,
                salience=sum(s.salience for s in group),
                largest_component_share=max(s.largest_component_share for s in group),
                spatial_coverage=max(s.spatial_coverage for s in group),
                border_share=sum(s.border_share * s.share for s in group) / max(total_share, 1e-9),
                observed_pixel=True,
                structural_background=(
                    sum(s.sampled_pixels for s in group if s.structural_background)
                    / max(1, sum(s.sampled_pixels for s in group))
                    >= 0.70
                ),
                sampled_pixels=sum(s.sampled_pixels for s in group),
                # Keep actual observed representative coordinates; centroid is
                # intentionally not converted into a fictional HEX value.
                oklab=representative.oklab,
                oklch=representative.oklch,
            )
        )
    merged.sort(key=_swatch_rank, reverse=True)
    return merged


def swatch_is_candidate_eligible(swatch: Swatch, settings: dict) -> bool:
    clustering = settings.get("clustering", {})
    min_local_share = float(clustering.get("min_local_share", 0.055))
    min_salience = float(clustering.get("min_salience", 0.025))
    min_component = float(clustering.get("min_component_share", 0.006))
    min_spatial = float(clustering.get("min_spatial_coverage", 0.125))
    share = swatch.adjusted_share if swatch.adjusted_share is not None else swatch.share
    if swatch.structural_background:
        return False
    if share < min_local_share and swatch.salience < min_salience:
        return False
    # Reject colors made only of scattered interface/text pixels. A broad
    # patterned color may pass through spatial coverage even if no one connected
    # component is large.
    return swatch.largest_component_share >= min_component or swatch.spatial_coverage >= min_spatial


def color_match_mask(
    path: str | Path,
    target_lab: tuple[float, float, float],
    *,
    threshold: float = 0.035,
    max_side: int = 520,
) -> tuple[Image.Image, np.ndarray]:
    """Return a resized RGB image and a mask proving where a color was observed."""

    image, valid = _prepare_image(path, max_side=max_side, max_pixels=max_side * max_side)
    rgb = np.asarray(image, dtype=np.uint8)
    labs = rgb_array_to_oklab(rgb)
    target = np.asarray(target_lab, dtype=float)
    mask = (np.linalg.norm(labs - target, axis=-1) <= threshold) & valid
    return image, mask


def color_match_overlay(
    path: str | Path,
    target_lab: tuple[float, float, float],
    *,
    threshold: float = 0.035,
    max_side: int = 520,
) -> Image.Image:
    """Create a private proof image: matched pixels stay colored, others gray."""

    image, mask = color_match_mask(path, target_lab, threshold=threshold, max_side=max_side)
    rgb = np.asarray(image, dtype=np.uint8)
    gray = np.asarray(image.convert("L"), dtype=np.uint8)
    muted = np.stack((gray, gray, gray), axis=-1)
    muted = (muted.astype(float) * 0.42 + 220 * 0.58).astype(np.uint8)
    output = np.where(mask[..., None], rgb, muted)
    return Image.fromarray(output, mode="RGB")


def _oklab_to_rgb_approx(lab: tuple[float, float, float]) -> tuple[int, int, int]:
    """Inverse OKLab conversion retained for compatibility with historical data."""

    l, a, b = lab
    l_ = l + 0.3963377774 * a + 0.2158037573 * b
    m_ = l - 0.1055613458 * a - 0.0638541728 * b
    s_ = l - 0.0894841775 * a - 1.2914855480 * b
    l3, m3, s3 = l_**3, m_**3, s_**3
    r = 4.0767416621 * l3 - 3.3077115913 * m3 + 0.2309699292 * s3
    g = -1.2684380046 * l3 + 2.6097574011 * m3 - 0.3413193965 * s3
    bl = -0.0041960863 * l3 - 0.7034186147 * m3 + 1.7076147010 * s3

    def gamma(x: float) -> float:
        x = max(0.0, min(1.0, x))
        return 12.92 * x if x <= 0.0031308 else 1.055 * (x ** (1 / 2.4)) - 0.055

    return tuple(int(round(gamma(x) * 255)) for x in (r, g, bl))
