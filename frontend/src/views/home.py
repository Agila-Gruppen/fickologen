import streamlit as st

from chat_engine import send_user_message
from components import go_to, logo_data_uri

SUGGESTIONS = [
    "Jag vet inte var jag ska börja",
    "Jag känner mig orolig inför något",
    "Något hände idag som jag vill prata om",
]


def render() -> None:
    st.markdown('<div class="fk-glow"></div>', unsafe_allow_html=True)
    # Rendered as its own markdown block: bundling it with the <h1> below causes
    # Streamlit's heading-anchor processing to silently drop this <img>.
    st.markdown(
        f'<img src="{logo_data_uri()}" class="fk-hero-logo" alt="Fickologen" />',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="fk-hero">
            <div class="fk-hero-eyebrow">Fickologen</div>
            <h1>Vad vill du prata om idag?</h1>
            <p class="fk-hero-sub">
                Skriv precis som tankarna kommer. Det finns inget rätt sätt att
                börja på, och du styr takten hela vägen.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    submitted, prompt_value = _render_composer()

    st.markdown(
        '<div class="fk-composer-hint">Fickologen lyssnar utan att döma – i din takt.</div>',
        unsafe_allow_html=True,
    )

    chosen_chip = _render_chips()

    if chosen_chip:
        send_user_message(chosen_chip)
        go_to("chat")

    if submitted and prompt_value and prompt_value.strip():
        send_user_message(prompt_value)
        go_to("chat")

    st.markdown('<div class="fk-divider"></div>', unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 1, 1])
    with mid:
        if st.button("Utforska funktioner", type="secondary", use_container_width=True):
            st.session_state["show_features"] = True

    if st.session_state.get("show_features", False):
        _render_feature_overview()


def _render_composer():
    with st.container(key="fk_composer"):
        with st.form("fk_composer_form", clear_on_submit=True, border=False):
            c1, c2 = st.columns([9, 1], vertical_alignment="center")
            with c1:
                prompt_value = st.text_area(
                    "prompt",
                    key="home_prompt",
                    placeholder="Skriv vad du vill prata om…",
                    label_visibility="collapsed",
                    height=68,
                )
            with c2:
                submitted = st.form_submit_button("➤", use_container_width=True)
    return submitted, prompt_value


def _render_chips():
    chosen = None
    with st.container(key="fk_chips_row", horizontal=True, horizontal_alignment="center", gap="small"):
        for i, text in enumerate(SUGGESTIONS):
            if st.button(text, key=f"fk_chip_{i}"):
                chosen = text
    return chosen


def _render_feature_overview() -> None:
    st.markdown('<div class="fk-section-title">Vad mer finns här</div>', unsafe_allow_html=True)

    features = [
        ("📓", "Dagbok", "Fånga tankar och mönster mellan samtalen, i din egen takt."),
        ("🌱", "Behandling – 9 veckor", "Ett strukturerat program som byggs stegvis tillsammans med dig."),
        ("🕰️", "Tidigare chattar", "Gå tillbaka och läsa vad ni pratat om, när du vill påminna dig."),
        ("💡", "Sparade lösningar", "Samla insikter och strategier som faktiskt fungerat för dig."),
    ]

    cols = st.columns(2)
    for i, (icon, title, desc) in enumerate(features):
        with cols[i % 2]:
            st.markdown(
                f"""
                <div class="fk-card" style="padding:1.3rem 1.4rem;">
                    <span class="fk-card-icon" style="font-size:1.4rem;">{icon}</span>
                    <div class="fk-card-title" style="font-size:1.02rem;">{title}</div>
                    <p class="fk-card-text" style="font-size:0.87rem;">{desc}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
