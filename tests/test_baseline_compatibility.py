from __future__ import annotations

import json

from challenger.baseline import load_history


def _day(root, date, key):
    day = root / date
    day.mkdir(parents=True)
    (day / "observations.json").write_text(json.dumps([{"source_id": "x", "swatches": []}]))
    (day / "manifest.json").write_text(json.dumps({"baseline_compatibility_key": key}))


def test_only_color_compatible_days_enter_baseline(tmp_path):
    _day(tmp_path, "2026-09-01", "legacy")
    _day(tmp_path, "2026-09-02", "color-truth-v1")
    history = load_history(
        tmp_path,
        "2026-09-05",
        compatibility_key="color-truth-v1",
    )
    assert [day["date"] for day in history] == ["2026-09-02"]


def test_unversioned_history_is_skipped_when_key_is_required(tmp_path):
    day = tmp_path / "2026-09-01"
    day.mkdir()
    (day / "observations.json").write_text("[]")
    assert load_history(tmp_path, "2026-09-05", compatibility_key="color-truth-v1") == []
