from datetime import date

from challenger.naming import candidate_labels, name_candidate
from tests.helpers import candidate


def test_neutral_names_do_not_inherit_unstable_hue_labels():
    white = candidate("#EEEEED", with_evidence=False)
    black = candidate("#141416", with_evidence=False)
    white_name = name_candidate(white, date(2026, 8, 30))
    black_name = name_candidate(black, date(2026, 8, 30))
    assert "Chartreuse" not in white_name
    assert white_name.endswith("White")
    assert "Violet" not in black_name
    assert black_name.endswith("Black")


def test_family_and_playful_name_are_separate():
    item = candidate("#4E95A2", with_evidence=False)
    family, creative, display = candidate_labels(item, date(2026, 8, 30))
    assert family
    assert creative
    assert display == f"{creative} {family}"
