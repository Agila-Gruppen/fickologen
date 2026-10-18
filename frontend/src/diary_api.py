"""Diary entries for the logged-in user, stored by the backend."""
import auth
from api import BackendUnavailable


class SessionExpired(Exception):
    """The login has expired; the user has been logged out."""


def _call(method: str, path: str, json: dict | None = None):
    resp = auth.authed_request(method, path, json)
    if resp.status_code == 401:
        auth.log_out()
        raise SessionExpired()
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    return resp.json() if resp.content else None


def list_entries() -> list[dict]:
    """The user's entries, newest first."""
    return _call("GET", "/diary/")


def create_entry(title: str, content: str, mood: int | None) -> dict:
    return _call("POST", "/diary/", {"title": title or None, "content": content, "mood": mood})


def update_entry(entry_id: int, title: str, content: str, mood: int | None) -> dict:
    return _call("PATCH", f"/diary/{entry_id}", {"title": title or None, "content": content, "mood": mood})


def delete_entry(entry_id: int) -> None:
    _call("DELETE", f"/diary/{entry_id}")


def delete_all_entries() -> int:
    """Delete every diary entry. Returns how many were deleted."""
    return _call("DELETE", "/diary/")["deleted"]
