"""Account handling against the backend: sign up, log in, log out, passwords and account data.

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


def authed_request(method: str, path: str, json: dict | None = None) -> httpx.Response:
    """Call the backend as the logged-in user by sending the stored token as its cookie."""
    headers = {"Cookie": f"access_token={st.session_state.get('fk_token', '')}"}
    try:
        return httpx.request(
            method, f"{BACKEND_URL}{path}", json=json, headers=headers, timeout=TIMEOUT_SECONDS
        )
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


def _check_new_password(password: str, password_again: str) -> str | None:
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Lösenordet behöver vara minst {MIN_PASSWORD_LENGTH} tecken."
    if password != password_again:
        return "Lösenorden matchar inte."
    return None


def _show_recovery_code(code: str) -> None:
    """Hand a new recovery code to the UI, which shows it once in a dialog."""
    st.session_state["fk_recovery_code"] = code


def sign_up(username: str, password: str, password_again: str) -> str | None:
    """Create an account and log in. Returns an error message, or None on success."""
    username = username.strip()
    if not MIN_USERNAME_LENGTH <= len(username) <= MAX_USERNAME_LENGTH:
        return f"Användarnamnet behöver vara {MIN_USERNAME_LENGTH}–{MAX_USERNAME_LENGTH} tecken."
    if not username.replace("_", "").isalnum():
        return "Användarnamnet får bara innehålla bokstäver, siffror och understreck."
    if error := _check_new_password(password, password_again):
        return error

    resp = _post("/users/", {"username": username, "password": password})
    if resp.status_code == 400:
        return "Användarnamnet är redan upptaget."
    if resp.status_code == 422:
        return "Användarnamnet eller lösenordet godkändes inte. Försök med något annat."
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    _show_recovery_code(resp.json()["recovery_code"])
    return log_in(username, password)


def reset_password(username: str, recovery_code: str, password: str, password_again: str) -> str | None:
    """Set a new password with the recovery code, then log in. Returns an error message, or None."""
    if not username.strip() or not recovery_code.strip():
        return "Fyll i ditt användarnamn och din återställningskod."
    if error := _check_new_password(password, password_again):
        return error

    resp = _post(
        "/auth/reset-password",
        {"username": username.strip(), "recovery_code": recovery_code, "new_password": password},
    )
    if resp.status_code in (400, 422):
        return "Användarnamnet eller återställningskoden stämmer inte."
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    # The used code is spent; the backend hands out a new one.
    _show_recovery_code(resp.json()["recovery_code"])
    return log_in(username, password)


def log_out() -> None:
    st.session_state.pop("fk_user", None)
    st.session_state.pop("fk_token", None)


SESSION_EXPIRED = "Din inloggning har gått ut. Logga in igen för att fortsätta."


def my_data() -> tuple[dict | None, str | None]:
    """Everything stored about the logged-in user.

    Returns (data, None) on success, or (None, error message). An expired
    login logs the user out.
    """
    resp = authed_request("GET", "/users/me")
    if resp.status_code in (401, 404):
        log_out()
        return None, SESSION_EXPIRED
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    return resp.json(), None


def delete_account() -> str | None:
    """Delete the account and all its data, then log out. Returns an error message, or None."""
    resp = authed_request("DELETE", "/users/me")
    if resp.status_code == 401:
        log_out()
        return SESSION_EXPIRED
    # 404: the account is already gone, which is what the user asked for.
    if not resp.is_success and resp.status_code != 404:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    log_out()
    return None


def change_password(current_password: str, password: str, password_again: str) -> str | None:
    """Change the logged-in user's password. Returns an error message, or None on success."""
    if error := _check_new_password(password, password_again):
        return error
    resp = authed_request(
        "PUT", "/users/me/password", {"current_password": current_password, "new_password": password}
    )
    if resp.status_code == 400:
        return "Ditt nuvarande lösenord stämmer inte."
    if resp.status_code in (401, 404):
        log_out()
        return SESSION_EXPIRED
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    return None


def new_recovery_code(current_password: str) -> str | None:
    """Replace the recovery code with a new one. Returns an error message, or None on success."""
    resp = authed_request("POST", "/users/me/recovery-code", {"current_password": current_password})
    if resp.status_code == 400:
        return "Lösenordet stämmer inte."
    if resp.status_code in (401, 404):
        log_out()
        return SESSION_EXPIRED
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    _show_recovery_code(resp.json()["recovery_code"])
    return None
