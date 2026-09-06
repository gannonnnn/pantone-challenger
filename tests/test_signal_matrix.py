from challenger.models import Domain, PanelType, ScaleClass, SignalStage
from challenger.signal_matrix import build_candidates
from tests.helpers import observation


SETTINGS = {"clustering": {"oklab_distance": 0.06, "candidate_distinctness": 0.04, "min_local_share": 0.01}, "scoring": {"target_domains": 4}}


def test_equal_source_voting_even_when_local_share_differs(tmp_path):
    observations = [
        observation(tmp_path, "a", "#115BB9", share=0.90),
        observation(tmp_path, "b", "#115BB9", share=0.10, domain=Domain.FASHION),
        observation(tmp_path, "c", "#115BB9", share=0.08, domain=Domain.MARKETPLACE),
    ]
    candidate = build_candidates(observations, "2026-09-05", SETTINGS)[0]
    assert {e.source_vote for e in candidate.evidence} == {1.0}
    assert candidate.top_source_weight == 1/3


def test_candidate_preserves_domain_sector_stage_and_local_swatch(tmp_path):
    observations = [
        observation(tmp_path, "art-a", "#A5C84A", domain=Domain.ART, sector="graduate art", stage=SignalStage.CREATION),
        observation(tmp_path, "market-b", "#A5C84A", domain=Domain.MARKETPLACE, sector="resale", stage=SignalStage.DISTRIBUTION),
        observation(tmp_path, "intent-c", "#A5C84A", domain=Domain.AUDIENCE_INTENT, sector="digital products", stage=SignalStage.ATTENTION),
    ]
    c = build_candidates(observations, "2026-09-05", SETTINGS)[0]
    assert c.domain_count == 3
    assert c.sector_count == 3
    assert c.stage_count == 3
    assert all(e.local_hex == "#A5C84A" for e in c.evidence)


def test_small_and_large_signals_are_recorded(tmp_path):
    obs = [
        observation(tmp_path, "small", "#A5C84A", scale=ScaleClass.GRASSROOTS, panel=PanelType.DISCOVERY),
        observation(tmp_path, "large", "#A5C84A", scale=ScaleClass.LARGE_COMMERCIAL, panel=PanelType.BENCHMARK, domain=Domain.ADVERTISING),
    ]
    c = build_candidates(obs, "2026-09-05", SETTINGS)[0]
    assert c.small_large_diversity == 1.0
    assert c.benchmark_count == 1 and c.discovery_count == 1
