import streamlit as st

from chat_engine import is_unlocked, send_user_message, start_new_conversation
from components import LOGO_MARK, go_to, open_account_dialog

SUGGESTIONS = [
    "Jag vet inte var jag ska börja",
    "Jag känner mig orolig inför något",
    "Något hände idag som jag vill prata om",
]


def render() -> None:
    st.markdown(
        f"""
        <div class="fk-hero">
            <div class="fk-hero-mark">{LOGO_MARK}</div>
            <div class="fk-hero-wordmark">Fickologen</div>
            <h1>Vad vill du prata om idag?</h1>
            <p class="fk-hero-sub">
                Skriv precis som tankarna kommer. Det finns inget rätt sätt att
                börja på, och du styr takten hela vägen.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    prompt_value = _render_composer()
    chosen_chip = _render_chips()

    st.markdown(
        '<div class="fk-composer-hint">Fickologen lyssnar utan att döma – i din takt.</div>',
        unsafe_allow_html=True,
    )

    def _handle_message(text: str) -> None:
        if not is_unlocked():
            open_account_dialog()
            return
        start_new_conversation()
        send_user_message(text)
        go_to("chat")

    if chosen_chip:
        _handle_message(chosen_chip)

    if prompt_value and prompt_value.strip():
        _handle_message(prompt_value)

    # st.markdown('<div class="fk-divider"></div>', unsafe_allow_html=True)
    #
    # _, mid, _ = st.columns([1, 1, 1])
    # with mid:
    #     if st.button("Utforska funktioner", type="secondary", use_container_width=True):
    #         st.session_state["show_features"] = True
    #
    # if st.session_state.get("show_features", False):
    #     _render_feature_overview()


def _render_composer() -> str | None:
    """Enter sends, Shift+Enter makes a new line. In a container so it stays here instead of at the page bottom."""
    with st.container(key="fk_composer"):
        return st.chat_input("Skriv vad du vill prata om…", key="home_prompt")


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
