"""Client for the backend's /program endpoints (the 12-week exercise program)."""
from typing import Any

import httpx
import streamlit as st

from api import BACKEND_URL, TIMEOUT_SECONDS, BackendUnavailable
from auth import SESSION_EXPIRED, log_out

NOT_UNLOCKED = "Den här veckan är inte öppen än. Den öppnas när du är klar med veckan före."
NOT_STARTED = "Du har inte startat programmet än."


def _request(method: str, path: str, json: dict | None = None) -> httpx.Response:
    headers = {"Cookie": f"access_token={st.session_state.get('fk_token', '')}"}
    try:
        return httpx.request(method, f"{BACKEND_URL}{path}", headers=headers, json=json, timeout=TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        raise BackendUnavailable(str(exc)) from exc


def _call(
    method: str,
    path: str,
    json: dict | None = None,
    messages: dict[int, str] | None = None,
) -> tuple[Any | None, str | None]:
    """Returns (data, None), or (None, a message for the user). `messages` maps status codes to texts."""
    resp = _request(method, path, json)
    if resp.status_code == 401:
        log_out()
        return None, SESSION_EXPIRED
    if messages and resp.status_code in messages:
        return None, messages[resp.status_code]
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    return resp.json(), None


def get_overview() -> tuple[dict | None, str | None]:
    """The 12 weeks with the user's status for each."""
    return _call("GET", "/program/")


def start() -> tuple[dict | None, str | None]:
    """Starts the program at week 1 (does nothing if it is already started)."""
    return _call("POST", "/program/start")


def reset() -> tuple[dict | None, str | None]:
    """Removes the user's progress and everything they wrote in the program."""
    return _call("DELETE", "/program/")


def get_week(number: int) -> tuple[dict | None, str | None]:
    """One week with theory, exercises and what the user has saved."""
    return _call("GET", f"/program/weeks/{number}", messages={403: NOT_UNLOCKED, 404: "Veckan finns inte.", 409: NOT_STARTED})


def save_exercise(
    number: int,
    exercise_id: str,
    done: bool,
    reflection: str | None,
    rating_before: int | None = None,
    rating_after: int | None = None,
) -> str | None:
    """Saves what the user did on an exercise. Returns None on success, or an error message."""
    _, error = _call(
        "PUT",
        f"/program/weeks/{number}/exercises/{exercise_id}",
        {"done": done, "reflection": reflection, "rating_before": rating_before, "rating_after": rating_after},
        messages={
            403: NOT_UNLOCKED,
            404: "Övningen finns inte.",
            409: NOT_STARTED,
            422: "Det gick inte att spara. Kontrollera att siffrorna är mellan 0 och 100 och att texten inte är för lång.",
        },
    )
    return error


def complete_week(number: int) -> tuple[dict | None, str | None]:
    """Marks the week as done and opens the next one."""
    return _call(
        "POST",
        f"/program/weeks/{number}/complete",
        messages={403: NOT_UNLOCKED, 409: "Gör klart veckans obligatoriska övningar först."},
    )
