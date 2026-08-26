from datetime import datetime, timezone

from challenger.dates import resolve_marketing_date


def test_utc_run_maps_to_prior_eastern_date():
    now = datetime(2026, 8, 25, 2, 15, tzinfo=timezone.utc)
    assert resolve_marketing_date("auto", now=now).isoformat() == "2026-08-24"


def test_after_midnight_before_rollover_stays_with_prior_marketing_day():
    # 04:30 UTC is 00:30 EDT on August 25.
    now = datetime(2026, 8, 25, 4, 30, tzinfo=timezone.utc)
    assert resolve_marketing_date("auto", now=now).isoformat() == "2026-08-24"


def test_explicit_date_is_unchanged():
    assert resolve_marketing_date("2026-08-20").isoformat() == "2026-08-20"
