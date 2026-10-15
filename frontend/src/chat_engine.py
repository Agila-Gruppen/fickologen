"""Shared conversation state; replies come from the backend's /chat route.

The Chat and Home views share one in-flight conversation stored in session state.
Logged-in users also have their conversations persisted — the backend returns a
`conversation_id` that we send back on every follow-up so new messages land in the
same thread, and that lets the Saved view open an old thread.
"""
import httpx
import streamlit as st

from api import BACKEND_URL, TIMEOUT_SECONDS, BackendUnavailable

GREETING = (
    "Hej, vad bra att du är här. Det här är en plats där du kan skriva precis som "
    "tankarna kommer – jag finns med och läser, i din takt."
)

ENGINES = {
    "router": "Ny motor (routing)",
    "legacy": "Gammal motor (en mall)",
}

ERROR_REPLY = (
    "Jag lyckades inte svara just nu – något gick fel på min sida, inte på din. "
    "Försök gärna igen om en liten stund.\n\nOm du behöver stöd direkt kan du "
    "ringa 1177 eller Självmordslinjen på 90101."
)


def _auth_headers() -> dict:
    """Logged-in users send their JWT cookie; anonymous users use CHAT_PASSWORD."""
    if st.session_state.get("fk_token"):
        return {"Cookie": f"access_token={st.session_state['fk_token']}"}
    return {"X-Chat-Password": st.session_state.get("fk_password", "")}


def _post(path: str, json: dict | None = None) -> httpx.Response:
    try:
        return httpx.post(
            f"{BACKEND_URL}{path}",
            json=json,
            headers=_auth_headers(),
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise BackendUnavailable(str(exc)) from exc


def _history() -> list[dict]:
    """Conversation to send to the backend, without failed replies."""
    return [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state["fk_messages"]
        if not m.get("error")
    ]


def get_engine() -> str:
    return st.session_state.get("fk_engine", "router")


def set_engine(engine: str) -> None:
    st.session_state["fk_engine"] = engine


def ensure_started() -> None:
    if "fk_messages" not in st.session_state:
        st.session_state["fk_messages"] = [{"role": "assistant", "content": GREETING}]
    if "fk_conversation_id" not in st.session_state:
        st.session_state["fk_conversation_id"] = None


def get_messages() -> list[dict]:
    ensure_started()
    return st.session_state["fk_messages"]


def send_user_message(text: str) -> None:
    text = text.strip()
    if not text:
        return
    ensure_started()
    st.session_state["fk_messages"].append({"role": "user", "content": text})


def start_new_conversation() -> None:
    """Reset the chat view. The next message will create a fresh thread in the DB."""
    st.session_state["fk_messages"] = [{"role": "assistant", "content": GREETING}]
    st.session_state["fk_conversation_id"] = None


def load_conversation(conversation_id: int, messages: list[dict]) -> None:
    """Open an existing conversation in the chat view."""
    bubbles: list[dict] = []
    for m in messages:
        bubbles.append({
            "role": m["role"],
            "content": m["content"],
            "category": m.get("category"),
            "via": m.get("via"),
            "llm_used": m.get("llm_used"),
            "engine": "router",
        })
    st.session_state["fk_messages"] = bubbles
    st.session_state["fk_conversation_id"] = conversation_id


def has_pending_reply() -> bool:
    msgs = get_messages()
    return len(msgs) > 0 and msgs[-1]["role"] == "user"


def is_unlocked() -> bool:
    """True if the user is allowed to chat (logged in, or password unlocked)."""
    return bool(st.session_state.get("fk_token") or st.session_state.get("fk_password"))


def try_unlock(password: str) -> bool:
    """Unlock the chat for anonymous users by trying the shared password."""
    try:
        resp = httpx.post(
            f"{BACKEND_URL}/chat/unlock",
            headers={"X-Chat-Password": password},
            timeout=TIMEOUT_SECONDS,
        )
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
        resp = _post(
            "/chat/",
            {
                "messages": _history(),
                "engine": get_engine(),
                "conversation_id": st.session_state.get("fk_conversation_id"),
            },
        )
        resp.raise_for_status()
        data = resp.json()
        # Remember which backend conversation we're writing to.
        if data.get("conversation_id") is not None:
            st.session_state["fk_conversation_id"] = data["conversation_id"]
        reply = {
            "role": "assistant",
            "content": data["reply"],
            "engine": data.get("engine"),
            "category": data.get("category"),
            "via": data.get("via"),
            "llm_used": data.get("llm_used"),
        }
    except Exception as exc:
        print(f"[chat_engine] Backend call failed: {exc!r}")
        reply = {"role": "assistant", "content": ERROR_REPLY, "error": True}
    st.session_state["fk_messages"].append(reply)