"""Konto-sida: profil, redigera uppgifter, säkerhet och datahantering."""
from datetime import datetime
from typing import Any

import streamlit as st

import auth
import conversations as conv_api
import diary_api
from api import BackendUnavailable
from chat_engine import start_new_conversation
from components import PROFILE_FIELDS, page_header
from datetime_utils import to_local

BACKEND_ERROR = "Kunde inte nå servern just nu. Försök igen om en liten stund."
PROFILE_FIELDS = [
    ("email", "E-post"),
    ("first_name", "Förnamn"),
    ("last_name", "Efternamn"),
    ("birth_year", "Födelseår"),
    ("phone", "Telefon"),
    ("gender", "Kön"),
    ("city", "Ort"),
]

_LABELS = dict(PROFILE_FIELDS)


def render() -> None:
    page_header(
        "Konto",
        "Dina kontouppgifter",
        "Här kan du uppdatera dina uppgifter, byta lösenord och hantera din data.",
    )

    if not auth.current_user():
        st.info("Logga in för att se dina kontouppgifter.")
        return

    if flash := st.session_state.pop("fk_account_flash_main", None):
        st.toast(flash)

    try:
        data, error = auth.my_data()
    except BackendUnavailable:
        st.error(BACKEND_ERROR)
        return
    if error:
        st.error(error)
        return
    if data is None:
        return

    _render_profile_header(data)
    st.markdown("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)
    _render_profile_form(data)
    st.markdown("<div style='height:1.6rem;'></div>", unsafe_allow_html=True)
    _render_security_section()
    st.markdown("<div style='height:1.6rem;'></div>", unsafe_allow_html=True)
    _render_danger_zone()


def _format_member_since(iso: str | None) -> str | None:
    if not iso:
        return None
    dt = to_local(iso)
    return dt.strftime("%Y-%m-%d") if dt else None


def _render_profile_header(data: dict[str, Any]) -> None:
    username = data.get("username") or "?"
    initial = username[:1].upper()
    role = data.get("role", "user")
    member_since = _format_member_since(data.get("created_at"))
    can_chat = data.get("can_chat") or role == "admin"

    with st.container(border=True):
        c1, c2 = st.columns([1, 4], vertical_alignment="center")
        with c1:
            st.markdown(
                f'<div style="width:72px;height:72px;border-radius:50%;background:var(--terracotta-tint);'
                f'color:var(--terracotta);display:flex;align-items:center;justify-content:center;'
                f'font-size:1.9rem;font-weight:700;">{initial}</div>',
                unsafe_allow_html=True,
            )
        with c2:
            role_tag = " 🛡️ Admin" if role == "admin" else ""
            st.markdown(f"### {username}{role_tag}")
            st.caption(f"Konto-ID {data['id']}")
            if member_since:
                st.caption(f"Medlem sedan {member_since}")
            chat_state = "aktiv ✓" if can_chat else "väntar på godkännande"
            st.caption(f"Chatt-tillgång: {chat_state}")


def _render_profile_form(data: dict[str, Any]) -> None:
    st.markdown('<div class="fk-section-title">Personuppgifter</div>', unsafe_allow_html=True)
    current_year = datetime.now().year
    with st.form("fk_account_profile", border=False, clear_on_submit=False):
        email = st.text_input(_LABELS["email"], value=data.get("email") or "")
        c1, c2 = st.columns(2)
        with c1:
            first_name = st.text_input(_LABELS["first_name"], value=data.get("first_name") or "")
        with c2:
            last_name = st.text_input(_LABELS["last_name"], value=data.get("last_name") or "")
        c3, c4 = st.columns(2)
        with c3:
            birth_year = st.number_input(
                _LABELS["birth_year"],
                min_value=1900,
                max_value=current_year,
                value=data.get("birth_year"),
                step=1,
                format="%d",
                placeholder="Lämna tomt om du inte vill ange",
            )
        with c4:
            phone = st.text_input(_LABELS["phone"], value=data.get("phone") or "")
        c5, c6 = st.columns(2)
        with c5:
            gender = st.text_input(_LABELS["gender"], value=data.get("gender") or "")
        with c6:
            city = st.text_input(_LABELS["city"], value=data.get("city") or "")
        submitted = st.form_submit_button("Spara ändringar", type="primary", use_container_width=True)

    if not submitted:
        return

    changes: dict[str, Any] = {}

    def _diff(key: str, new_value: str | int | None) -> None:
        if isinstance(new_value, str):
            new_value = new_value.strip() or None
        if new_value != data.get(key):
            changes[key] = new_value

    _diff("email", email)
    _diff("first_name", first_name)
    _diff("last_name", last_name)
    _diff("birth_year", int(birth_year) if birth_year is not None else None)
    _diff("phone", phone)
    _diff("gender", gender)
    _diff("city", city)

    if not changes:
        st.info("Inget har ändrats.")
        return

    try:
        _, error = auth.update_my_data(changes)
    except BackendUnavailable:
        st.error(BACKEND_ERROR)
        return
    if error:
        st.error(error)
        return
    st.session_state["fk_account_flash_main"] = "Dina uppgifter är sparade. ✓"
    st.rerun()


def _render_security_section() -> None:
    st.markdown('<div class="fk-section-title">Säkerhet</div>', unsafe_allow_html=True)
    _render_change_password()
    st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)
    _render_new_recovery_code()


