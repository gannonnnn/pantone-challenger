from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from .models import CaptureRecord


def _dhash(path: Path, size: int = 12) -> int:
    with Image.open(path) as image:
        gray = image.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
        pixels = np.asarray(gray, dtype=np.int16)
    differences = pixels[:, 1:] > pixels[:, :-1]
    value = 0
    for bit in differences.reshape(-1):
        value = (value << 1) | int(bit)
    return value


def _mean_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        rgb.thumbnail((80, 80), Image.Resampling.BILINEAR)
        array = np.asarray(rgb, dtype=np.float64) / 255.0
    return np.mean(array.reshape(-1, 3), axis=0)


def _hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def deduplicate_records(records: list[CaptureRecord]) -> list[CaptureRecord]:
    """
    Remove exact duplicates and only the most conservative near duplicates.

    Browser challenge pages and syndicated templates can otherwise cast several
    votes. The near-duplicate test requires an almost identical dHash, similar
    file size, and nearly identical mean RGB. It intentionally favors false
    negatives over suppressing independent marketing pages.
    """
    accepted: list[tuple[CaptureRecord, int, np.ndarray, int]] = []
    seen_sha: dict[str, str] = {}
    for record in records:
        if not record.success or not record.frames:
            continue
        first = record.frames[0]
        duplicate_of = seen_sha.get(first.sha256)
        if duplicate_of:
            record.success = False
            record.error = f"Exact duplicate of {duplicate_of}"
            continue

        path = Path(first.path)
        try:
            hash_value = _dhash(path)
            mean = _mean_rgb(path)
            size = path.stat().st_size
        except OSError:
            record.success = False
            record.error = "Captured frame could not be read"
            continue

        near_duplicate = None
        for prior, prior_hash, prior_mean, prior_size in accepted:
            size_ratio = size / max(prior_size, 1)
            if not 0.90 <= size_ratio <= 1.10:
                continue
            if _hamming(hash_value, prior_hash) <= 2 and float(
                np.linalg.norm(mean - prior_mean)
            ) <= 0.018:
                near_duplicate = prior.source_id
                break
        if near_duplicate:
            record.success = False
            record.error = f"Guarded near-duplicate of {near_duplicate}"
            continue

        seen_sha[first.sha256] = record.source_id
        accepted.append((record, hash_value, mean, size))
    return records
