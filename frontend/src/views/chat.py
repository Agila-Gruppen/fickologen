import html
from typing import Any

import streamlit as st

import auth
from chat_engine import (
    generate_pending_reply,
    get_messages,
    has_pending_reply,
    is_unlocked,
    send_user_message,
    start_new_conversation,
)
from components import open_account_dialog, page_header

VIA_LABELS = {
    "regel": "regel",
    "klassificerare": "Gemini-klassificerare",
    "reserv": "reservregel",
}


def _tech_info(msg: dict[str, Any]) -> str | None:
    """One line about how the backend produced a reply, or None if there is nothing to show."""
    if msg["role"] != "assistant" or msg.get("error") or not msg.get("engine"):
        return None
    if msg["engine"] == "legacy":
        return "Version 1: samma mall för alla meddelanden"
    category = msg.get("category") or "okänd"
    how = "Gemini skrev svaret" if msg.get("llm_used") else "fast, granskad text (ingen AI)"
    via_key = msg.get("via") or "okänt"
    via = VIA_LABELS.get(via_key, via_key)
    line = f"Kategori: {category} · {how} · upptäckt via {via}"
    if msg["engine"] == "rag":
        sources = msg.get("sources") or []
        line += f" · Källor: {'; '.join(sources)}" if sources else " · Ingen kunskap användes"
    return line


def render_bubble(msg: dict[str, Any], compact: bool = False) -> None:
    """One chat message. `compact` leaves out the "reflekterar" label, for small chat panels."""
    role, content = msg["role"], msg["content"]
    if role == "assistant":
        if not compact:
            st.markdown('<div class="fk-reflect-label">Fickologen reflekterar…</div>', unsafe_allow_html=True)
        # Blank lines around the content let Streamlit render the model's markdown.
        st.markdown(
            f'<div class="fk-bubble fk-bubble-bot">\n\n{html.escape(content, quote=False)}\n\n</div>',
            unsafe_allow_html=True,
        )
        info = _tech_info(msg) if auth.is_admin() and st.session_state.get("fk_show_tech") else None
        if info:
            st.caption(info)
    else:
        _, col = st.columns([1, 5])
        with col:
            st.markdown(
                f'<div class="fk-bubble fk-bubble-user">{html.escape(content)}</div>',
                unsafe_allow_html=True,
            )
    st.markdown("<div style='height: 1.1rem;'></div>", unsafe_allow_html=True)


def _render_login_cta() -> None:
    """Shown instead of the composer when the visitor isn't logged in."""
    st.markdown(
        '<div class="fk-card" style="text-align:center;">'
        '<span class="fk-card-icon">🔒</span>'
        '<div class="fk-card-title">Logga in för att chatta</div>'
        '<p class="fk-card-text">'
        "Chatten är i stängd beta. Logga in på ditt konto eller skapa ett nytt "
        "för att börja prata med Fickologen."
        '</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        if st.button(
            "Logga in / skapa konto",
            type="primary",
            use_container_width=True,
            key="fk_chat_login_cta",
        ):
            open_account_dialog()

def render() -> None:
    page_header(
        "Chatt",
        "Låt oss ta det i din takt",
        "Det du skriver stannar mellan dig och Fickologen. Det finns inget rätt "
        "sätt att börja på.",
    )

    if not is_unlocked():
        _render_login_cta()
        return

    _, right = st.columns([4, 2])
    with right:
        if st.button("➕ Ny chatt", use_container_width=True, key="fk_new_chat"):
            start_new_conversation()
            st.rerun()

    for msg in get_messages():
        render_bubble(msg)

    user_text = st.chat_input("Skriv vad som helst – det finns ingen fel ordning.")
    if user_text:
        send_user_message(user_text)
        st.rerun()

    if has_pending_reply():
        with st.spinner("Fickologen reflekterar…"):
            generate_pending_reply()
        st.rerun()

    st.markdown(
        '<div class="fk-chat-intro" style="margin-top:1.6rem;">'
        "Detta är en tidig prototyp. Fickologen är en AI och ersätter inte vård – "
        "vid akut kris, ring 112 eller Självmordslinjen på 90101."
        "</div>",
        unsafe_allow_html=True,
    )