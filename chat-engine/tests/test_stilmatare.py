"""Tester för stilmätarens räknare (utan nätverk): chat-engine/stilmatare.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stilmatare import analysera, meningar, upprepade_oppningar  # noqa: E402


def test_tom_lista_ger_tomt_resultat():
    assert analysera([]) == {"antal": 0}


def test_raknar_mönster_och_andelar():
    svar = [
        "Tack för att du frågar! Kort sagt är det en tankefälla. Det är inte ett misslyckande. Hur brukar det vara för dig?",
        "Det är en jättebra fråga. En bra tumregel är att stanna upp.",
        "Tankeläsning är när du tror att du vet vad andra tänker. Vill du ha ett exempel?",
        "Du kände dig nervös. Det låter jobbigt.",
    ]
    res = analysera(svar)
    assert res["antal"] == 4
    assert res["börjar med tack/beröm"] == 0.5
    assert res['"kort sagt"/"det korta svaret"'] == 0.25
    assert res['"misslyckande"'] == 0.25
    assert res['"tumregel"/"konkret verktyg"'] == 0.25
    assert res['börjar med "Du ..." (upprepar)'] == 0.25
    assert res['"det låter jobbigt"'] == 0.25
    assert res['"vill du ha ett exempel"'] == 0.25
    assert res["avslutar med fråga"] == 0.5
    assert res['frågan innehåller "brukar"'] == 0.25


def test_laengd_raknas_i_ord():
    res = analysera(["ett två tre", " ".join(["ord"] * 200)])
    assert res["genomsnitt ord"] == (3 + 200) / 2
    assert res["andel över 150 ord"] == 0.5


def test_upprepade_oppningar_raknar_samma_tre_forsta_orden():
    svar = ["Tankeläsning är när du tror", "Det beror på vad", "Tankeläsning är när hjärnan gissar", "Något helt annat här"]
    assert upprepade_oppningar(svar) == 1
    assert upprepade_oppningar([]) == 0


def test_meningar_delar_vid_skiljetecken():
    assert meningar("Hej! Hur mår du? Bra.") == ["Hej!", "Hur mår du?", "Bra."]


if __name__ == "__main__":
    antal_fel = 0
    tester = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for namn, funktion in tester:
        try:
            funktion()
            print("OK   ", namn)
        except AssertionError as e:
            antal_fel += 1
            print("FEL  ", namn, "->", e)
    print()
    print(f"{len(tester) - antal_fel}/{len(tester)} tester gick igenom")
    sys.exit(1 if antal_fel else 0)
