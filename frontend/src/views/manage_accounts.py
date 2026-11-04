"""Admin-sida for kontohantering."""

import streamlit as st

import auth
from api import BackendUnavailable
from components import page_header
from datetime_utils import to_local

BACKEND_ERROR = "Kunde inte nå servern just nu. Försök igen om en liten stund."

PASSWORD_KEY = "fk_manage_accounts_new_password"
TARGET_KEY = "fk_manage_accounts_target"
FLASH_KEY = "fk_manage_accounts_flash"
ERROR_KEY = "fk_manage_accounts_error"


def render() -> None:
    page_header(
        "Admin",
        "Hantera konton",
        "Byt lösenord, skicka påminnelser och radera konton.",
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
    st.markdown("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)
    _render_reminders_card()
    st.markdown("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)
    _render_delete_user_card()


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
        f"Lösenordet för {usernames_by_label[chosen_label]} är uppdaterat."
    )


def _render_change_password_card() -> None:
    with st.container(key="fk_card_admin_password"):
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


def _render_reminders_card() -> None:
    with st.container(key="fk_card_admin_reminders"):
        st.markdown('<div class="fk-section-title">Veckopåminnelser</div>', unsafe_allow_html=True)
        st.markdown(
            '<p class="fk-card-text">Varje söndag kväll får alla som går programmet och har '
            "slagit på påminnelser ett mejl om att en ny vecka börjar. Här kan du skicka dem "
            "direkt, t.ex. för att prova. Den som redan fått dagens mejl får inget till.</p>",
            unsafe_allow_html=True,
        )
        if not st.button("Skicka påminnelser nu", key="fk_admin_send_reminders"):
            return
        try:
            result, error = auth.admin_send_reminders()
        except BackendUnavailable:
            st.error(BACKEND_ERROR)
            return
        if error:
            st.error(error)
            return
        message = (
            f"Skickade: {result['sent']} · redan skickade idag: {result['already_sent']} · "
            f"misslyckades: {result['failed']}"
        )
        if result["failed"]:
            st.warning(message + " – se backendens logg.")
        else:
            st.success(message)


DELETE_TARGET_KEY = "fk_admin_delete_target"
DELETE_CONFIRM_KEY = "fk_admin_delete_confirm"
# Bumped after each delete so the user picker starts empty: Streamlit would
# otherwise keep showing the deleted account as selected.
DELETE_ROUND_KEY = "fk_admin_delete_round"


def _render_delete_user_card() -> None:
    with st.container(key="fk_card_admin_delete"):
        st.markdown('<div class="fk-section-title">Radera konto</div>', unsafe_allow_html=True)
        st.markdown(
            '<p class="fk-card-text">Raderar användarens konto och allt som hör till det – '
            "chattar, dagbok och allt i programmet. Det går inte att ångra. Admins kan inte "
            "raderas här, och ditt eget konto raderar du under Mitt konto.</p>",
            unsafe_allow_html=True,
        )

        try:
            users, error = auth.admin_list_users()
        except BackendUnavailable:
            st.error(BACKEND_ERROR)
            return
        if error:
            st.error(error)
            return

        me = (auth.current_user() or {}).get("user_id")
        deletable = [u for u in users or [] if u.get("role") != "admin" and u.get("id") != me]
        if not deletable:
            st.info("Det finns inga användarkonton att radera.")
            return

        by_id = {int(u["id"]): u for u in deletable}
        delete_round = st.session_state.get(DELETE_ROUND_KEY, 0)
        user_id = st.selectbox(
            "Välj användare",
            options=list(by_id),
            format_func=lambda i: f"{by_id[i].get('username', '?')} (ID {i})",
            index=None,
            placeholder="Välj ett konto",
            key=f"{DELETE_TARGET_KEY}_{delete_round}",
        )
        if user_id is None:
            return

        user = by_id[user_id]
        username = str(user.get("username", ""))
        created = to_local(user.get("created_at", ""))
        details = [f"Konto-ID {user_id}"]
        if created:
            details.append(f"skapat {created:%Y-%m-%d}")
        if user.get("email"):
            details.append(f"e-post {user['email']}")
        st.caption(" · ".join(details))

        typed = st.text_input(
            f"Skriv användarnamnet **{username}** för att bekräfta",
            key=f"{DELETE_CONFIRM_KEY}_{user_id}",
        )
        if not st.button(
            "Radera kontot permanent",
            key="fk_admin_delete_user_btn",
            disabled=typed.strip() != username,
            use_container_width=True,
        ):
            return

        try:
            error = auth.admin_delete_user(user_id)
        except BackendUnavailable:
            st.error(BACKEND_ERROR)
            return
        if error:
            st.error(error)
            return
        st.session_state[DELETE_ROUND_KEY] = delete_round + 1
        st.session_state.pop(f"{DELETE_TARGET_KEY}_{delete_round}", None)
        st.session_state.pop(f"{DELETE_CONFIRM_KEY}_{user_id}", None)
        st.session_state[FLASH_KEY] = f"Kontot {username} och all dess data är raderat."
        st.rerun()
