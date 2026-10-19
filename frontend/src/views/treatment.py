import streamlit as st

from components import page_header, placeholder_module


def render() -> None:
    page_header(
        "Behandling",
        "Ett program i nio veckor",
        "Strukturerat, men aldrig snabbare än vad som känns hanterbart för dig.",
    )

    weeks_html = "".join(
        f'<div class="fk-week{" fk-week-active" if i == 1 else ""}">{i}</div>'
        for i in range(1, 10)
    )
    st.markdown(
        f"""
        <div class="fk-card">
            <span class="fk-card-icon">🌱</span>
            <div class="fk-badge">Kommer snart</div>
            <div class="fk-card-title">Ditt 9-veckorsprogram</div>
            <p class="fk-card-text">
                Programmet byggs stegvis utifrån var du befinner dig, med en tydlig
                struktur men gott om utrymme att gå i din egen takt.
            </p>
            <div class="fk-timeline">{weeks_html}</div>
            <p class="fk-card-text" style="font-size:0.82rem; margin-top:0.8rem;">
                Vecka 1 av 9 – resten låses upp allt eftersom.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Säg till när det är klart", key="notify_treatment"):
        st.toast("Tack! Vi hör av oss så snart programmet är redo. 🌱")
