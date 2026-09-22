import streamlit as st

from chat_engine import get_messages, send_user_message
from components import page_header


def _render_bubble(role: str, content: str) -> None:
    if role == "assistant":
        st.markdown('<div class="fk-reflect-label">Fickologen reflekterar…</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="fk-bubble fk-bubble-bot">{content}</div>', unsafe_allow_html=True)
    else:
        _, col = st.columns([1, 5])
        with col:
            st.markdown(f'<div class="fk-bubble fk-bubble-user">{content}</div>', unsafe_allow_html=True)
    st.markdown("<div style='height: 1.1rem;'></div>", unsafe_allow_html=True)


def render() -> None:
    page_header(
        "Chatt",
        "Låt oss ta det i din takt",
        "Det du skriver stannar mellan dig och Fickologen. Det finns inget rätt "
        "sätt att börja på.",
    )

    for msg in get_messages():
        _render_bubble(msg["role"], msg["content"])

    user_text = st.chat_input("Skriv vad som helst – det finns ingen fel ordning.")
    if user_text:
        send_user_message(user_text)
        st.rerun()

    st.markdown(
        '<div class="fk-chat-intro" style="margin-top:1.6rem;">'
        "Detta är en tidig prototyp. Svaren ovan är exempel på ton och struktur, "
        "inte skarp funktionalitet."
        "</div>",
        unsafe_allow_html=True,
    )
