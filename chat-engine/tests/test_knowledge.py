"""Tester för uppdelningen av kunskapsmaterial (chat-engine/knowledge/chunker.py).

Kör:   python chat-engine/tests/test_knowledge.py
Använder påhittad text, så testerna fungerar utan själva modulerna.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "knowledge"))

from chunker import MAX_WORDS, MIN_WORDS, chunk_markdown, parse_front_matter  # noqa: E402


def ord_text(n, ord_="ord"):
    return " ".join([ord_] * n)


DOK = f"""---
id: modul-99-test
titel: "Modul 99: Test"
modul: 99
källa: "påhittat"
---

# Modul 99

## Begrepp A

{ord_text(120, "alfa")}

### Delbegrepp A1

{ord_text(90, "beta")}

### Delbegrepp A2

{ord_text(60, "gamma")}

## Övning 1: Träna

1. Gör ett.
2. Gör två.

{ord_text(80, "delta")}

## Arbetsblad 1: Blankett

{ord_text(100, "epsilon")}

### Exempel på ifylld rad

{ord_text(70, "zeta")}

## Lång text

{chr(10).join(ord_text(150, "eta") + chr(10) for _ in range(6))}
"""


def test_front_matter_laases_och_tas_bort_fran_texten():
    meta, body = parse_front_matter(DOK)
    assert meta["id"] == "modul-99-test" and meta["modul"] == "99"
    assert body.startswith("# Modul 99")


def test_varje_bit_far_rubrikvag_foerst_i_texten():
    chunks = chunk_markdown(DOK)
    a1 = next(c for c in chunks if c.path == ["Begrepp A", "Delbegrepp A1"])
    assert a1.text.startswith("Modul 99: Test > Begrepp A > Delbegrepp A1\n\n")


def test_korta_avsnitt_slas_ihop_med_naesta():
    chunks = chunk_markdown(DOK)
    # A2 (60 ord) är över gränsen, men ett avsnitt under MIN_WORDS ska aldrig bli en egen bit
    assert all(c.words >= MIN_WORDS for c in chunks)
    kort = chunk_markdown("---\nid: x\n---\n\n## Kort\n\nbara ett par ord\n\n## Lång\n\n" + ord_text(100))
    assert len(kort) == 1 and "bara ett par ord" in kort[0].text and "Lång" in kort[0].text


def test_laanga_avsnitt_delas_vid_styckegraenser():
    chunks = [c for c in chunk_markdown(DOK) if c.path == ["Lång text"]]
    assert len(chunks) >= 2
    assert all(c.words <= MAX_WORDS for c in chunks)
    assert chunks[1].id.endswith("-2")


def test_arbetsblad_indexeras_inte_men_oevningar_gor_det():
    chunks = chunk_markdown(DOK)
    assert not any("arbetsblad" in " ".join(c.path).lower() for c in chunks)
    ovning = next(c for c in chunks if c.path == ["Övning 1: Träna"])
    assert ovning.typ == "övning" and "1. Gör ett." in ovning.text


def test_id_ar_unika_och_stabila():
    ids = [c.id for c in chunk_markdown(DOK)]
    assert len(ids) == len(set(ids))
    assert ids == [c.id for c in chunk_markdown(DOK)]
    assert ids[0].startswith("modul-99-test#")


def test_tom_fil_och_fil_utan_rubriker_kraschar_inte():
    assert chunk_markdown("") == []
    enda = chunk_markdown("---\nid: y\n---\n\n" + ord_text(60))
    assert len(enda) == 1 and enda[0].id == "y#intro"


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
    print(f"\n{len(tester) - antal_fel}/{len(tester)} tester gick igenom")
    sys.exit(1 if antal_fel else 0)
