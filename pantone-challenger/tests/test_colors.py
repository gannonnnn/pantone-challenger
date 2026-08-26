import numpy as np

from challenger.colors import (
    delta,
    hex_from_oklab,
    oklab_from_hex,
    oklab_to_oklch,
)


def test_hex_round_trip_is_perceptually_close():
    for value in ("#A34D43", "#7D8646", "#4799A2", "#F2F0E9", "#16191D"):
        lab = oklab_from_hex(value)
        rebuilt = hex_from_oklab(lab)
        assert delta(lab, oklab_from_hex(rebuilt)) < 0.004


def test_oklch_is_well_formed():
    lightness, chroma, hue = oklab_to_oklch(oklab_from_hex("#4799A2"))
    assert 0 <= lightness <= 1
    assert chroma >= 0
    assert 0 <= hue < 360
