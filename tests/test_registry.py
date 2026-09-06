from challenger.config import load_sources


def test_source_registry_validates_and_spans_culture():
    version, sources = load_sources()
    assert version == "2026.09-v1.5"
    enabled = [s for s in sources if s.enabled]
    assert len(enabled) >= 50
    assert len({s.domain.value for s in enabled}) >= 10
    assert {s.signal_stage.value for s in enabled} == {"creation", "distribution", "attention"}
    assert {s.panel_type.value for s in enabled} == {"benchmark", "discovery"}


def test_authoritative_sector_mappings():
    _, sources = load_sources()
    by_id = {s.id: s for s in sources}
    assert by_id["spotify"].sector == "music streaming"
    assert by_id["max"].sector == "streaming entertainment"
    assert by_id["playstation"].sector == "video games"
    assert by_id["epic-games-store"].sector == "video games"
    assert by_id["nike"].sector == "sportswear"
    assert by_id["sephora"].sector == "beauty retail"


def test_no_public_runtime_favicon_fallback():
    _, sources = load_sources()
    assert all(s.brand_mark_status != "approved" or s.brand_mark_path for s in sources)
    assert not any("favicon" in s.brand_mark_path.lower() for s in sources)
