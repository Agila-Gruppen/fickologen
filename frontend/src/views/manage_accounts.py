"""Admin-sida for kontohantering."""

import streamlit as st

import auth
from api import BackendUnavailable
from components import page_header

BACKEND_ERROR = "Kunde inte nå servern just nu. Försök igen om en liten stund."

PASSWORD_KEY = "fk_manage_accounts_new_password"
TARGET_KEY = "fk_manage_accounts_target"
FLASH_KEY = "fk_manage_accounts_flash"
ERROR_KEY = "fk_manage_accounts_error"


def render() -> None:
    page_header(
        "Admin",
        "Hantera konton",
        "Byt lösenord för användare och admins.",
    )

    if not auth.current_user():
        st.info("Logga in för att hantera konton.")
        return

    if not auth.is_admin():
        st.error("Du behöver adminbehörighet för att se den här sidan.")
        return

    if flash := st.session_state.pop(FLASH_KEY, None):
        st.toast(flash)

    _render_change_password_card()


def _on_cancel() -> None:
    st.session_state[PASSWORD_KEY] = ""
    st.session_state.pop(ERROR_KEY, None)


def _on_submit(ids_by_label: dict[str, int], usernames_by_label: dict[str, str]) -> None:
    chosen_label = st.session_state.get(TARGET_KEY)
    new_password = st.session_state.get(PASSWORD_KEY, "")

    if chosen_label not in ids_by_label:
        st.session_state[ERROR_KEY] = "Välj en användare."
        return

    try:
        error = auth.admin_change_user_password(ids_by_label[chosen_label], new_password)
    except BackendUnavailable:
        st.session_state[ERROR_KEY] = BACKEND_ERROR
        return

    if error:
        st.session_state[ERROR_KEY] = error
        return

    st.session_state[PASSWORD_KEY] = ""
    st.session_state.pop(ERROR_KEY, None)
    st.session_state[FLASH_KEY] = (
        f"Lösenordet för {usernames_by_label[chosen_label]} är uppdaterat. ✓"
    )


def _render_change_password_card() -> None:
    with st.container(border=True):
        st.markdown('<div class="fk-section-title">Ändra lösenord</div>', unsafe_allow_html=True)

        try:
            users, error = auth.admin_list_users()
        except BackendUnavailable:
            st.error(BACKEND_ERROR)
            return

        if error:
            st.error(error)
            return

        if not users:
            st.info("Inga användare hittades.")
            return

        labels: list[str] = []
        ids_by_label: dict[str, int] = {}
        usernames_by_label: dict[str, str] = {}

        for user in users:
            role_label = "admin" if user.get("role") == "admin" else "user"
            label = f"{user.get('username', '?')} ({role_label})"
            labels.append(label)
            ids_by_label[label] = int(user["id"])
            usernames_by_label[label] = str(user.get("username", "okänd användare"))

        if form_error := st.session_state.pop(ERROR_KEY, None):
            st.error(form_error)

        with st.form("fk_manage_accounts_change_password", border=False):
            st.selectbox("Välj användare", options=labels, key=TARGET_KEY)
            st.text_input(
                "Nytt lösenord",
                type="password",
                help="Minst 6 tecken.",
                key=PASSWORD_KEY,
            )
            c1, c2 = st.columns(2)
            with c1:
                st.form_submit_button(
                    "OK",
                    type="primary",
                    use_container_width=True,
                    on_click=_on_submit,
                    args=(ids_by_label, usernames_by_label),
                )
            with c2:
                st.form_submit_button(
                    "Avbryt",
                    use_container_width=True,
                    on_click=_on_cancel,
                )