"""Tester för kopplingen mellan backenden och routern (utan nätverk och utan nyckel).

Kör från repots rot:   python chat-engine/tests/test_backend_wiring.py
Gemini ersätts av fejkade funktioner, så inget förbrukar kvoten.
"""
import asyncio
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))                 # så att backend.src... går att importera
sys.path.insert(0, str(REPO / "chat-engine"))  # platta imports i chat-engine
logging.disable(logging.CRITICAL)

import safety_config as cfg  # noqa: E402
from router import route, state_from_history  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from backend.src.schemas.chat import ChatMessage, ChatRequest  # noqa: E402
from backend.src.services import chat as chat_service  # noqa: E402
from backend.src.services.retrieval import ContextChunk  # noqa: E402

GREETING = ChatMessage(role="assistant", content="Hej, vad bra att du är här.")


def u(text):
    return ChatMessage(role="user", content=text)


def a(text):
    return ChatMessage(role="assistant", content=text)


def kor(messages, engine="router", klass="KBT_DELNING", svar="FEJK-SVAR"):
    """Kör generate_reply med fejkad Gemini. svar kan vara en text eller ett Exception."""
    def generate(system_prompt, historik):
        if isinstance(svar, Exception):
            raise svar
        return svar

    chat_service._load_engine = lambda: SimpleNamespace(
        route=route,
        state_from_history=state_from_history,
        classify=lambda m, h, s: klass,
        generate=generate,
    )
    return asyncio.run(chat_service.generate_reply(messages, engine))


def test_kris_ger_fast_text_utan_gemini():
    res = kor([GREETING, u("jag vill ta livet av mig")])
    assert res.reply == cfg.FASTA_SVAR["SJALVSKADA"]
    assert (res.category, res.via, res.llm_used) == ("SJALVSKADA", "regel", False)


def test_tack_efter_kris_far_uppfoljning_trots_att_backenden_saknar_minne():
    historik = [GREETING, u("jag vill ta livet av mig"), a(cfg.FASTA_SVAR["SJALVSKADA"]), u("tack")]
    res = kor(historik)
    assert res.category == "RISK_UPPFOLJNING"
    assert "112" in res.reply


def test_vanligt_meddelande_far_gemini_svar_och_metadata():
    res = kor([GREETING, u("Jag blev nervös inför mötet")])
    assert res.reply == "FEJK-SVAR"
    assert (res.category, res.via, res.llm_used) == ("KBT_DELNING", "klassificerare", True)


def test_inledande_halsning_fran_boten_stoppar_inte_routern():
    res = kor([GREETING, u("hej")])
    assert res.category == "HEJ"


def test_rag_underlag_hamtas_bara_for_kbt_och_redovisas_som_kalla():
    anrop = []

    def fejk_retrieve(query, k=4):
        anrop.append(query)
        return [ContextChunk(text="Automatiska tankar är...", source="Modul 2")]

    chat_service.retrieve_context = fejk_retrieve
    res = kor([GREETING, u("Jag blev nervös inför mötet")])
    assert [c.source for c in res.chunks] == ["Modul 2"] and len(anrop) == 1

    anrop.clear()
    res = kor([GREETING, u("jag vill ta livet av mig")])
    assert res.chunks == [] and anrop == []


def test_gemini_som_kraschar_ger_reservtext_inte_fel():
    res = kor([GREETING, u("Jag blev nervös inför mötet")], svar=RuntimeError("nere"))
    assert res.reply == cfg.FASTA_SVAR["FALLBACK"]


def test_gamla_motorn_valjs_med_engine_legacy():
    async def fejk_legacy(messages):
        return chat_service.ChatResult(reply="GAMMALT SVAR")

    original = chat_service._generate_reply_legacy
    chat_service._generate_reply_legacy = fejk_legacy
    try:
        res = kor([GREETING, u("hej")], engine="legacy")
    finally:
        chat_service._generate_reply_legacy = original
    assert res.reply == "GAMMALT SVAR" and res.category is None


def test_schemat_har_router_som_standard_och_nekar_okand_motor():
    assert ChatRequest(messages=[u("hej")]).engine == "router"
    try:
        ChatRequest(messages=[u("hej")], engine="nagot-annat")
    except ValidationError:
        return
    raise AssertionError("okänd motor borde ge ValidationError")


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
