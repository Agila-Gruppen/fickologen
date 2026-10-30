"""Tester för övningsprogrammets sidor i Streamlit (PLAN-92), mot den riktiga backenden.

Kör från repots rot:   python chat-engine/tests/test_program_ui.py
Backenden körs i samma process med en tillfällig SQLite-databas och inloggningen ersätts.
Chatten (Gemini) är fejkad, så inget nätverk eller nyckel behövs. Allt data är påhittat.
"""
import itertools
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "frontend" / "src"))

_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_dir, 'test.db').as_posix()}"
os.environ["BACKEND_URL"] = "http://127.0.0.1:9"  # ingen riktig server
os.environ.setdefault("SECRET_KEY", "test")

from fastapi.testclient import TestClient  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

import chat_engine  # noqa: E402
import program_api  # noqa: E402
from backend.src.config.database import Base, SessionLocal, engine  # noqa: E402
from backend.src.main import app  # noqa: E402
from backend.src.models import cbt_progress, conversation, diary_entry, exercise_log, message, user  # noqa: E402,F401
from backend.src.models.exercise_log import ExerciseLog  # noqa: E402
from backend.src.models.user import User  # noqa: E402
from backend.src.schemas.auth import CurrentUser  # noqa: E402
from backend.src.utils.auth import get_current_user  # noqa: E402

APP = str(REPO / "frontend" / "src" / "app.py")
Base.metadata.create_all(bind=engine)
backend = TestClient(app)
_nummer = itertools.count(1)
CHAT_ANROP = []


class FejkSvar:
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return {"reply": "Det är en bra fråga om veckan.", "engine": "rag", "category": "KBT_FRAGA",
                "via": "klassificerare", "llm_used": True, "sources": [], "conversation_id": None}


def fejk_post(path, json=None):
    CHAT_ANROP.append((path, json))
    return FejkSvar()


program_api._request = lambda method, path, json=None: backend.request(method, path, json=json)
chat_engine._post = fejk_post


def starta(roll="admin", vy="treatment"):
    """Startar appen som en ny påhittad användare med given roll."""
    db = SessionLocal()
    try:
        u = User(username=f"deltagare{next(_nummer)}", password="x", recovery_code="x")
        db.add(u)
        db.commit()
        user_id, username = u.id, u.username
    finally:
        db.close()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(user_id=user_id, username=username)
    CHAT_ANROP.clear()
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params["view"] = vy
    at.session_state["fk_token"] = "test"
    at.session_state["fk_user"] = {"user_id": user_id, "username": username, "role": roll}
    at.run()
    assert not at.exception, at.exception
    return at, user_id


def knapp(at, text):
    traffar = [b for b in at.button if b.label == text]
    assert traffar, f"hittar ingen knapp '{text}' bland {[b.label for b in at.button]}"
    return traffar[0]


def alla_texter(at):
    return " ".join(m.value for m in at.markdown) + " " + " ".join(c.value for c in at.caption)


def starta_vecka_1(roll="admin"):
    """Startar programmet och öppnar vecka 1."""
    at, user_id = starta(roll)
    knapp(at, "Starta programmet").click()
    at.run()
    assert not at.exception, at.exception
    knapp(at, "Fortsätt med vecka 1").click()
    at.run()
    assert not at.exception, at.exception
    return at, user_id


def markera_alla_gjorda(at):
    for ruta in at.checkbox:
        if ruta.key and ruta.key.startswith("fk_ex_done_"):
            ruta.check()


def sparade_ovningar(user_id):
    db = SessionLocal()
    try:
        return {l.exercise_id: l for l in db.query(ExerciseLog).filter_by(user_id=user_id).all()}
    finally:
        db.close()


def test_programmet_syns_for_alla_inloggade_men_inte_for_besokare():
    admin, _ = starta("admin", "home")
    vanlig, _ = starta("user", "home")
    besokare = AppTest.from_file(APP, default_timeout=60)
    besokare.query_params["view"] = "treatment"
    besokare.run()
    assert not besokare.exception, besokare.exception
    assert any("12 veckor KBT" in b.label for b in admin.sidebar.button)
    assert any("12 veckor KBT" in b.label for b in vanlig.sidebar.button)
    assert not any("12 veckor KBT" in b.label for b in besokare.sidebar.button)
    # utan konto hamnar man på startsidan, inte i programmet
    assert not any("Starta programmet" in b.label for b in besokare.button)
    assert not any("Hantera konton" in b.label for b in vanlig.sidebar.button)


