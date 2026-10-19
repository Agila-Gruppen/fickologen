import streamlit as st

from components import page_header

SECTIONS = [
    (
        "Vad Fickologen är till för",
        "Fickologen är byggt för att ge dig ett lugnt, tillgängligt utrymme att "
        "sätta ord på tankar och känslor mellan – eller istället för – andra "
        "samtal. Målet är aldrig att ersätta mänsklig kontakt, utan att göra det "
        "lite lättare att tänka klart och känna sig mindre ensam med det som pågår.",
    ),
    (
        "Vad Fickologen inte är",
        "Fickologen är inte en akutresurs och gör inga medicinska bedömningar. "
        "Vid akut fara för liv eller hälsa, kontakta alltid 112 eller din "
        "vårdgivare. Se knappen \"Behöver du akut stöd?\" i menyn för fler vägar "
        "att få hjälp direkt.",
    ),
    (
        "Hur vi hanterar dina uppgifter",
        "Det du skriver behandlas varsamt och delas aldrig vidare i syfte att "
        "identifiera dig. Du kommer alltid kunna se, exportera och radera din "
        "data. Vi samlar bara in det som behövs för att Fickologen ska kunna "
        "fungera för dig.",
    ),
    (
        "Din kontroll",
        "Du väljer själv vad du delar, i vilken takt, och när du vill pausa eller "
        "avsluta ett samtal. Inget krävs av dig här – varken svar, tempo eller "
        "riktning.",
    ),
    (
        "Hur vi tänker kring bedömning",
        "Fickologen är byggt för att vara icke-dömande. Reaktioner, strategier "
        "och motstånd behandlas som begripliga – inte som fel som ska rättas till "
        "i första hand, utan som något att förstå tillsammans.",
    ),
]


def render() -> None:
    page_header(
        "Trygghet & integritet",
        "Så tänker vi kring dig och din data",
        "",
    )

    for title, text in SECTIONS:
        _section(title, text)


def _section(title: str, text: str) -> None:
    st.markdown(
        f"""
        <div class="fk-safety-section">
            <h3>{title}</h3>
            <p>{text}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
