"""Shared conversation state; replies come from the backend's /chat route.

The Chat and Home views share one in-flight conversation stored in session state.
Only logged-in users can chat — the backend persists their conversations and
returns a `conversation_id` that we send back on every follow-up so new messages
land in the same thread, and that lets the Saved view open an old thread.
"""
import httpx
import streamlit as st

from api import BACKEND_URL, TIMEOUT_SECONDS, BackendUnavailable

GREETING = (
    "Hej, vad bra att du är här. Det här är en plats där du kan skriva precis som "
    "tankarna kommer – jag finns med och läser, i din takt."
)

# The three chat engine versions, oldest first. "rag" is the latest and the default.
ENGINES = {
    "legacy": "Version 1: Grundmotor (en mall)",
    "router": "Version 2: Routing (lager och mallar)",
    "rag": "Version 3: Routing + RAG (kunskap ur modulerna)",
}
DEFAULT_ENGINE = "rag"

ERROR_REPLY = (
    "Jag lyckades inte svara just nu – något gick fel på min sida, inte på din. "
    "Försök gärna igen om en liten stund.\n\nOm du behöver stöd direkt kan du "
    "ringa 1177 eller Självmordslinjen på 90101."
)


def _auth_headers() -> dict:
    """The JWT cookie identifies the logged-in user; chat requires it."""
    token = st.session_state.get("fk_token", "")
    return {"Cookie": f"access_token={token}"}


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
    return st.session_state.get("fk_engine", DEFAULT_ENGINE)


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
    """True if the user is logged in and can therefore reach the chat endpoint."""
    return bool(st.session_state.get("fk_token"))

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
        if resp.status_code == 403:
            reply = {
                "role": "assistant",
                "content": (
                    "Chatten är i stängd beta just nu och ditt konto har inte fått "
                    "åtkomst än. Hör av dig till teamet om du vill vara med och testa."
                ),
                "error": True,
            }
            st.session_state["fk_messages"].append(reply)
            return
        if resp.status_code == 401:
            # Login expired; drop state so the UI falls back to the login CTA.
            st.session_state.pop("fk_token", None)
            st.session_state.pop("fk_user", None)
            st.session_state["fk_messages"].append({
                "role": "assistant",
                "content": "Din inloggning har gått ut. Logga in igen för att fortsätta.",
                "error": True,
            })
            return
        resp.raise_for_status()
        data = resp.json()
        if data.get("conversation_id") is not None:
            st.session_state["fk_conversation_id"] = data["conversation_id"]
        reply = {
            "role": "assistant",
            "content": data["reply"],
            "engine": data.get("engine"),
            "category": data.get("category"),
            "via": data.get("via"),
            "llm_used": data.get("llm_used"),
            # Titles of the knowledge passages the reply was grounded in (RAG only).
            "sources": [source["source"] for source in data.get("sources") or []],
        }
    except Exception as exc:
        print(f"[chat_engine] Backend call failed: {exc!r}")
        reply = {"role": "assistant", "content": ERROR_REPLY, "error": True}
    st.session_state["fk_messages"].append(reply)