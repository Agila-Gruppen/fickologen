"""Tester för kunskapssökningen (PLAN-113): krypterat paket, sökning, inläggning och backendkoppling.

Kör från repots rot:   python chat-engine/tests/test_retrieval.py
Använder fejkade vektorer och en påhittad nyckel: inget nätverk, ingen Gemini-kvot, inget riktigt material.
"""
import logging
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for p in (REPO, REPO / "chat-engine", REPO / "chat-engine" / "knowledge"):
    sys.path.insert(0, str(p))
logging.disable(logging.CRITICAL)

import knowledge_retriever  # noqa: E402
import knowledge_store  # noqa: E402
import ingest  # noqa: E402
import evaluate  # noqa: E402
from chunker import chunk_markdown  # noqa: E402

KEY = knowledge_store.new_key()
RECORDS = [
    {"id": "modul-03-test#tankelasning", "source": "Modul 3: Test > Tankeläsning", "text": "Tankeläsning är att tro att man vet vad andra tänker.", "typ": "begrepp"},
    {"id": "modul-05-test#exponering", "source": "Modul 5: Test > Exponering", "text": "Exponering är att närma sig det som är svårt.", "typ": "begrepp"},
    {"id": "modul-08-test#nej", "source": "Modul 8: Test > Säga nej", "text": "Be om tid innan du svarar.", "typ": "begrepp"},
]
VECTORS = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def store():
    return knowledge_store.unpack(knowledge_store.pack(RECORDS, VECTORS, "fejk", KEY), KEY)


def test_paketet_ar_krypterat_och_oeppnas_bara_med_ratt_nyckel():
    blob = knowledge_store.pack(RECORDS, VECTORS, "fejk", KEY)
    assert b"Tankel" not in blob and "närma sig" .encode() not in blob  # ingen läsbar text
    assert knowledge_store.unpack(blob, KEY).records == RECORDS
    try:
        knowledge_store.unpack(blob, knowledge_store.new_key())
    except Exception:
        return
    raise AssertionError("fel nyckel borde ge fel")


def test_soekning_ger_baesta_traeff_foerst_och_respekterar_k_och_troeskel():
    s = store()
    traffar = s.search([0.9, 0.1, 0.0], k=2, min_score=0.0)
    assert [r["id"] for _, r in traffar] == ["modul-03-test#tankelasning", "modul-05-test#exponering"]
    assert [r["id"] for _, r in s.search([0.9, 0.1, 0.0], k=3, min_score=0.5)] == ["modul-03-test#tankelasning"]
    assert s.search([1.0, 0.0, 0.0], k=1)[0][0] > 0.99


def test_vektorer_normaliseras_sa_att_laengd_inte_spelar_roll():
    assert store().search([50.0, 0.0, 0.0], k=1)[0][0] > 0.99


def test_fel_vektorlaengd_ger_fel():
    try:
        store().search([1.0, 0.0], k=1)
    except ValueError:
        return
    raise AssertionError("borde ge ValueError")


def test_retrieve_ger_traeffar_med_kaella_och_text_utan_rubrikvaeg():
    hits = knowledge_retriever.retrieve("vad är tankeläsning", store=store(), embed_fn=lambda q: [1.0, 0.0, 0.0])
    assert len(hits) == 1 and hits[0].source == "Modul 3: Test > Tankeläsning"
    assert hits[0].text.startswith("Tankeläsning är")


def test_retrieve_ger_inget_vid_svag_traeff_saknat_paket_tom_fraga_eller_fel():
    svag = knowledge_retriever.retrieve("orelaterat", store=store(), embed_fn=lambda q: [0.5, 0.5, 0.5])
    assert svag == []  # alla poäng ~0,58 < MIN_SCORE
    assert knowledge_retriever.retrieve("x", store=None, embed_fn=lambda q: [1, 0, 0]) in ([], )  # inget paket
    assert knowledge_retriever.retrieve("   ", store=store(), embed_fn=lambda q: [1.0, 0.0, 0.0]) == []

    def trasig(q):
        raise RuntimeError("Gemini nere")
    assert knowledge_retriever.retrieve("fråga", store=store(), embed_fn=trasig) == []


