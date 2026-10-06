"""Shared UI building blocks for the Fickologen prototype."""
import base64
import html
from pathlib import Path

import streamlit as st

import auth
from api import BackendUnavailable

ASSETS_DIR = Path(__file__).parent / "assets"

NAV_ITEMS = [
    ("home", "Hem", "🏡"),
    ("chat", "Chatt", "💬"),
    # ("diary", "Dagbok", "📓"),
    # ("treatment", "Behandling", "🌱"),
    # ("history", "Tidigare chattar", "🕰️"),
    # ("saved", "Sparade lösningar", "💡"),
    ("safety", "Trygghet & integritet", "🛡️"),
]

CRISIS_RESOURCES = [
    ("112", "Vid akut fara för liv – ring alltid 112."),
    ("1177", "Sjukvårdsrådgivning dygnet runt, för råd som inte är livshotande."),
    ("Mind Självmordslinjen", "90101 eller chatt på mind.se – för dig i kris, dygnet runt."),
    ("Jourhavande medmänniska", "08-702 16 80, kl. 21–06 – någon att prata med när natten är svår."),
]


def load_css() -> None:
    css_path = ASSETS_DIR / "style.css"
    st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def logo_data_uri() -> str:
    encoded = base64.b64encode((ASSETS_DIR / "logo-mark.png").read_bytes()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def logo_path() -> Path:
    return ASSETS_DIR / "logo-mark.png"


def get_current_view() -> str:
    valid = {key for key, _, _ in NAV_ITEMS}
    view = st.query_params.get("view", "home")
    return view if view in valid else "home"


def go_to(view: str) -> None:
    st.query_params["view"] = view
    st.rerun()


@st.dialog("Behöver du akut stöd?")
def _crisis_dialog() -> None:
    st.markdown(
        "Om du befinner dig i en akut kris eller känner dig osäker på din säkerhet "
        "just nu, är det viktigt att du får hjälp direkt av någon som kan finnas "
        "på riktigt vid din sida. Fickologen är inte en akutresurs och ersätter "
        "inte vård."
    )
    for label, desc in CRISIS_RESOURCES:
        st.markdown(
            f"""<div class="fk-card" style="padding:1.1rem 1.3rem; margin-bottom:0.7rem;">
                <div style="font-weight:600; color:var(--terracotta); margin-bottom:0.2rem;">{label}</div>
                <div style="color:var(--text-muted); font-size:0.9rem;">{desc}</div>
            </div>""",
            unsafe_allow_html=True,
        )
    st.caption("Du är inte ensam om det här, även om det känns så just nu.")


def _submit_account_form(action, *args) -> None:
    """Run a log in / sign up action and show its outcome inside the dialog."""
    try:
        error = action(*args)
    except BackendUnavailable:
        st.error("Kunde inte nå servern just nu. Försök igen om en liten stund.")
        return
    if error:
        st.error(error)
        return
    st.rerun()


@st.dialog("Ditt konto")
def _account_dialog() -> None:
    login_tab, signup_tab = st.tabs(["Logga in", "Skapa konto"])

    with login_tab:
        with st.form("fk_login_form", border=False):
            username = st.text_input("Användarnamn", key="fk_login_username")
            password = st.text_input("Lösenord", type="password", key="fk_login_password")
            submitted = st.form_submit_button("Logga in", type="primary", use_container_width=True)
        if submitted:
            _submit_account_form(auth.log_in, username, password)

    with signup_tab:
        with st.form("fk_signup_form", border=False):
            username = st.text_input(
                "Användarnamn",
                key="fk_signup_username",
                help="3–50 tecken: bokstäver, siffror och understreck.",
            )
            password = st.text_input(
                "Lösenord",
                type="password",
                key="fk_signup_password",
                help="Minst 6 tecken.",
            )
            password_again = st.text_input("Upprepa lösenordet", type="password", key="fk_signup_password_again")
            submitted = st.form_submit_button("Skapa konto", type="primary", use_container_width=True)
        if submitted:
            _submit_account_form(auth.sign_up, username, password, password_again)


def _render_account() -> None:
    """Account box at the bottom of the sidebar (pinned there by the CSS)."""
    user = auth.current_user()
    with st.container(key="fk_account"):
        if user:
            username = html.escape(user["username"])
            st.markdown(
                f"""
                <div class="fk-account">
                    <span class="fk-account-avatar">{username[:1].upper()}</span>
                    <span class="fk-account-text">
                        <span class="fk-account-label">Inloggad som</span>
                        <span class="fk-account-name">{username}</span>
                        <span class="fk-account-label">Konto-ID {user["user_id"]}</span>
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Logga ut", key="logout_btn", use_container_width=True):
                auth.log_out()
                st.rerun()
        else:
            st.markdown(
                """
                <div class="fk-account">
                    <span class="fk-account-avatar">?</span>
                    <span class="fk-account-text">
                        <span class="fk-account-name">Inte inloggad</span>
                        <span class="fk-account-label">Logga in eller skapa ett konto</span>
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Logga in / skapa konto", key="login_btn", use_container_width=True):
                _account_dialog()


def render_sidebar() -> None:
    current = get_current_view()
    with st.sidebar:
        st.markdown(
            f"""
            <div class="fk-brand">
                <img src="{logo_data_uri()}" class="fk-brand-mark" alt="Fickologen" />
                <span class="fk-brand-text">
                    <span class="fk-brand-title">Fickologen</span>
                    <span class="fk-brand-tagline">Din trygga plats att tänka högt</span>
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Buttons rather than <a href> links: a link reloads the page, which
        # starts a new Streamlit session and wipes the chat and its unlock.
        for key, label, icon in NAV_ITEMS:
            state = "navactive" if key == current else "nav"
            if st.button(label, icon=icon, key=f"{state}_{key}", use_container_width=True):
                go_to(key)

        st.markdown('<div class="fk-sidebar-spacer"></div>', unsafe_allow_html=True)
        st.markdown('<div class="fk-sidebar-footer">', unsafe_allow_html=True)
        if st.button("🆘 Behöver du akut stöd?", key="crisis_btn", use_container_width=True):
            _crisis_dialog()
        st.markdown("</div>", unsafe_allow_html=True)

        _render_account()


def page_header(eyebrow: str, title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div style="margin-bottom: 1.6rem;">
            <div class="fk-hero-eyebrow" style="text-align:left;">{eyebrow}</div>
            <h1 style="font-size:2rem; margin-bottom:0.5rem;">{title}</h1>
            {f'<p style="color:var(--text-muted); font-size:1rem; line-height:1.65; max-width:560px;">{subtitle}</p>' if subtitle else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def placeholder_module(icon: str, title: str, description: str, detail: str, cta_key: str) -> None:
    st.markdown(
        f"""
        <div class="fk-card">
            <span class="fk-card-icon">{icon}</span>
            <div class="fk-badge">Kommer snart</div>
            <div class="fk-card-title">{title}</div>
            <p class="fk-card-text">{description}</p>
            <p class="fk-card-text" style="font-size:0.87rem;">{detail}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Säg till när det är klart", key=cta_key):
        st.toast("Tack! Vi hör av oss så snart det är redo. 🌱")
