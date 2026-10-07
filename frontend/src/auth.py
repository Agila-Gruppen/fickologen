"""Account handling: sign up, log in and log out against the backend.

The backend sets its JWT as an HTTP-only cookie. Streamlit talks to the backend
server-side, so the token is kept in session state together with the user.
"""
import httpx
import streamlit as st

from api import BACKEND_URL, TIMEOUT_SECONDS, BackendUnavailable

# Mirrors the rules in the backend's UserCreate schema.
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 50
MIN_PASSWORD_LENGTH = 6


def _post(path: str, json: dict) -> httpx.Response:
    try:
        return httpx.post(f"{BACKEND_URL}{path}", json=json, timeout=TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        raise BackendUnavailable(str(exc)) from exc


def current_user() -> dict | None:
    """The logged-in user as {"user_id", "username"}, or None."""
    return st.session_state.get("fk_user")


def log_in(username: str, password: str) -> str | None:
    """Log in. Returns an error message for the user, or None on success."""
    resp = _post("/auth/login", {"username": username.strip(), "password": password})
    if resp.status_code == 401:
        return "Fel användarnamn eller lösenord."
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    data = resp.json()
    st.session_state["fk_user"] = {"user_id": data["user_id"], "username": data["username"]}
    st.session_state["fk_token"] = resp.cookies.get("access_token")
    return None


def sign_up(username: str, password: str, password_again: str) -> str | None:
    """Create an account and log in. Returns an error message, or None on success."""
    username = username.strip()
    if not MIN_USERNAME_LENGTH <= len(username) <= MAX_USERNAME_LENGTH:
        return f"Användarnamnet behöver vara {MIN_USERNAME_LENGTH}–{MAX_USERNAME_LENGTH} tecken."
    if not username.replace("_", "").isalnum():
        return "Användarnamnet får bara innehålla bokstäver, siffror och understreck."
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Lösenordet behöver vara minst {MIN_PASSWORD_LENGTH} tecken."
    if password != password_again:
        return "Lösenorden matchar inte."

    resp = _post("/users/", {"username": username, "password": password})
    if resp.status_code == 400:
        return "Användarnamnet är redan upptaget."
    if resp.status_code == 422:
        return "Användarnamnet eller lösenordet godkändes inte. Försök med något annat."
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    return log_in(username, password)


def log_out() -> None:
    st.session_state.pop("fk_user", None)
    st.session_state.pop("fk_token", None)
