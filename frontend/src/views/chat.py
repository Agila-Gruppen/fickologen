import html

import streamlit as st

from chat_engine import (
    generate_pending_reply,
    get_messages,
    has_pending_reply,
    is_unlocked,
    send_user_message,
    try_unlock,
)
from components import page_header


def _render_bubble(role: str, content: str) -> None:
    if role == "assistant":
        st.markdown('<div class="fk-reflect-label">Fickologen reflekterar…</div>', unsafe_allow_html=True)
        # Blank lines around the content let Streamlit render the model's markdown.
        st.markdown(
            f'<div class="fk-bubble fk-bubble-bot">\n\n{html.escape(content, quote=False)}\n\n</div>',
            unsafe_allow_html=True,
        )
    else:
        _, col = st.columns([1, 5])
        with col:
            st.markdown(
                f'<div class="fk-bubble fk-bubble-user">{html.escape(content)}</div>',
                unsafe_allow_html=True,
            )
    st.markdown("<div style='height: 1.1rem;'></div>", unsafe_allow_html=True)


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
        if try_unlock(password):
            st.rerun()
        st.error("Fel lösenord. Försök igen.")


def render() -> None:
    page_header(
        "Chatt",
        "Låt oss ta det i din takt",
        "Det du skriver stannar mellan dig och Fickologen. Det finns inget rätt "
        "sätt att börja på.",
    )

    for msg in get_messages():
        _render_bubble(msg["role"], msg["content"])

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
