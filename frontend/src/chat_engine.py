"""Shared conversation state and Gemini-backed replies.

The Chat and Home views share one conversation stored in session state.
Sending a message only records it; the Chat view then asks for the reply via
`generate_pending_reply` so it can show a spinner while Gemini answers.
"""
import hmac
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from google import genai

load_dotenv()

MODEL = "gemini-3.5-flash-lite"
PROMPT_PATH = Path(__file__).resolve().parents[2] / "chat-engine" / "prompt_v1.txt"

GREETING = (
    "Hej, vad bra att du är här. Det här är en plats där du kan skriva precis som "
    "tankarna kommer – jag finns med och läser, i din takt."
)

ERROR_REPLY = (
    "Jag lyckades inte svara just nu – något gick fel på min sida, inte på din. "
    "Försök gärna igen om en liten stund.\n\nOm du behöver stöd direkt kan du "
    "ringa 1177 eller Självmordslinjen på 90101."
)


@st.cache_resource
def _client() -> genai.Client:
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


@st.cache_data
def _system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _history() -> list[dict]:
    """Conversation in Gemini's format, without the greeting and failed replies."""
    messages = [m for m in st.session_state["fk_messages"] if not m.get("error")]
    while messages and messages[0]["role"] != "user":
        messages = messages[1:]
    return [
        {
            "role": "user" if m["role"] == "user" else "model",
            "parts": [{"text": m["content"]}],
        }
        for m in messages
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
    return st.session_state.get("fk_unlocked", False)


def try_unlock(password: str) -> bool:
    """Unlock the chat for this session if the password matches CHAT_PASSWORD."""
    expected = os.environ.get("CHAT_PASSWORD", "")
    # Fail closed: without a configured password nobody gets through.
    if expected and hmac.compare_digest(password.encode(), expected.encode()):
        st.session_state["fk_unlocked"] = True
    return is_unlocked()


def generate_pending_reply() -> None:
    if not has_pending_reply() or not is_unlocked():
        return
    try:
        resp = _client().models.generate_content(
            model=MODEL,
            contents=_history(),
            config={"system_instruction": _system_prompt()},
        )
        reply = {"role": "assistant", "content": resp.text or ERROR_REPLY}
        if not resp.text:
            reply["error"] = True
    except Exception as exc:  # missing key, network, quota, ...
        print(f"[chat_engine] Gemini call failed: {exc!r}")
        reply = {"role": "assistant", "content": ERROR_REPLY, "error": True}
    st.session_state["fk_messages"].append(reply)
