"""Shared conversation state; replies come from the backend's /chat route.

The Chat and Home views share one conversation stored in session state.
Sending a message only records it; the Chat view then asks for the reply via
`generate_pending_reply` so it can show a spinner while the backend answers.
"""
import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")
# Generous: the backend waits for the language model before answering.
TIMEOUT_SECONDS = 60

GREETING = (
    "Hej, vad bra att du är här. Det här är en plats där du kan skriva precis som "
    "tankarna kommer – jag finns med och läser, i din takt."
)

ERROR_REPLY = (
    "Jag lyckades inte svara just nu – något gick fel på min sida, inte på din. "
    "Försök gärna igen om en liten stund.\n\nOm du behöver stöd direkt kan du "
    "ringa 1177 eller Självmordslinjen på 90101."
)


class BackendUnavailable(Exception):
    """The backend could not be reached or answered with an unexpected error."""


def _post(path: str, password: str, json: dict | None = None) -> httpx.Response:
    return httpx.post(
        f"{BACKEND_URL}{path}",
        json=json,
        headers={"X-Chat-Password": password},
        timeout=TIMEOUT_SECONDS,
    )


def _history() -> list[dict]:
    """Conversation to send to the backend, without failed replies."""
    return [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state["fk_messages"]
        if not m.get("error")
    ]


def ensure_started() -> None:
    if "fk_messages" not in st.session_state:
        st.session_state["fk_messages"] = [{"role": "assistant", "content": GREETING}]


def get_messages() -> list[dict]:
    ensure_started()
    return st.session_state["fk_messages"]


def send_user_message(text: str) -> None:
    text = text.strip()
    if not text:
        return
    ensure_started()
    st.session_state["fk_messages"].append({"role": "user", "content": text})


def has_pending_reply() -> bool:
    return get_messages()[-1]["role"] == "user"


def is_unlocked() -> bool:
    return "fk_password" in st.session_state


def try_unlock(password: str) -> bool:
    """Unlock the chat for this session if the backend accepts the password."""
    try:
        resp = _post("/chat/unlock", password)
    except httpx.HTTPError as exc:
        raise BackendUnavailable(str(exc)) from exc
    if resp.status_code == 401:
        return False
    if not resp.is_success:
        raise BackendUnavailable(f"HTTP {resp.status_code}")
    st.session_state["fk_password"] = password
    return True


def generate_pending_reply() -> None:
    if not has_pending_reply() or not is_unlocked():
        return
    try:
        resp = _post("/chat/", st.session_state["fk_password"], {"messages": _history()})
        resp.raise_for_status()
        reply = {"role": "assistant", "content": resp.json()["reply"]}
    except Exception as exc:  # backend down, model failure, ...
        print(f"[chat_engine] Backend call failed: {exc!r}")
        reply = {"role": "assistant", "content": ERROR_REPLY, "error": True}
    st.session_state["fk_messages"].append(reply)
