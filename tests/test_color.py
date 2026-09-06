from challenger.color import family_label, hex_to_oklab, normalize_hex, oklab_to_oklch, readable_text_color


def family(hex_value):
    return family_label(oklab_to_oklch(hex_to_oklab(hex_value)))


def test_hex_normalization():
    assert normalize_hex("abc") == "#AABBCC"


def test_neutrals_are_not_given_chromatic_names():
    assert family("#141416") in {"Black", "Charcoal"}
    assert family("#EEEEED") in {"Light Gray", "White"}


def test_chromatic_families_are_plausible():
    assert family("#A5C84A") in {"Yellow-Green", "Chartreuse", "Green"}
    assert family("#115BB9") in {"Blue", "Indigo"}
    assert family("#A34D43") in {"Red", "Red-Orange", "Orange"}


def test_text_contrast_switches():
    assert readable_text_color("#FFFFFF") == "#111111"
    assert readable_text_color("#111111") == "#FFFFFF"
