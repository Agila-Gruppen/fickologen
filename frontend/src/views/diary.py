from components import page_header, placeholder_module


def render() -> None:
    page_header(
        "Dagbok",
        "Ett ställe för tankarna mellan samtalen",
        "Inget du skriver här behöver vara ordnat eller korrekt – det räcker att "
        "det är sant för dig just nu.",
    )
    placeholder_module(
        icon="📓",
        title="Din dagbok",
        description=(
            "Här kommer du kunna skriva korta eller långa anteckningar, koppla dem "
            "till hur du mådde, och se mönster växa fram över tid – helt i din egen takt."
        ),
        detail=(
            "Vi bygger dagboken så att den känns lika trygg som ett samtal: ingen "
            "bedömning, ingen press att skriva varje dag."
        ),
        cta_key="notify_diary",
    )
