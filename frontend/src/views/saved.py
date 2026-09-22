from components import page_header, placeholder_module


def render() -> None:
    page_header(
        "Sparade lösningar",
        "Det som faktiskt har hjälpt dig",
        "En samling av dina egna insikter – inte generella råd, utan det som "
        "fungerat för just dig.",
    )
    placeholder_module(
        icon="💡",
        title="Dina lösningar",
        description=(
            "När ett samtal leder fram till något som hjälper – en strategi, en "
            "omformulering, ett litet experiment – kommer du kunna spara det här "
            "för att lätt hitta tillbaka."
        ),
        detail="Tanken är att bygga ett eget bibliotek, i dina egna ord.",
        cta_key="notify_saved",
    )
