"""Shared conversation state and placeholder reply logic for the prototype.

No real NLU here - this mirrors Elin's *tone* (reflect -> validate -> gentle
closing question) with a small rotating set of templates so the Chat and Home
views can share one conversation.
"""
import streamlit as st

GREETING = (
    "Hej, vad bra att du är här. Det här är en plats där du kan skriva precis som "
    "tankarna kommer – jag finns med och läser, i din takt."
)

REPLY_TEMPLATES = [
    "Tack för att du delar det här. Jag hör att du skriver \"{snippet}\" – och det "
    "låter som något som väger en del just nu.\n\nDet är en begriplig reaktion, "
    "även om den kanske känns jobbig. Du behöver inte ha ett färdigt svar för att "
    "sätta ord på den.\n\nOm du vill – vad märker du i kroppen när du tänker på det?",
    "Jag förstår verkligen att \"{snippet}\" känns som mycket att bära. Det är "
    "vanligt att en del av oss reagerar starkt på precis den typen av situationer.\n\n"
    "Vi behöver inte lösa allt på en gång – det räcker att vi tittar närmare på en "
    "liten del av det.\n\nVad tror du den reaktionen försöker skydda dig från?",
    "Det du beskriver – \"{snippet}\" – säger något viktigt om var du är just nu, "
    "och jag är glad att du skriver ner det istället för att bära det ensam.\n\n"
    "Ibland kan två saker vara sanna samtidigt: att reaktionen är begriplig, och "
    "att den samtidigt kostar en hel del energi.\n\nVad skulle ett litet, hanterbart "
    "nästa steg kunna se ut som?",
]


def _snippet(text: str, limit: int = 64) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _generate_reply(user_text: str) -> str:
    idx = st.session_state.get("fk_reply_idx", 0) % len(REPLY_TEMPLATES)
    st.session_state["fk_reply_idx"] = idx + 1
    return REPLY_TEMPLATES[idx].format(snippet=_snippet(user_text))


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
    st.session_state["fk_messages"].append({"role": "assistant", "content": _generate_reply(text)})
