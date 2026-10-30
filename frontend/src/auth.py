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
    """The logged-in user as {"user_id", "username", "role"}, or None."""
    return st.session_state.get("fk_user")


def log_in(username: str, password: str) -> str | None:
    """Log in. Returns an error message for the user, or None on success."""
    resp = _post("/auth/login", {"username": username.strip(), "password": password})
    if resp.status_code == 401:
        return "Fel användarnamn eller lösenord."
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    data = resp.json()
    st.session_state["fk_token"] = resp.cookies.get("access_token")
    st.session_state["fk_user"] = {
        "user_id": data["user_id"],
        "username": data["username"],
        "role": _fetch_role(),
    }
    return None


def _fetch_role() -> str:
    """The logged-in user's role ("admin" or "user"). Anything unclear counts as a normal user."""
    try:
        resp = authed_request("GET", "/users/me")
    except BackendUnavailable:
        return "user"
    return resp.json().get("role", "user") if resp.is_success else "user"


def is_admin() -> bool:
    """True only for a logged-in admin. Used to show the demo settings and technical info."""
    user = current_user()
    return bool(user and user.get("role") == "admin")


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
    st.session_state.pop("fk_messages", None)
    st.session_state.pop("fk_conversation_id", None)


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


def delete_my_content() -> tuple[dict | None, str | None]:
    """Delete all chats, diary entries and CBT progress but keep the account.

    Returns ({"conversations", "diary_entries"} counts, None), or (None, error message).
    """
    resp = authed_request("DELETE", "/users/me/data")
    if resp.status_code in (401, 404):
        log_out()
        return None, SESSION_EXPIRED
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    return resp.json(), None

def update_my_data(fields: dict) -> tuple[dict | None, str | None]:
    """Patch the logged-in user's own account details.

    `fields` only contains the keys the user actually changed.
    Returns (updated_user_dict, None), or (None, error message).
    """
    resp = authed_request("PATCH", "/users/me", fields)
    if resp.status_code == 400:
        try:
            return None, resp.json().get("detail") or "Något i formuläret kunde inte sparas."
        except ValueError:
            return None, "Något i formuläret kunde inte sparas."
    if resp.status_code == 422:
        return None, "Något i formuläret stämde inte. Kolla värdena och försök igen."
    if resp.status_code in (401, 404):
        log_out()
        return None, SESSION_EXPIRED
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    return resp.json(), None


def admin_list_users() -> tuple[list[dict] | None, str | None]:
    """List all users for admin tools.

    Returns (users, None), or (None, error message).
    """
    resp = authed_request("GET", "/admin/users")
    if resp.status_code == 403:
        return None, "Du behöver adminbehörighet för att göra det här."
    if resp.status_code in (401, 404):
        log_out()
        return None, SESSION_EXPIRED
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    return resp.json(), None


def admin_change_user_password(user_id: int, new_password: str) -> str | None:
    """Set a new password for any user as admin. Returns an error message, or None."""
    if len(new_password) < MIN_PASSWORD_LENGTH:
        return f"Lösenordet behöver vara minst {MIN_PASSWORD_LENGTH} tecken."

    resp = authed_request("PUT", f"/admin/users/{user_id}/password", {"new_password": new_password})
    if resp.status_code == 403:
        return "Du behöver adminbehörighet för att göra det här."
    if resp.status_code == 404:
        return "Användaren hittades inte."
    if resp.status_code == 422:
        return "Lösenordet godkändes inte. Kontrollera att det uppfyller kraven."
    if resp.status_code in (401,):
        log_out()
        return SESSION_EXPIRED
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    return None


def csv_downloader(kind: str):
    """A function that fetches one CSV export ("account", "chats" or "diary").

    Meant as st.download_button's data, so the file is only built when the
    user clicks. Streamlit calls it outside the script run, where session
    state is unavailable, so the login token is captured now.
    """
    token = st.session_state.get("fk_token", "")

    def fetch() -> bytes:
        try:
            resp = httpx.get(
                f"{BACKEND_URL}/users/me/export/{kind}",
                headers={"Cookie": f"access_token={token}"},
                timeout=TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            raise BackendUnavailable(str(exc)) from exc
        if not resp.is_success:
            raise BackendUnavailable(f"HTTP {resp.status_code}")
        return resp.content

    return fetch


EMAIL_NOT_SET_UP = "Mejlutskick är inte inställt på servern än. Prata med en admin."


def set_reminders(enabled: bool) -> tuple[dict | None, str | None]:
    """Turn the weekly program reminder emails on or off. Returns (user, None) or (None, error)."""
    resp = authed_request("PUT", "/users/me/reminders", {"enabled": enabled})
    if resp.status_code == 400:
        return None, "Lägg till din e-postadress först."
    if resp.status_code in (401, 404):
        log_out()
        return None, SESSION_EXPIRED
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    return resp.json(), None


def send_test_reminder() -> str | None:
    """Send the weekly reminder to yourself right away. Returns an error message, or None."""
    resp = authed_request("POST", "/users/me/reminders/test")
    if resp.status_code == 400:
        return "Lägg till din e-postadress först."
    if resp.status_code == 503:
        return EMAIL_NOT_SET_UP
    if resp.status_code == 502:
        return "Mejlservern kunde inte skicka mejlet just nu. Försök igen senare."
    if resp.status_code in (401, 404):
        log_out()
        return SESSION_EXPIRED
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    return None


def admin_send_reminders() -> tuple[dict | None, str | None]:
    """Send this week's reminders now. Returns ({"sent", "already_sent", "failed"}, None) or (None, error)."""
    resp = authed_request("POST", "/admin/reminders/send")
    if resp.status_code == 503:
        return None, "Mejlutskick är inte inställt: sätt SMTP_HOST med flera i backendens .env."
    if resp.status_code == 403:
        return None, "Du behöver adminbehörighet."
    if resp.status_code in (401, 404):
        log_out()
        return None, SESSION_EXPIRED
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    return resp.json(), None