def test_innan_start_visas_introt_och_ingen_vecka():
    at, _ = starta()
    assert "Så här fungerar programmet" in alla_texter(at)
    assert knapp(at, "Starta programmet")
    assert not [b for b in at.button if "Fortsätt med vecka" in b.label]


def test_en_vanlig_anvandare_kan_gora_programmet():
    at, user_id = starta_vecka_1("user")
    at.text_area(key="fk_ex_note_w01-kartlagg").set_value("Möten och middagar.")
    knapp(at, "Spara").click()
    at.run()
    assert not at.exception, at.exception
    assert "w01-kartlagg" in sparade_ovningar(user_id)


def test_start_visar_vecka_1_och_den_oppnas_med_teori_ovningar_och_chatt():
    at, _ = starta_vecka_1()
    text = alla_texter(at)
    assert "Så fungerar social ångest" in text and "Kartlägg ditt mönster" in text
    assert at.chat_input(key="fk_program_chat_input") is not None
    assert len([t for t in at.text_area if t.key.startswith("fk_ex_note_")]) >= 3  # 2 övningar + reflektion


def test_varje_ovning_visar_en_tydlig_uppgift_och_vad_man_ska_skriva():
    at, _ = starta_vecka_1()
    text = " ".join(m.value for m in at.markdown)
    assert text.count("Din uppgift") == 2  # veckans två övningar
    assert "Beskriv tre situationer där du blir nervös" in text
    etiketter = {t.key: t.label for t in at.text_area}
    assert etiketter["fk_ex_note_w01-mal"] == "Mitt mål och mitt första lilla steg"


def test_att_spara_en_ovning_hamnar_i_databasen():
    at, user_id = starta_vecka_1()
    at.text_area(key="fk_ex_note_w01-kartlagg").set_value("Möten, middagar och telefonsamtal.")
    at.checkbox(key="fk_ex_done_w01-kartlagg").check()
    knapp(at, "Spara").click()
    at.run()
    assert not at.exception, at.exception
    logg = sparade_ovningar(user_id)["w01-kartlagg"]
    assert logg.done is True and logg.reflection == "Möten, middagar och telefonsamtal."


def test_ett_klick_pa_spara_sparar_alla_ovningar_och_reflektionen():
    at, user_id = starta_vecka_1()
    at.text_area(key="fk_ex_note_w01-kartlagg").set_value("Första")
    at.text_area(key="fk_ex_note_w01-mal").set_value("Andra")
    at.text_area(key="fk_ex_note_reflektion_1").set_value("Cirkeln kändes igen.")
    knapp(at, "Spara").click()
    at.run()
    assert not at.exception, at.exception
    sparat = sparade_ovningar(user_id)
    assert sparat["w01-kartlagg"].reflection == "Första"
    assert sparat["w01-mal"].reflection == "Andra"
    assert sparat["reflektion"].reflection == "Cirkeln kändes igen."


def test_spara_utan_att_skriva_nagot_sparar_inget():
    at, user_id = starta_vecka_1()
    knapp(at, "Spara").click()
    at.run()
    assert not at.exception, at.exception
    assert sparade_ovningar(user_id) == {}


def test_att_spara_om_skriver_over_och_laser_om_efter_omladdning():
    at, user_id = starta_vecka_1()
    at.text_area(key="fk_ex_note_w01-mal").set_value("Version ett")
    knapp(at, "Spara").click()
    at.run()
    at.text_area(key="fk_ex_note_w01-mal").set_value("Version två")
    knapp(at, "Spara").click()
    at.run()
    assert sparade_ovningar(user_id)["w01-mal"].reflection == "Version två"
    # ny session (som att ladda om sidan): det sparade ligger kvar
    ny, _ = starta_om(user_id)
    assert ny.text_area(key="fk_ex_note_w01-mal").value == "Version två"


def starta_om(user_id, roll="admin"):
    """Öppnar vecka 1 igen för en befintlig användare, som efter en omladdning."""
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(user_id=user_id, username="x")
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params["view"] = "treatment"
    at.session_state["fk_token"] = "test"
    at.session_state["fk_user"] = {"user_id": user_id, "username": "x", "role": roll}
    at.session_state["fk_program_week"] = 1
    at.run()
    assert not at.exception, at.exception
    return at, user_id


