"""Saved chats: list the logged-in user's conversations, open, rename or delete them."""
import html
from datetime import datetime
from datetime_utils import to_local

import streamlit as st

import auth
import conversations as conv_api
from chat_engine import load_conversation, start_new_conversation
from components import go_to, page_header


def _format_dt(iso: str) -> str:
    dt = to_local(iso)
    if dt is None:
        return iso
    return dt.strftime("%Y-%m-%d %H:%M")


def _open(conversation_id: int) -> None:
    with st.spinner("Öppnar chatten..."):
        data, error = conv_api.get_conversation(conversation_id)
    if error:
        st.error(error)
        return
    if data is None:
        return
    load_conversation(conversation_id, data.get("messages", []))
    go_to("chat")


def _delete(conversation_id: int) -> None:
    error = conv_api.delete_conversation(conversation_id)
    if error:
        st.error(error)
        return
    if st.session_state.get("fk_conversation_id") == conversation_id:
        start_new_conversation()
    st.session_state.pop("fk_pending_delete", None)
    st.toast("Chatten är raderad.")
    st.rerun()


@st.dialog("Byt namn på chatten")
def _rename_dialog(conversation_id: int, current_title: str) -> None:
    with st.form(f"rename_form_{conversation_id}", border=False):
        new_title = st.text_input("Namn", value=current_title, max_chars=60)
        submitted = st.form_submit_button("Spara", type="primary", use_container_width=True)
    if submitted:
        error = conv_api.rename_conversation(conversation_id, new_title)
        if error:
            st.error(error)
            return
        st.toast("Namnet är sparat.")
        st.rerun()


@st.dialog("Radera chatt?")
def _confirm_delete_dialog(conversation_id: int, title: str) -> None:
    st.markdown(f"Vill du radera chatten **{title}**? Den försvinner för gott.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Avbryt", use_container_width=True):
            st.session_state.pop("fk_pending_delete", None)
            st.rerun()
    with c2:
        if st.button("Radera", type="primary", use_container_width=True):
            _delete(conversation_id)


def render() -> None:
    page_header(
        "Sparade chattar",
        "Dina tidigare samtal",
        "Alla chattar du haft med Fickologen – klicka för att fortsätta "
        "eller radera dem du inte längre vill behålla.",
    )

    if not auth.current_user():
        st.info("Logga in för att se dina sparade chattar.")
        return

    with st.spinner("Hämtar dina chattar..."):
        conversations, error = conv_api.list_conversations()
    if error:
        st.error(error)
        return
    if not conversations:
        st.info("Du har inga sparade chattar än. Starta ett samtal på hemsidan när du vill.")
        return

    pending = st.session_state.get("fk_pending_delete")

    for conv in conversations:
        title = conv.get("title") or "Namnlös chatt"
        is_open = st.session_state.get("fk_conversation_id") == conv["id"]
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([6, 2, 1, 1])
            with c1:
                marker = "🟢 " if is_open else ""
                st.markdown(f'<div class="fk-saved-title">{marker}{html.escape(title)}</div>', unsafe_allow_html=True)
                st.caption(f"Senast uppdaterad {_format_dt(conv['updated_at'])}")
            with c2:
                if st.button("Öppna", key=f"open_{conv['id']}", use_container_width=True):
                    _open(conv["id"])
            with c3:
                if st.button("✏️", key=f"conv_edit_{conv['id']}", use_container_width=True, help="Byt namn"):
                    _rename_dialog(conv["id"], conv.get("title") or "")
            with c4:
                if st.button("🗑️", key=f"conv_del_{conv['id']}", use_container_width=True, help="Radera chatten"):
                    st.session_state["fk_pending_delete"] = conv["id"]
                    _confirm_delete_dialog(conv["id"], title)

    # Reopen the dialog if the user navigated inside it and triggered a rerun.
    if pending is not None and st.session_state.get("fk_pending_delete") == pending:
        pass  # dialog already shown above when the button was clicked