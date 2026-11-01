"""Password reset via one-time email link.

Shown when the URL carries ?reset=<token>, from the email that
`backend/src/services/password_reset.py` sends out.
"""
import streamlit as st

import auth
from api import BackendUnavailable
from components import go_to, page_header


BACKEND_ERROR = "Kunde inte nå servern just nu. Försök igen om en liten stund."


def render() -> None:
    page_header(
        "Återställ lösenord",
        "Välj ett nytt lösenord",
        "Du har klickat på återställningslänken i mejlet. Välj ett nytt lösenord "
        "nedan – du blir inte inloggad automatiskt, utan loggar in med det nya "
        "lösenordet när du är klar.",
    )

    token = st.query_params.get("reset", "").strip()
    if not token:
        st.error("Länken saknar en giltig återställningstoken.")
        if st.button("Till startsidan", type="primary"):
            _clear_reset_and_go_home()
        return

    with st.container(key="fk_card_password_reset"):
        with st.form("fk_password_reset_form", border=False):
            st.markdown(
                '<p class="fk-card-text">Lösenordet behöver vara minst 6 tecken. '
                "Skriv in det två gånger så vi är säkra på att det är rätt.</p>",
                unsafe_allow_html=True,
            )
            password = st.text_input(
                "Nytt lösenord",
                type="password",
                key="fk_password_reset_new",
                help="Minst 6 tecken.",
            )
            password_again = st.text_input(
                "Upprepa det nya lösenordet",
                type="password",
                key="fk_password_reset_again",
            )
            submitted = st.form_submit_button(
                "Spara nytt lösenord", type="primary", use_container_width=True
            )

    if submitted:
        try:
            error = auth.reset_password_with_token(token, password, password_again)
        except BackendUnavailable:
            st.error(BACKEND_ERROR)
            return
        if error:
            st.warning(error)
            return
        st.success("Ditt lösenord är ändrat. Du kan nu logga in med det nya.")
        _clear_reset_and_go_home()


def _clear_reset_and_go_home() -> None:
    """Remove the one-time token from the URL and open the home page."""
    if "reset" in st.query_params:
        del st.query_params["reset"]
    go_to("home")