def test_att_avsluta_veckan_utan_klara_ovningar_sparar_men_stannar_och_forklarar():
    at, user_id = starta_vecka_1()
    at.text_area(key="fk_ex_note_w01-kartlagg").set_value("Halvfärdigt")
    knapp(at, "Spara och avsluta veckan ✓").click()
    at.run()
    assert not at.exception, at.exception
    assert sparade_ovningar(user_id)["w01-kartlagg"].reflection == "Halvfärdigt"
    varningar = " ".join(w.value for w in at.warning)
    assert "Det du skrivit är sparat" in varningar and "Kartlägg ditt mönster" in varningar
    assert "Så fungerar social ångest" in alla_texter(at)  # kvar på vecka 1


def test_ett_klick_sparar_avslutar_veckan_och_oppnar_nasta_vecka_direkt():
    at, user_id = starta_vecka_1()
    markera_alla_gjorda(at)
    knapp(at, "Spara och avsluta veckan ✓").click()
    at.run()
    assert not at.exception, at.exception
    assert all(l.done for k, l in sparade_ovningar(user_id).items() if k != "reflektion")
    # direkt på vecka 2, utan omväg via översikten
    assert "Tankar, känslor och kropp" in alla_texter(at)
    assert knapp(at, "‹ Förra veckan").disabled is False


def test_man_kan_ga_fram_och_tillbaka_mellan_veckor():
    at, _ = starta_vecka_1()
    assert knapp(at, "‹ Förra veckan").disabled is True       # första veckan
    assert knapp(at, "Nästa vecka ›").disabled is True        # vecka 2 är låst
    markera_alla_gjorda(at)
    knapp(at, "Spara och avsluta veckan ✓").click()
    at.run()

    knapp(at, "‹ Förra veckan").click()
    at.run()
    assert not at.exception, at.exception
    assert "Så fungerar social ångest" in alla_texter(at)
    knapp(at, "Nästa vecka ›").click()
    at.run()
    assert "Tankar, känslor och kropp" in alla_texter(at)
    assert knapp(at, "Nästa vecka ›").disabled is True        # vecka 3 är låst än


def test_veckovaljaren_byter_vecka_och_stannar_kvar_om_veckan_ar_last():
    at, _ = starta_vecka_1()
    markera_alla_gjorda(at)
    knapp(at, "Spara och avsluta veckan ✓").click()
    at.run()                                                   # nu på vecka 2

    at.selectbox(key="fk_program_jump_2").set_value(1).run()
    assert not at.exception, at.exception
    assert "Så fungerar social ångest" in alla_texter(at)

    at.selectbox(key="fk_program_jump_1").set_value(2).run()
    assert "Tankar, känslor och kropp" in alla_texter(at)

    at.selectbox(key="fk_program_jump_2").set_value(7).run()   # låst
    assert not at.exception, at.exception
    assert "Tankar, känslor och kropp" in alla_texter(at)
    assert at.selectbox(key="fk_program_jump_2").value == 2


def test_en_klar_vecka_kan_andras_och_ger_knapp_till_nasta():
    at, user_id = starta_vecka_1()
    markera_alla_gjorda(at)
    knapp(at, "Spara och avsluta veckan ✓").click()
    at.run()
    knapp(at, "‹ Förra veckan").click()
    at.run()
    at.text_area(key="fk_ex_note_w01-mal").set_value("Ändrat i efterhand")
    knapp(at, "Spara").click()
    at.run()
    assert sparade_ovningar(user_id)["w01-mal"].reflection == "Ändrat i efterhand"
    knapp(at, "Spara och gå till vecka 2 ›").click()
    at.run()
    assert not at.exception, at.exception
    assert "Tankar, känslor och kropp" in alla_texter(at)


def test_oversikten_listar_alla_veckor_och_lar_oppna_en_tidigare():
    at, _ = starta_vecka_1()
    markera_alla_gjorda(at)
    knapp(at, "Spara och avsluta veckan ✓").click()
    at.run()
    at.button(key="fk_program_back").click().run()
    assert not at.exception, at.exception
    assert "Vecka 12:" in alla_texter(at)
    assert [b for b in at.button if b.key == "fk_program_open_1"]
    assert not [b for b in at.button if b.key == "fk_program_open_5"]  # låsta veckor har ingen knapp
    at.button(key="fk_program_open_1").click().run()
    assert "Så fungerar social ångest" in alla_texter(at)


