from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image

from challenger.color import hex_to_rgb, normalize_hex
from challenger.models import Candidate, Observation


def _packed_rgb(hex_value: str) -> int:
    red, green, blue = hex_to_rgb(normalize_hex(hex_value))
    return (red << 16) | (green << 8) | blue


def _visible_colors(path: str | Path) -> np.ndarray:
    """Return sorted unique decoded visible RGB colors as packed integers."""

    image_path = Path(path)
    if not image_path.exists():
        raise FileNotFoundError(f"Evidence image does not exist: {image_path}")
    rgba = np.asarray(Image.open(image_path).convert("RGBA"), dtype=np.uint8)
    pixels = rgba[rgba[..., 3] >= 32, :3]
    if not len(pixels):
        return np.empty((0,), dtype=np.uint32)
    packed = (
        (pixels[:, 0].astype(np.uint32) << 16)
        | (pixels[:, 1].astype(np.uint32) << 8)
        | pixels[:, 2].astype(np.uint32)
    )
    return np.unique(packed)


def _contains(colors: np.ndarray, hex_value: str) -> bool:
    if not len(colors):
        return False
    value = np.uint32(_packed_rgb(hex_value))
    position = int(np.searchsorted(colors, value))
    return position < len(colors) and bool(colors[position] == value)


def audit_color_truth(
    observations: Iterable[Observation],
    candidates: Iterable[Candidate],
) -> dict:
    """Independently verify that every extracted/public HEX exists in evidence pixels.

    This deliberately does not trust the ``observed_pixel`` flags created during
    palette extraction. It opens each decoded evidence image again and verifies
    exact RGB membership. A failure is a software-integrity error, not a weak-day
    publication state.
    """

    observations = list(observations)
    candidates = list(candidates)
    cache: dict[str, np.ndarray] = {}
    errors: list[dict] = []
    extracted_count = 0
    candidate_evidence_count = 0

    def colors_for(path: str) -> np.ndarray:
        if path not in cache:
            cache[path] = _visible_colors(path)
        return cache[path]

    for observation in observations:
        path = observation.region.screenshot_path
        try:
            source_colors = colors_for(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(
                {
                    "scope": "observation",
                    "source_id": observation.source_id,
                    "region_id": observation.region.region_id,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        for swatch in observation.swatches:
            extracted_count += 1
            if not swatch.observed_pixel:
                errors.append(
                    {
                        "scope": "swatch_flag",
                        "source_id": observation.source_id,
                        "region_id": observation.region.region_id,
                        "hex": swatch.hex,
                        "error": "Palette swatch was not marked as an observed pixel.",
                    }
                )
            if not _contains(source_colors, swatch.hex):
                errors.append(
                    {
                        "scope": "swatch_pixel",
                        "source_id": observation.source_id,
                        "region_id": observation.region.region_id,
                        "hex": swatch.hex,
                        "error": "Extracted HEX was not present in the decoded source pixels.",
                    }
                )

    for candidate in candidates:
        local_hexes = {normalize_hex(item.local_hex) for item in candidate.evidence}
        if normalize_hex(candidate.hex) not in local_hexes:
            errors.append(
                {
                    "scope": "candidate_display",
                    "candidate_hex": candidate.hex,
                    "family": candidate.family_label,
                    "error": "Public display HEX is not one of the candidate's observed local swatches.",
                }
            )
        representative = [
            item
            for item in candidate.evidence
            if item.source_id == candidate.display_hex_source_id
            and normalize_hex(item.local_hex) == normalize_hex(candidate.hex)
        ]
        if not representative:
            errors.append(
                {
                    "scope": "candidate_representative",
                    "candidate_hex": candidate.hex,
                    "display_hex_source_id": candidate.display_hex_source_id,
                    "error": "The named representative source does not contain the public display HEX.",
                }
            )
        for item in candidate.evidence:
            candidate_evidence_count += 1
            try:
                source_colors = colors_for(item.region_path)
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    {
                        "scope": "candidate_evidence",
                        "source_id": item.source_id,
                        "region_id": item.region_id,
                        "hex": item.local_hex,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
            if not item.observed_pixel:
                errors.append(
                    {
                        "scope": "candidate_evidence_flag",
                        "source_id": item.source_id,
                        "region_id": item.region_id,
                        "hex": item.local_hex,
                        "error": "Candidate evidence was not marked as an observed source pixel.",
                    }
                )
            if not _contains(source_colors, item.local_hex):
                errors.append(
                    {
                        "scope": "candidate_evidence_pixel",
                        "source_id": item.source_id,
                        "region_id": item.region_id,
                        "hex": item.local_hex,
                        "error": "Candidate local HEX was not present in its decoded evidence image.",
                    }
                )

    return {
        "passed": not errors,
        "evidence_images_checked": len(cache),
        "extracted_swatches_checked": extracted_count,
        "candidate_count_checked": len(candidates),
        "candidate_evidence_records_checked": candidate_evidence_count,
        "errors": errors,
    }


def require_color_truth(observations: Iterable[Observation], candidates: Iterable[Candidate]) -> dict:
    report = audit_color_truth(observations, candidates)
    if not report["passed"]:
        first = report["errors"][0]
        raise RuntimeError(
            "Color truth verification failed. No result may be rendered or published. "
            f"First error: {first.get('error', 'unknown color-integrity error')}"
        )
    return report
