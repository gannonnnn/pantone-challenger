from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from challenger.color import family_label, hex_to_oklab, hex_to_rgb, oklab_to_oklch
from challenger.palette import color_match_overlay, extract_palette, swatch_is_candidate_eligible
from challenger.signal_matrix import build_candidates
from tests.helpers import observation


SETTINGS = {
    "clustering": {
        "oklab_distance": 0.05,
        "candidate_distinctness": 0.04,
        "min_local_share": 0.055,
        "min_salience": 0.025,
        "min_component_share": 0.006,
        "min_spatial_coverage": 0.125,
    },
    "scoring": {"target_domains": 4},
}


def family(hex_value: str) -> str:
    return family_label(oklab_to_oklch(hex_to_oklab(hex_value)))


def test_oklch_family_calibration_uses_actual_oklch_wheel():
    assert family("#FF0000") == "Red"
    assert family("#FF7F00") == "Orange"
    assert family("#FFFF00") == "Yellow"
    assert family("#7FFF00") == "Chartreuse"
    assert family("#00FF00") == "Green"
    assert family("#00FFFF") == "Cyan"
    assert family("#0000FF") == "Blue"
    assert family("#8F00FF") == "Violet"
    assert family("#FF00FF") == "Magenta"


def test_palette_hex_is_an_actual_source_pixel(tmp_path):
    path = tmp_path / "blocks.png"
    image = Image.new("RGB", (600, 400), "#F4F4F4")
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 300, 360), fill="#E4372E")
    draw.rectangle((300, 40, 560, 360), fill="#125BC2")
    image.save(path)
    pixels = {tuple(pixel) for pixel in np.asarray(image).reshape(-1, 3)}
    palette = extract_palette(path)
    assert palette
    for swatch in palette:
        assert hex_to_rgb(swatch.hex) in pixels
        assert swatch.observed_pixel


def test_transparent_padding_does_not_create_fake_beige(tmp_path):
    path = tmp_path / "transparent.png"
    image = Image.new("RGBA", (600, 400), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((200, 100, 400, 300), fill="#E4372EFF")
    image.save(path)
    palette = extract_palette(path)
    assert palette[0].hex == "#E4372E"
    assert all(swatch.hex != "#F5F2EC" for swatch in palette)


def test_border_connected_white_is_structural_not_a_candidate(tmp_path):
    path = tmp_path / "white-page.png"
    image = Image.new("RGB", (600, 400), "white")
    ImageDraw.Draw(image).rectangle((120, 80, 480, 320), fill="#17A768")
    image.save(path)
    palette = extract_palette(path)
    white = next(s for s in palette if family(s.hex) == "White")
    green = next(s for s in palette if family(s.hex) in {"Green", "Green-Teal"})
    assert white.structural_background
    assert not swatch_is_candidate_eligible(white, SETTINGS)
    assert swatch_is_candidate_eligible(green, SETTINGS)


def test_tiny_scattered_interface_accent_is_not_promoted(tmp_path):
    path = tmp_path / "buttons.png"
    image = Image.new("RGB", (800, 600), "white")
    draw = ImageDraw.Draw(image)
    for row in range(5):
        for col in range(5):
            x, y = 25 + col * 150, 25 + row * 110
            draw.rectangle((x, y, x + 18, y + 10), fill="#00A8FF")
    image.save(path)
    blue = next((s for s in extract_palette(path) if family(s.hex) in {"Blue", "Blue-Teal", "Cyan"}), None)
    if blue is not None:
        assert not swatch_is_candidate_eligible(blue, SETTINGS)


def test_candidate_display_hex_is_observed_medoid(tmp_path):
    observations = [
        observation(tmp_path, "a", "#E9342E"),
        observation(tmp_path, "b", "#ED3A31"),
        observation(tmp_path, "c", "#E62D28"),
    ]
    candidates = build_candidates(observations, "2026-09-05", SETTINGS)
    candidate = max(candidates, key=lambda c: c.source_count)
    local_hexes = {item.local_hex for item in candidate.evidence}
    assert candidate.hex in local_hexes
    assert candidate.color_integrity["display_hex_is_observed"] is True
    assert candidate.color_integrity["all_local_hex_observed"] is True


def test_complete_linkage_prevents_color_chain_drift(tmp_path):
    # A and B are near; B and C are near; A and C are deliberately farther than
    # the complete-linkage threshold. They must not all collapse into one color.
    observations = [
        observation(tmp_path, "a", "#0B5BC0"),
        observation(tmp_path, "b", "#0E62BF"),
        observation(tmp_path, "c", "#156FBE"),
    ]
    candidates = build_candidates(observations, "2026-09-05", SETTINGS)
    assert max(c.source_count for c in candidates) < 3


def test_color_proof_overlay_keeps_matching_pixels_colored(tmp_path):
    path = tmp_path / "proof.png"
    image = Image.new("RGB", (600, 400), "white")
    ImageDraw.Draw(image).rectangle((100, 80, 500, 320), fill="#E4372E")
    image.save(path)
    overlay = color_match_overlay(path, hex_to_oklab("#E4372E"))
    arr = np.asarray(overlay)
    assert tuple(arr[arr.shape[0] // 2, arr.shape[1] // 2]) == (228, 55, 46)
    assert tuple(arr[5, 5]) != (255, 255, 255)
