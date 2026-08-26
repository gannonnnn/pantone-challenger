from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "America/New_York"
DEFAULT_ROLLOVER_HOUR = 4


def resolve_marketing_date(
    value: str | date | None = "auto",
    *,
    now: datetime | None = None,
    timezone_name: str = DEFAULT_TIMEZONE,
    rollover_hour: int = DEFAULT_ROLLOVER_HOUR,
) -> date:
    """
    Resolve the commercial day represented by a scheduled run.

    The daily GitHub workflow runs near midnight Eastern. GitHub cron uses UTC,
    and daylight-saving time changes the local calendar boundary. A 4 a.m.
    local rollover makes both 23:30 EST and 00:30 EDT belong to the intended
    marketing day.
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if value not in (None, "", "auto", "latest"):
        return date.fromisoformat(str(value))

    tz = ZoneInfo(timezone_name)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    local = current.astimezone(tz)
    effective = local - timedelta(days=1) if local.hour < rollover_hour else local
    return effective.date()


def iso_now(timezone_name: str = DEFAULT_TIMEZONE) -> str:
    return datetime.now(ZoneInfo(timezone_name)).isoformat(timespec="seconds")