def test_load_store_ger_none_om_fil_eller_nyckel_saknas_eller_ar_fel():
    with tempfile.TemporaryDirectory() as d:
        fil = Path(d) / "material.enc"
        assert knowledge_store.load_store(fil, KEY) is None            # filen saknas
        fil.write_bytes(knowledge_store.pack(RECORDS, VECTORS, "fejk", KEY))
        assert knowledge_store.load_store(fil, KEY) is not None
        assert knowledge_store.load_store(fil, knowledge_store.new_key()) is None  # fel nyckel
        import os
        gammal = os.environ.pop("KNOWLEDGE_KEY", None)
        try:
            assert knowledge_store.load_store(fil, None) is None       # ingen nyckel
        finally:
            if gammal:
                os.environ["KNOWLEDGE_KEY"] = gammal


def test_inlaeggning_anvaender_cache_och_provar_igen_vid_fel():
    anrop, cache = [], {}

    def embed(text):
        anrop.append(text)
        if len(anrop) == 1:
            raise RuntimeError("kvot")  # första försöket misslyckas
        return [float(len(text)), 1.0]

    vektorer = ingest.embed_all(["aa", "bbb", "aa"], embed, cache, sleep=lambda s: None)
    assert vektorer[0] == vektorer[2] == [2.0, 1.0] and vektorer[1] == [3.0, 1.0]
    assert anrop == ["aa", "aa", "bbb"]  # ett omförsök, och "aa" återanvänds ur cachen
    assert ingest.embed_all(["aa", "bbb"], lambda t: 1 / 0, cache, sleep=lambda s: None)  # allt ur cachen


def test_inlaeggning_ger_upp_efter_max_foersoek():
    def alltid_fel(text):
        raise RuntimeError("kvot")
    try:
        ingest.embed_all(["a"], alltid_fel, {}, sleep=lambda s: None)
    except RuntimeError:
        return
    raise AssertionError("borde ge upp")


def test_poster_far_kaella_med_rubrikvaeg_och_text_utan():
    md = "---\nid: modul-03-t\ntitel: \"Modul 3: T\"\n---\n\n## Tankefällor\n\n### Tankeläsning\n\n" + "ord " * 60
    post = ingest.to_records(chunk_markdown(md))[0]
    assert post["source"] == "Modul 3: T > Tankefällor > Tankeläsning"
    assert post["text"].startswith("ord") and "Tankeläsning" not in post["text"]


def test_utvaerderingen_raeknar_traeff_och_foreslar_troeskel():
    frågor = [
        {"fråga": "tankeläsning?", "moduler": [3], "rubrik": "Tankeläsning"},
        {"fråga": "pannkakor?", "moduler": [], "rubrik": ""},
    ]
    vektor = {"tankeläsning?": [1.0, 0.0, 0.0], "pannkakor?": [0.5, 0.5, 0.5]}
    rapport = evaluate.evaluate(frågor, store(), lambda q: vektor[q])
    assert rapport["träff"] == 1 and rapport["relevanta"] == 1
    assert 0.0 < rapport["förslag_min_score"] < 1.0


def test_backendens_retrieve_context_oeversaetter_traeffar_och_sluker_fel():
    from backend.src.services import retrieval
    original = knowledge_retriever.retrieve
    try:
        knowledge_retriever.retrieve = lambda q, k=4: [knowledge_retriever.Hit(0.9, "id", "Modul 3: T > A", "text", "begrepp")]
        chunks = retrieval.retrieve_context("fråga")
        assert [(c.source, c.text) for c in chunks] == [("Modul 3: T > A", "text")]

        def trasig(q, k=4):
            raise RuntimeError("fel")
        knowledge_retriever.retrieve = trasig
        assert retrieval.retrieve_context("fråga") == []
    finally:
        knowledge_retriever.retrieve = original


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
        except Exception as e:  # oväntat fel i testet självt
            antal_fel += 1
            print("FEL  ", namn, "->", type(e).__name__, e)
    print(f"\n{len(tester) - antal_fel}/{len(tester)} tester gick igenom")
    sys.exit(1 if antal_fel else 0)
