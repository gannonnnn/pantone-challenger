import json

from challenger.recurrence import recurrence_for_candidates
from tests.helpers import candidate


def test_tied_days_use_fractional_day_share(tmp_path):
    archive = tmp_path / "archive"
    day = archive / "2026-01-01"
    day.mkdir(parents=True)
    (day / "result.json").write_text(json.dumps({"state":"ready","challenger":[{"hex":"#A5C84A","evidence":[]},{"hex":"#4799A2","evidence":[]}]}))
    c = candidate("#A5C84A")
    rec = recurrence_for_candidates(archive, 2026, [c], "2026-01-02")
    assert rec[c.hex]["appearance_days"] == 2
    assert rec[c.hex]["leaderboard_day_share"] == 1.5