def test_chatten_bredvid_skickar_med_vilken_vecka_som_ar_oppen():
    at, _ = starta()
    knapp(at, "Starta programmet").click()
    at.run()
    knapp(at, "Fortsätt med vecka 1").click()
    at.run()
    at.chat_input(key="fk_program_chat_input").set_value("Vad är en säkerhetsbeteende?").run()
    assert not at.exception, at.exception
    assert CHAT_ANROP, "chatten borde ha anropat backenden"
    path, payload = CHAT_ANROP[-1]
    assert path == "/chat/" and payload["program_week"] == 1
    assert "Det är en bra fråga om veckan." in alla_texter(at)


def test_chattens_forslag_syns_direkt_och_en_fraga_kan_skickas_med_ett_klick():
    at, _ = starta_vecka_1()
    forslag = [b for b in at.button if b.key and b.key.startswith("fk_chip_program_1_")]
    assert len(forslag) == 3
    forslag[0].click().run()
    assert not at.exception, at.exception
    assert CHAT_ANROP and CHAT_ANROP[-1][1]["program_week"] == 1
    assert CHAT_ANROP[-1][1]["messages"][-1]["content"] == "Kan du förklara cirkeln med ett vardagsexempel?"
    # när samtalet har börjat ligger förslagen i en hopfälld ruta i stället
    assert not [b for b in at.button if b.key and b.key.startswith("fk_chip_program_")]
    assert [b for b in at.button if b.key and b.key.startswith("fk_program_tip_1_")]


def test_ny_chatt_i_programmet_tommer_samtalet():
    at, _ = starta_vecka_1()
    at.chat_input(key="fk_program_chat_input").set_value("Hej").run()
    assert "Det är en bra fråga om veckan." in alla_texter(at)
    at.button(key="fk_program_new_chat").click().run()
    assert not at.exception, at.exception
    assert "Det är en bra fråga om veckan." not in alla_texter(at)
    assert [b for b in at.button if b.key and b.key.startswith("fk_chip_program_1_")]


def test_chatten_visar_inte_etiketten_fickologen_reflekterar_pa_varje_svar():
    at, _ = starta_vecka_1()
    at.chat_input(key="fk_program_chat_input").set_value("Hej").run()
    assert "Det är en bra fråga om veckan." in alla_texter(at)
    assert 'class="fk-reflect-label"' not in " ".join(m.value for m in at.markdown)


def test_vanliga_chatten_skickar_ingen_vecka():
    at, _ = starta(vy="chat")
    at.chat_input[0].set_value("Hej, jag blev nervös inför mötet").run()
    assert CHAT_ANROP and "program_week" not in CHAT_ANROP[-1][1]


def test_chatten_kan_stangas_av_och_veckan_visas_fortfarande():
    at, _ = starta()
    knapp(at, "Starta programmet").click()
    at.run()
    knapp(at, "Fortsätt med vecka 1").click()
    at.run()
    at.toggle(key="fk_program_chat_on").set_value(False).run()
    assert not at.exception, at.exception
    assert not at.chat_input
    assert "Så fungerar social ångest" in alla_texter(at)


def test_borja_om_tar_bort_framsteg_och_gammal_text():
    at, user_id = starta()
    knapp(at, "Starta programmet").click()
    at.run()
    knapp(at, "Fortsätt med vecka 1").click()
    at.run()
    at.text_area(key="fk_ex_note_w01-kartlagg").set_value("Hemlig text")
    at.checkbox(key="fk_ex_done_w01-kartlagg").check()
    knapp(at, "Spara").click()
    at.run()
    at.button(key="fk_program_back").click().run()
    at.checkbox(key="fk_program_reset_sure").check().run()
    at.button(key="fk_program_reset").click().run()
    assert not at.exception, at.exception
    assert knapp(at, "Starta programmet")
    # startar om och öppnar vecka 1: inget av det gamla ska finnas kvar
    knapp(at, "Starta programmet").click()
    at.run()
    knapp(at, "Fortsätt med vecka 1").click()
    at.run()
    assert at.text_area(key="fk_ex_note_w01-kartlagg").value == ""
    assert at.checkbox(key="fk_ex_done_w01-kartlagg").value is False


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
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
