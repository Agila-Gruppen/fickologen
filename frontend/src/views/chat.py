import html

import streamlit as st

from chat_engine import (
    ENGINES,
    BackendUnavailable,
    generate_pending_reply,
    get_engine,
    get_messages,
    has_pending_reply,
    is_unlocked,
    send_user_message,
    set_engine,
    try_unlock,
)
from components import page_header

VIA_LABELS = {
    "regel": "regel",
    "klassificerare": "Gemini-klassificerare",
    "reserv": "reservregel",
}


def _tech_info(msg: dict) -> str | None:
    """One line about how the backend produced a reply, or None if there is nothing to show."""
    if msg["role"] != "assistant" or msg.get("error") or not msg.get("engine"):
        return None
    if msg["engine"] == "legacy":
        return "Gammal motor: samma mall för alla meddelanden"
    category = msg.get("category") or "okänd"
    how = "Gemini skrev svaret" if msg.get("llm_used") else "fast, granskad text (ingen AI)"
    via = VIA_LABELS.get(msg.get("via"), msg.get("via") or "okänt")
    return f"Kategori: {category} · {how} · upptäckt via {via}"


def _render_bubble(msg: dict) -> None:
    role, content = msg["role"], msg["content"]
    if role == "assistant":
        st.markdown('<div class="fk-reflect-label">Fickologen reflekterar…</div>', unsafe_allow_html=True)
        # Blank lines around the content let Streamlit render the model's markdown.
        st.markdown(
            f'<div class="fk-bubble fk-bubble-bot">\n\n{html.escape(content, quote=False)}\n\n</div>',
            unsafe_allow_html=True,
        )
        info = _tech_info(msg) if st.session_state.get("fk_show_tech") else None
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


def _demo_settings() -> None:
    """Choose the chat engine and show how replies were produced (for demos)."""
    with st.expander("Demo-inställningar"):
        engines = list(ENGINES)
        engine = st.radio(
            "Chattmotor",
            options=engines,
            index=engines.index(get_engine()),
            format_func=ENGINES.get,
            horizontal=True,
            key="fk_engine_choice",
        )
        set_engine(engine)
        st.session_state["fk_show_tech"] = st.checkbox(
            "Visa teknisk info under svaren",
            value=st.session_state.get("fk_show_tech", False),
            key="fk_show_tech_choice",
        )


@st.dialog("🔒 Lösenord krävs", dismissible=False)
def _password_dialog() -> None:
    st.markdown(
        "Den här prototypen är lösenordsskyddad. **Skriv in lösenordet** för att "
        "skicka ditt meddelande och börja chatta. Du behöver bara göra det en gång."
    )
    with st.form("fk_password_form", border=False):
        password = st.text_input(
            "Lösenord",
            type="password",
            placeholder="Skriv lösenordet här",
        )
        submitted = st.form_submit_button("Lås upp chatten", type="primary", use_container_width=True)
    if submitted:
        try:
            unlocked = try_unlock(password)
        except BackendUnavailable:
            st.error("Kunde inte nå servern just nu. Försök igen om en liten stund.")
            return
        if unlocked:
            st.rerun()
        st.error("Fel lösenord. Försök igen.")


def render() -> None:
    page_header(
        "Chatt",
        "Låt oss ta det i din takt",
        "Det du skriver stannar mellan dig och Fickologen. Det finns inget rätt "
        "sätt att börja på.",
    )

    _demo_settings()

    for msg in get_messages():
        _render_bubble(msg)

    if has_pending_reply() and not is_unlocked():
        _password_dialog()
        return

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