def _render_change_password() -> None:
    with st.expander("Byt lösenord"):
        with st.form("fk_change_password", border=False):
            current_pw = st.text_input("Nuvarande lösenord", type="password", key="fk_change_pw_current")
            new_pw = st.text_input("Nytt lösenord", type="password", help="Minst 6 tecken.", key="fk_change_pw_new")
            new_pw_again = st.text_input("Upprepa det nya lösenordet", type="password", key="fk_change_pw_again")
            submitted = st.form_submit_button("Byt lösenord", type="primary", use_container_width=True)
        if not submitted:
            return
        try:
            error = auth.change_password(current_pw, new_pw, new_pw_again)
        except BackendUnavailable:
            st.error(BACKEND_ERROR)
            return
        if error:
            st.error(error)
            return
        st.session_state["fk_account_flash_main"] = "Lösenordet är ändrat. ✓"
        st.rerun()


def _render_new_recovery_code() -> None:
    with st.expander("Ny återställningskod"):
        st.markdown(
            '<p class="fk-card-text">Du får en helt ny återställningskod — den gamla slutar fungera. '
            'Den nya visas en gång, så spara den direkt.</p>',
            unsafe_allow_html=True,
        )
        with st.form("fk_new_recovery", border=False):
            current_pw = st.text_input("Nuvarande lösenord", type="password", key="fk_recovery_pw_current")
            submitted = st.form_submit_button(
                "Skapa ny återställningskod", type="primary", use_container_width=True
            )
        if not submitted:
            return
        try:
            error = auth.new_recovery_code(current_pw)
        except BackendUnavailable:
            st.error(BACKEND_ERROR)
            return
        if error:
            st.error(error)
            return
        st.session_state["fk_account_flash_main"] = "En ny återställningskod har skapats."
        st.rerun()


def _count(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _fetch_counts() -> tuple[int | None, int | None]:
    """Return (chat_count, diary_count), or None for each that failed to load."""
    try:
        convs, error = conv_api.list_conversations()
        chat_count: int | None = len(convs) if not error and convs is not None else None
    except BackendUnavailable:
        chat_count = None
    try:
        diary_count: int | None = len(diary_api.list_entries())
    except (diary_api.SessionExpired, BackendUnavailable):
        diary_count = None
    return chat_count, diary_count

def _render_danger_zone() -> None:
    st.markdown(
        '<hr class="fk-divider" /><div class="fk-section-title">Datahantering</div>',
        unsafe_allow_html=True,
    )
    _render_delete_content_section()
    st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)
    _render_delete_account_section()


def _render_delete_content_section() -> None:
    with st.expander("Radera innehåll (behåll kontot)"):
        st.markdown(
            '<p class="fk-card-text">Rensa det du sparat men behåll ditt konto. Det går inte att ångra.</p>',
            unsafe_allow_html=True,
        )

        chat_count, diary_count = _fetch_counts()
        chat_label = f"Alla chattar ({chat_count})" if chat_count is not None else "Alla chattar"
        diary_label = (
            f"Alla dagboksanteckningar ({diary_count})"
            if diary_count is not None
            else "Alla dagboksanteckningar"
        )
        labels = {
            "chats": chat_label,
            "diary": diary_label,
            "all": "Allt innehåll – chattar och dagbok",
        }
        choice = st.radio(
            "Vad vill du radera?",
            options=list(labels),
            format_func=labels.get,
            key="fk_account_delete_choice",
        )
        nothing_to_delete = {
            "chats": chat_count == 0,
            "diary": diary_count == 0,
            "all": chat_count == 0 and diary_count == 0,
        }[choice]
        if nothing_to_delete:
            st.caption("Det finns inget sparat att radera för detta val.")

        confirmed = st.checkbox(
            "Jag förstår att det inte går att ångra", key="fk_account_delete_confirm"
        )
        if not st.button(
            "Radera",
            disabled=not confirmed or nothing_to_delete,
            use_container_width=True,
            key="fk_account_delete_data_btn",
        ):
            return

    message: str | None = None
    error: str | None = None
    try:
        if choice == "chats":
            deleted, error = conv_api.delete_all_conversations()
            if not error and deleted is not None:
                message = f"Raderat: {_count(deleted, 'chatt', 'chattar')}."
        elif choice == "diary":
            deleted_count = diary_api.delete_all_entries()
            message = f"Raderat: {_count(deleted_count, 'dagboksanteckning', 'dagboksanteckningar')}."
        else:
            counts, error = auth.delete_my_content()
            if not error and counts is not None:
                message = (
                    f"Raderat: {_count(counts['conversations'], 'chatt', 'chattar')} och "
                    f"{_count(counts['diary_entries'], 'dagboksanteckning', 'dagboksanteckningar')}."
                )
    except diary_api.SessionExpired:
        error = auth.SESSION_EXPIRED
    except BackendUnavailable:
        error = BACKEND_ERROR

    if error:
        st.error(error)
        return
    if choice in ("chats", "all"):
        start_new_conversation()
    st.session_state["fk_account_flash_main"] = message or "Raderat."
    st.rerun()


def _render_delete_account_section() -> None:
    with st.expander("Radera konto permanent"):
        st.markdown(
            '<p class="fk-card-text">Ditt konto och all tillhörande data raderas för gott. '
            'Det går inte att ångra.</p>',
            unsafe_allow_html=True,
        )
        confirmed = st.checkbox(
            "Jag förstår att det inte går att ångra", key="fk_account_delete_acc_confirm"
        )
        if not st.button(
            "Radera mitt konto",
            disabled=not confirmed,
            use_container_width=True,
            key="fk_account_delete_acc_btn",
        ):
            return
        try:
            error = auth.delete_account()
        except BackendUnavailable:
            st.error(BACKEND_ERROR)
            return
        if error:
            st.error(error)
            return
        st.session_state["fk_account_deleted"] = True
        st.query_params["view"] = "home"
        st.rerun()