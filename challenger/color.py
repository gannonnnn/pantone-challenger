from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np


NEUTRAL_FAMILIES = {"Black", "Charcoal", "Gray", "Light Gray", "White"}


def normalize_hex(value: str) -> str:
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in value):
        raise ValueError(f"Invalid HEX color: {value!r}")
    return f"#{value.upper()}"


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = normalize_hex(value)[1:]
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: Iterable[float]) -> str:
    vals = [max(0, min(255, int(round(float(x))))) for x in rgb]
    return "#" + "".join(f"{v:02X}" for v in vals)


def _srgb_to_linear(c: np.ndarray) -> np.ndarray:
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def rgb_array_to_oklab(rgb: np.ndarray) -> np.ndarray:
    """Convert an ``(..., 3)`` sRGB array in the 0-255 range to OKLab.

    This vectorized path is used by palette extraction and proof masks so color
    clustering happens in a perceptually meaningful space instead of raw RGB.
    """

    arr = np.asarray(rgb, dtype=float)
    if arr.shape[-1] != 3:
        raise ValueError("RGB input must have a final dimension of length 3")
    linear = _srgb_to_linear(arr)
    r, g, b = np.moveaxis(linear, -1, 0)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = np.cbrt(l), np.cbrt(m), np.cbrt(s)
    return np.stack(
        (
            0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
        ),
        axis=-1,
    )


def rgb_to_oklab(rgb: Iterable[float]) -> tuple[float, float, float]:
    converted = rgb_array_to_oklab(np.asarray(tuple(rgb), dtype=float))
    return tuple(float(x) for x in converted)


def oklab_to_oklch(lab: Iterable[float]) -> tuple[float, float, float]:
    l, a, b = tuple(float(x) for x in lab)
    c = math.hypot(a, b)
    h = (math.degrees(math.atan2(b, a)) + 360.0) % 360.0 if c > 1e-9 else 0.0
    return l, c, h


def hex_to_oklab(value: str) -> tuple[float, float, float]:
    return rgb_to_oklab(hex_to_rgb(value))


def distance(a: Iterable[float], b: Iterable[float]) -> float:
    aa = np.asarray(tuple(a), dtype=float)
    bb = np.asarray(tuple(b), dtype=float)
    return float(np.linalg.norm(aa - bb))


def is_neutral(oklch: Iterable[float], chroma_threshold: float = 0.035) -> bool:
    _, c, _ = tuple(oklch)
    return c < chroma_threshold


def family_label(oklch: Iterable[float]) -> str:
    """Return an intuitive family label for an OKLCH color.

    OKLCH hue is not aligned with an HSL artist wheel: sRGB red is around 29°,
    yellow around 110°, green around 143°, cyan around 195°, and blue around
    264°.  The earlier implementation treated 0° as ordinary red and therefore
    called pure red *orange*, yellow *yellow-green*, and blue *indigo*.  These
    calibrated boundaries are based on actual OKLCH anchor colors.
    """

    l, c, h = tuple(float(x) for x in oklch)
    if c < 0.028:
        if l < 0.20:
            return "Black"
        if l < 0.38:
            return "Charcoal"
        if l < 0.72:
            return "Gray"
        if l < 0.90:
            return "Light Gray"
        return "White"

    # Useful low-chroma material families.  These prevent dark earth tones from
    # being described as bright orange/amber and pale warm neutrals as yellow.
    if 35 <= h < 95 and l < 0.62 and c < 0.17:
        return "Brown"
    if 92 <= h < 136 and l < 0.72 and c < 0.15:
        return "Olive"
    if 45 <= h < 115 and l >= 0.74 and c < 0.075:
        return "Beige"

    # Rose wraps through zero on the OKLCH wheel.
    if h >= 346 or h < 15:
        return "Rose"
    if h < 36:
        return "Red"
    if h < 47:
        return "Red-Orange"
    if h < 70:
        return "Orange"
    if h < 98:
        return "Amber"
    if h < 118:
        return "Yellow"
    if h < 131:
        return "Yellow-Green"
    if h < 141.5:
        return "Chartreuse"
    if h < 162:
        return "Green"
    if h < 184:
        return "Green-Teal"
    if h < 205:
        # Cyan and teal share almost the same OKLCH hue; lightness/chroma are
        # needed to distinguish an electric cyan from a darker muted teal.
        return "Cyan" if l >= 0.80 and c >= 0.12 else "Teal"
    if h < 232:
        return "Blue-Teal"
    if h < 272:
        return "Blue"
    if h < 291:
        return "Indigo"
    if h < 315:
        return "Violet"
    return "Magenta"


def relative_luminance(hex_value: str) -> float:
    arr = _srgb_to_linear(np.asarray(hex_to_rgb(hex_value), dtype=float))
    return float(0.2126 * arr[0] + 0.7152 * arr[1] + 0.0722 * arr[2])


def contrast_ratio(a: str, b: str) -> float:
    l1, l2 = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def readable_text_color(background: str) -> str:
    black = contrast_ratio(background, "#111111")
    white = contrast_ratio(background, "#FFFFFF")
    return "#111111" if black >= white else "#FFFFFF"


def warm_or_cool(hue: float) -> str:
    # Warm red/orange/yellow and magenta/rose; cool green through violet.
    return "warm" if 15 <= hue < 135 or hue >= 315 or hue < 15 else "cool"
