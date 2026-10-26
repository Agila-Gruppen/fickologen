"""Shared datetime helpers for the frontend."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

STOCKHOLM = ZoneInfo("Europe/Stockholm")


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