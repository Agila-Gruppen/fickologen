"""Client for the backend's /conversations endpoints (saved chats)."""
import httpx
import streamlit as st

from api import BACKEND_URL, TIMEOUT_SECONDS, BackendUnavailable
from auth import SESSION_EXPIRED, log_out


def _authed(method: str, path: str, json: dict | None = None) -> httpx.Response:
    headers = {"Cookie": f"access_token={st.session_state.get('fk_token', '')}"}
    try:
        return httpx.request(method, f"{BACKEND_URL}{path}", headers=headers, json=json, timeout=TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        raise BackendUnavailable(str(exc)) from exc


def list_conversations() -> tuple[list[dict] | None, str | None]:
    """All the logged-in user's conversations, newest first."""
    resp = _authed("GET", "/conversations/")
    if resp.status_code == 401:
        log_out()
        return None, SESSION_EXPIRED
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    return resp.json(), None


def get_conversation(conversation_id: int) -> tuple[dict | None, str | None]:
    """A single conversation with all its messages."""
    resp = _authed("GET", f"/conversations/{conversation_id}/messages")
    if resp.status_code == 401:
        log_out()
        return None, SESSION_EXPIRED
    if resp.status_code == 404:
        return None, "Konversationen finns inte längre."
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    return resp.json(), None


def rename_conversation(conversation_id: int, title: str) -> str | None:
    """Gives a saved chat a new name. Returns None on success, or an error message."""
    if not title.strip():
        return "Skriv ett namn på chatten."
    resp = _authed("PATCH", f"/conversations/{conversation_id}", {"title": title})
    if resp.status_code == 401:
        log_out()
        return SESSION_EXPIRED
    if resp.status_code == 404:
        return "Chatten finns inte längre."
    if resp.status_code == 422:
        return "Namnet gick inte att spara. Försök med ett kortare namn."
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    return None


def delete_conversation(conversation_id: int) -> str | None:
    """Returns None on success, or an error message."""
    resp = _authed("DELETE", f"/conversations/{conversation_id}")
    if resp.status_code == 401:
        log_out()
        return SESSION_EXPIRED
    # 404 is fine — the user wanted it gone, it's gone.
    if not resp.is_success and resp.status_code != 404:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    return None


def delete_all_conversations() -> tuple[int | None, str | None]:
    """Delete every saved chat. Returns (how many were deleted, None), or (None, error message)."""
    resp = _authed("DELETE", "/conversations/")
    if resp.status_code == 401:
        log_out()
        return None, SESSION_EXPIRED
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    return resp.json()["deleted"], None
