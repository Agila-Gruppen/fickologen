"""Shared datetime helpers for the frontend."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

STOCKHOLM = ZoneInfo("Europe/Stockholm")

MONTHS = [
    "januari", "februari", "mars", "april", "maj", "juni",
    "juli", "augusti", "september", "oktober", "november", "december",
]


def to_local(value: str | datetime) -> datetime | None:
    """
    Parse an ISO datetime from the backend (treated as UTC when naive) and
    return it in Stockholm time. Returns None if the input can't be parsed.
    """
    try:
        dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(STOCKHOLM)


def format_day(dt: datetime) -> str:
    """A date the way you would say it: 31 oktober 2026."""
    return f"{dt.day} {MONTHS[dt.month - 1]} {dt.year}"
