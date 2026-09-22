from components import page_header, placeholder_module


def render() -> None:
    page_header(
        "Tidigare chattar",
        "Gå tillbaka när du vill påminna dig",
        "Ibland är det värdefullt att läsa sina egna ord igen, med lite distans.",
    )
    placeholder_module(
        icon="🕰️",
        title="Din historik",
        description=(
            "Här kommer dina tidigare samtal att samlas, sökbara och sorterade "
            "efter datum, så att du enkelt kan gå tillbaka till ett resonemang."
        ),
        detail="Du bestämmer alltid själv vad som sparas och vad som raderas.",
        cta_key="notify_history",
    )
