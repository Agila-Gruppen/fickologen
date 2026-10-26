"""Admin-sida for kontohantering."""

import streamlit as st

import auth
from api import BackendUnavailable
from components import page_header

BACKEND_ERROR = "Kunde inte nå servern just nu. Försök igen om en liten stund."


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

    if flash := st.session_state.pop("fk_manage_accounts_flash", None):
        st.toast(flash)

    _render_change_password_card()


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

        labels = []
        ids_by_label: dict[str, int] = {}
        usernames_by_label: dict[str, str] = {}

        for user in users:
            role_label = "admin" if user.get("role") == "admin" else "user"
            label = f"{user.get('username', '?')} ({role_label})"
            labels.append(label)
            ids_by_label[label] = int(user["id"])
            usernames_by_label[label] = str(user.get("username", "okänd användare"))

        with st.form("fk_manage_accounts_change_password", border=False):
            chosen_label = st.selectbox("Välj användare", options=labels, key="fk_manage_accounts_target")
            new_password = st.text_input(
                "Nytt lösenord",
                type="password",
                help="Minst 6 tecken.",
                key="fk_manage_accounts_new_password",
            )
            c1, c2 = st.columns(2)
            with c1:
                submitted_ok = st.form_submit_button("OK", type="primary", use_container_width=True)
            with c2:
                submitted_cancel = st.form_submit_button("Avbryt", use_container_width=True)

        if submitted_cancel:
            st.session_state["fk_manage_accounts_new_password"] = ""
            st.rerun()

        if not submitted_ok:
            return

        target_user_id = ids_by_label[chosen_label]

        try:
            error = auth.admin_change_user_password(target_user_id, new_password)
        except BackendUnavailable:
            st.error(BACKEND_ERROR)
            return

        if error:
            st.error(error)
            return

        st.session_state["fk_manage_accounts_new_password"] = ""
        st.session_state["fk_manage_accounts_flash"] = (
            f"Lösenordet för {usernames_by_label[chosen_label]} är uppdaterat. ✓"
        )
        st.rerun()
