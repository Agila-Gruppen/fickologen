"""Tester för chatten i övningsprogrammet (PLAN-92): veckans innehåll når prompten, men aldrig efter en kris.

Kör från repots rot:   python chat-engine/tests/test_program_chat.py
Gemini ersätts av fejkade funktioner, så inget nätverk eller nyckel behövs.
"""
import asyncio
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "chat-engine"))
logging.disable(logging.CRITICAL)

import prompts  # noqa: E402
import safety_config as cfg  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from router import route, state_from_history  # noqa: E402

from backend.src.schemas.chat import ChatMessage, ChatRequest  # noqa: E402
from backend.src.services import chat as chat_service  # noqa: E402
from backend.src.services import program_content  # noqa: E402

PROMPTER = []


def u(text):
    return ChatMessage(role="user", content=text)


def kor(messages, program_week=None, engine="rag", klass="KBT_FRAGA"):
    """Kör generate_reply med fejkad Gemini och sparar systemprompten i PROMPTER."""
    PROMPTER.clear()

    def generate(system_prompt, historik):
        PROMPTER.append(system_prompt)
        return "FEJK-SVAR"

    chat_service._load_engine = lambda: SimpleNamespace(
        route=route,
        state_from_history=state_from_history,
        classify=lambda m, h, s: klass,
        generate=generate,
    )
    chat_service.retrieve_context = lambda q, k=4: []
    return asyncio.run(chat_service.generate_reply(messages, engine, program_week=program_week))


def test_veckans_innehall_hamtas_ur_vara_egna_filer():
    text = program_content.week_chat_context(5)
    assert "Vecka 5 av 12: Beteendeexperiment" in text
    assert "Planera ett experiment" in text and "Säkerhet:" in text
    assert program_content.week_chat_context(13) is None


def test_prompten_far_veckan_nar_man_chattar_fran_programmet():
    kor([u("Vad är en tankefälla?")], program_week=3)
    assert "PROGRAMLÄGE" in PROMPTER[0]
    assert "Vecka 3 av 12: Tankefällor" in PROMPTER[0]


def test_utan_program_ar_prompten_som_vanligt():
    kor([u("Vad är en tankefälla?")])
    assert "PROGRAMLÄGE" not in PROMPTER[0] and "VECKANS INNEHÅLL" not in PROMPTER[0]


def test_veckan_laggs_till_for_alla_gemini_moduler_utom_forsiktigt_lage():
    for klass in ("KBT_DELNING", "KBT_FRAGA", "KORT_SVAR", "OVRIGT"):
        kor([u("Jag förstår inte övningen riktigt")], program_week=4, klass=klass)
        assert "Vecka 4 av 12" in PROMPTER[0], klass


def test_efter_en_kris_far_prompten_aldrig_veckans_ovningar():
    kristext = ChatMessage(role="assistant", content=cfg.FASTA_SVAR["SJALVSKADA"])
    historik = [u("jag vill ta livet av mig"), kristext, u("jag vet inte")]
    kor(historik, program_week=7, klass="KORT_SVAR")
    assert PROMPTER, "Gemini borde ha anropats i försiktigt läge"
    assert "FÖRSIKTIGT LÄGE" in PROMPTER[0]
    assert "PROGRAMLÄGE" not in PROMPTER[0] and "Vecka 7" not in PROMPTER[0]


def test_kris_i_programmet_ger_fortfarande_fast_text_utan_gemini():
    res = kor([u("jag vill ta livet av mig")], program_week=7)
    assert res.llm_used is False and PROMPTER == []


def test_gamla_motorn_ignorerar_veckan():
    async def fejk_legacy(messages):
        return chat_service.ChatResult(reply="gammal")

    original = chat_service._generate_reply_legacy
    chat_service._generate_reply_legacy = fejk_legacy
    try:
        res = asyncio.run(chat_service.generate_reply([u("hej då")], "legacy", program_week=2))
    finally:
        chat_service._generate_reply_legacy = original
    assert res.reply == "gammal"


def test_schemat_godtar_bara_vecka_1_till_12():
    assert ChatRequest(messages=[u("hej")], program_week=12).program_week == 12
    assert ChatRequest(messages=[u("hej")]).program_week is None
    for fel in (0, 13, -1):
        try:
            ChatRequest(messages=[u("hej")], program_week=fel)
            assert False, fel
        except ValidationError:
            pass


def test_programreglerna_ligger_inte_i_den_vanliga_prompten():
    assert "PROGRAMLÄGE" not in prompts.build_system_prompt("kunskap")
    assert "PROGRAMLÄGE" in prompts.build_system_prompt("kunskap", None, "Vecka 1")


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
        except Exception as e:
            antal_fel += 1
            print("FEL  ", namn, "->", type(e).__name__, e)
    print(f"\n{len(tester) - antal_fel}/{len(tester)} tester gick igenom")
    sys.exit(1 if antal_fel else 0)
