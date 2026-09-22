"""Shared UI building blocks for the Fickologen prototype."""
import base64
from pathlib import Path

import streamlit as st

ASSETS_DIR = Path(__file__).parent / "assets"

NAV_ITEMS = [
    ("home", "Hem", "🏡"),
    ("chat", "Chatt", "💬"),
    ("diary", "Dagbok", "📓"),
    ("treatment", "Behandling", "🌱"),
    ("history", "Tidigare chattar", "🕰️"),
    ("saved", "Sparade lösningar", "💡"),
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

        links_html = ""
        for key, label, icon in NAV_ITEMS:
            active_class = " active" if key == current else ""
            links_html += (
                f'<a class="fk-nav-link{active_class}" href="?view={key}" target="_self">'
                f'<span class="fk-nav-icon">{icon}</span><span>{label}</span></a>'
            )
        st.markdown(links_html, unsafe_allow_html=True)

        st.markdown('<div class="fk-sidebar-spacer"></div>', unsafe_allow_html=True)
        st.markdown('<div class="fk-sidebar-footer">', unsafe_allow_html=True)
        if st.button("🆘 Behöver du akut stöd?", key="crisis_btn", use_container_width=True):
            _crisis_dialog()
        st.markdown("</div>", unsafe_allow_html=True)


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
