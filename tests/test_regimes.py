from challenger.models import Domain
from challenger.regimes import calculate_regime
from tests.helpers import observation


def test_high_chroma_regime(tmp_path):
    observations = [
        observation(tmp_path, "a", "#FF2266", domain=Domain.ART),
        observation(tmp_path, "b", "#00AEEF", domain=Domain.FASHION),
        observation(tmp_path, "c", "#D8E545", domain=Domain.MARKETPLACE),
    ]
    regime = calculate_regime(observations)
    assert regime.median_chroma > 0.1
    assert "chroma" in regime.dominant_regime or "saturated" in regime.dominant_regime


def test_one_source_one_regime_vote(tmp_path):
    a = observation(tmp_path, "same", "#FF0000")
    b = observation(tmp_path, "same", "#0000FF")
    b.region.confidence = 0.5
    other = observation(tmp_path, "other", "#00FF00")
    regime = calculate_regime([a, b, other])
    assert regime.mean_palette_size == 1.0
