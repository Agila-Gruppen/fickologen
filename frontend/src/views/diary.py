import html
from datetime import datetime

import streamlit as st

import auth
import diary_api
from api import BackendUnavailable
from components import open_account_dialog, page_header

MOODS = {
    1: "😞 Tungt",
    2: "🙁 Lite tungt",
    3: "😐 Okej",
    4: "🙂 Ganska bra",
    5: "😊 Bra",
}

WEEKDAYS = ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"]
MONTHS = [
    "januari", "februari", "mars", "april", "maj", "juni",
    "juli", "augusti", "september", "oktober", "november", "december",
]

BACKEND_ERROR = "Kunde inte nå servern just nu. Försök igen om en liten stund."


def render() -> None:
    page_header(
        "Dagbok",
        "Ett ställe för tankarna mellan samtalen",
        "Inget du skriver här behöver vara ordnat eller korrekt – det räcker att "
        "det är sant för dig just nu.",
    )

    if not auth.current_user():
        _render_logged_out()
        return

    # Set before an st.rerun(), shown here once the page has redrawn.
    if flash := st.session_state.pop("fk_diary_flash", None):
        st.toast(flash)

    try:
        _render_composer()
        _render_entries(diary_api.list_entries())
    except diary_api.SessionExpired:
        st.error(auth.SESSION_EXPIRED)
    except BackendUnavailable:
        st.error(BACKEND_ERROR)


def _render_logged_out() -> None:
    st.markdown(
        """
        <div class="fk-card">
            <span class="fk-card-icon">📓</span>
            <div class="fk-card-title">Din dagbok</div>
            <p class="fk-card-text">
                Dagboken sparas på ditt konto, så att du kan komma tillbaka till den.
                Logga in eller skapa ett konto för att börja skriva – du behöver inte
                uppge vem du är.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Logga in / skapa konto", key="diary_login_btn", type="primary"):
        open_account_dialog()


def _mood_picker(key: str, default: int | None = None) -> int | None:
    return st.segmented_control(
        "Hur mår du? (valfritt)",
        options=list(MOODS),
        format_func=lambda m: MOODS[m],
        default=default,
        key=key,
    )


def _render_composer() -> None:
    with st.container(key="fk_diary_composer"):
        st.markdown('<div class="fk-card-title">Skriv något nytt</div>', unsafe_allow_html=True)
        with st.form("fk_diary_new", border=False, clear_on_submit=True):
            title = st.text_input("Rubrik (valfri)", max_chars=200)
            content = st.text_area(
                "Anteckning",
                height=160,
                placeholder="Vad har du i tankarna just nu?",
                label_visibility="collapsed",
            )
            mood = _mood_picker("fk_diary_new_mood")
            submitted = st.form_submit_button("Spara anteckning", type="primary")
        if submitted:
            if not content.strip():
                st.warning("Skriv något i anteckningen innan du sparar.")
                return
            diary_api.create_entry(title.strip(), content.strip(), mood)
            st.toast("Anteckningen är sparad. 🌱")


def _render_entries(entries: list[dict]) -> None:
    st.markdown('<div class="fk-section-title">Dina anteckningar</div>', unsafe_allow_html=True)
    if not entries:
        st.markdown(
            '<p class="fk-chat-intro" style="text-align:left;">'
            "Inga anteckningar än – det du skriver hamnar här.</p>",
            unsafe_allow_html=True,
        )
        return

    for entry in entries:
        if st.session_state.get("fk_diary_editing") == entry["id"]:
            _render_edit_form(entry)
        else:
            _render_entry(entry)


def _format_date(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    return f"{WEEKDAYS[dt.weekday()].capitalize()} {dt.day} {MONTHS[dt.month - 1]} {dt.year}, {dt:%H:%M}"


def _render_entry(entry: dict) -> None:
    entry_id = entry["id"]
    mood = f'<span class="fk-diary-mood">{MOODS[entry["mood"]]}</span>' if entry.get("mood") in MOODS else ""
    title = f'<div class="fk-card-title">{html.escape(entry["title"])}</div>' if entry.get("title") else ""
    # <br> rather than raw newlines: a blank line would end the HTML block and
    # let markdown take over the rest of the text.
    content = html.escape(entry["content"]).replace("\r\n", "\n").replace("\n", "<br>")
    st.markdown(
        '<div class="fk-diary-entry">'
        f'<div class="fk-diary-meta"><span>{_format_date(entry["created_at"])}</span>{mood}</div>'
        f'{title}'
        f'<div class="fk-diary-content">{content}</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.get("fk_diary_deleting") == entry_id:
        st.markdown(
            '<p class="fk-card-text">Vill du radera anteckningen? Det går inte att ångra.</p>',
            unsafe_allow_html=True,
        )
        yes, no, _ = st.columns([1.3, 1, 2])
        if yes.button("Ja, radera", key=f"diary_confirmdelete_{entry_id}", use_container_width=True):
            diary_api.delete_entry(entry_id)
            st.session_state.pop("fk_diary_deleting", None)
            st.session_state["fk_diary_flash"] = "Anteckningen är raderad."
            st.rerun()
        if no.button("Avbryt", key=f"diary_canceldelete_{entry_id}", use_container_width=True):
            st.session_state.pop("fk_diary_deleting", None)
            st.rerun()
    else:
        edit, delete, _ = st.columns([1, 1, 3])
        if edit.button("Redigera", key=f"diary_edit_{entry_id}", use_container_width=True):
            st.session_state["fk_diary_editing"] = entry_id
            st.session_state.pop("fk_diary_deleting", None)
            st.rerun()
        if delete.button("Radera", key=f"diary_delete_{entry_id}", use_container_width=True):
            st.session_state["fk_diary_deleting"] = entry_id
            st.rerun()
    st.markdown('<div style="height:0.8rem;"></div>', unsafe_allow_html=True)


def _render_edit_form(entry: dict) -> None:
    entry_id = entry["id"]
    with st.container(key=f"fk_diary_editbox_{entry_id}"):
        with st.form(f"fk_diary_edit_{entry_id}", border=False):
            title = st.text_input("Rubrik (valfri)", value=entry.get("title") or "", max_chars=200)
            content = st.text_area("Anteckning", value=entry["content"], height=160)
            mood = _mood_picker(f"fk_diary_edit_mood_{entry_id}", entry.get("mood"))
            save, cancel, _ = st.columns([1, 1, 2])
            saved = save.form_submit_button("Spara", type="primary", use_container_width=True)
            cancelled = cancel.form_submit_button("Avbryt", use_container_width=True)
    if cancelled:
        st.session_state.pop("fk_diary_editing", None)
        st.rerun()
    if saved:
        content_text = content or ""
        if not content_text.strip():
            st.warning("Anteckningen kan inte vara tom.")
            return
        diary_api.update_entry(entry_id, title.strip(), content_text.strip(), mood)
        st.session_state.pop("fk_diary_editing", None)
        st.session_state["fk_diary_flash"] = "Ändringarna är sparade."
        st.rerun()
