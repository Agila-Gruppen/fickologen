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


def spara_alla_obligatoriska(at):
    """Fyller i och sparar veckans övningar som gjorda, en i taget (varje spar ger omkörning)."""
    for _ in range(5):
        kvar = [c for c in at.checkbox if c.key and c.key.startswith("fk_ex_done_") and not c.value]
        if not kvar:
            return at
        kvar[0].check()
        index = [c.key for c in at.checkbox if c.key and c.key.startswith("fk_ex_done_")].index(kvar[0].key)
        [b for b in at.button if b.label == "Spara"][index].click()
        at.run()
        assert not at.exception, at.exception
    return at


def test_programmet_syns_i_menyn_bara_for_admin():
    admin, _ = starta("admin", "home")
    vanlig, _ = starta("user", "home")
    assert any("Övningsprogram" in b.label for b in admin.sidebar.button)
    assert not any("Övningsprogram" in b.label for b in vanlig.sidebar.button)


def test_innan_start_visas_introt_och_ingen_vecka():
    at, _ = starta()
    assert "Så här fungerar programmet" in alla_texter(at)
    assert knapp(at, "Starta programmet")
    assert not [b for b in at.button if "Fortsätt med vecka" in b.label]


def test_start_visar_vecka_1_och_den_oppnas_med_teori_ovningar_och_chatt():
    at, _ = starta()
    knapp(at, "Starta programmet").click()
    at.run()
    assert not at.exception, at.exception
    knapp(at, "Fortsätt med vecka 1").click()
    at.run()
    assert not at.exception, at.exception
    text = alla_texter(at)
    assert "Så fungerar social ångest" in text and "Kartlägg ditt mönster" in text
    assert at.chat_input(key="fk_program_chat_input") is not None
    assert len([t for t in at.text_area if t.key.startswith("fk_ex_note_")]) >= 3  # 2 övningar + reflektion


def test_att_spara_en_ovning_hamnar_i_databasen():
    at, user_id = starta()
    knapp(at, "Starta programmet").click()
    at.run()
    knapp(at, "Fortsätt med vecka 1").click()
    at.run()
    at.text_area(key="fk_ex_note_w01-kartlagg").set_value("Möten, middagar och telefonsamtal.")
    at.checkbox(key="fk_ex_done_w01-kartlagg").check()
    knapp(at, "Spara").click()
    at.run()
    assert not at.exception, at.exception
    db = SessionLocal()
    try:
        logg = db.query(ExerciseLog).filter_by(user_id=user_id, exercise_id="w01-kartlagg").one()
        assert logg.done is True and logg.reflection == "Möten, middagar och telefonsamtal."
    finally:
        db.close()


def test_veckan_kan_inte_avslutas_for_obligatoriska_ovningar_ar_klara_och_sedan_kan_den_det():
    at, _ = starta()
    knapp(at, "Starta programmet").click()
    at.run()
    knapp(at, "Fortsätt med vecka 1").click()
    at.run()
    assert knapp(at, "Klar med veckan ✓").disabled is True
    assert "För att gå vidare behöver du markera" in alla_texter(at)

    spara_alla_obligatoriska(at)
    avsluta = knapp(at, "Klar med veckan ✓")
    assert avsluta.disabled is False
    avsluta.click()
    at.run()
    assert not at.exception, at.exception
    # tillbaka på översikten, och vecka 2 är nu veckan
    assert knapp(at, "Fortsätt med vecka 2")


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
