"""Tester för att byta namn på sparade chattar (PATCH /conversations/{id}).

Kör från repots rot:   python chat-engine/tests/test_conversations_rename.py
Använder en tillfällig SQLite-databas och ersätter inloggningen, så inget nätverk eller Gemini behövs.
"""
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_dir, 'test.db').as_posix()}"
os.environ.setdefault("SECRET_KEY", "test")

from fastapi.testclient import TestClient  # noqa: E402

from backend.src.config.database import Base, SessionLocal, engine  # noqa: E402
from backend.src.main import app  # noqa: E402
from backend.src.models import cbt_progress, conversation, diary_entry, message, user  # noqa: E402,F401
from backend.src.models.conversation import Conversation  # noqa: E402
from backend.src.models.user import User  # noqa: E402
from backend.src.schemas.auth import CurrentUser  # noqa: E402
from backend.src.utils.auth import get_current_user  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(app)  # utan "with": startup-händelserna körs inte
INLOGGAD = {"id": None}


def _som(user_id):
    INLOGGAD["id"] = user_id
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(user_id=user_id, username=f"u{user_id}")


def _skapa_anvandare_och_chattar():
    db = SessionLocal()
    try:
        for namn in ("anna", "bertil"):
            db.add(User(username=namn, password="x", recovery_code="x"))
        db.commit()
        ids = [u.id for u in db.query(User).order_by(User.id)]
        annas = Conversation(user_id=ids[0], title="Jag dricker för mycket varje kväll")
        bertils = Conversation(user_id=ids[1], title="Bertils chatt")
        db.add_all([annas, bertils])
        db.commit()
        return ids[0], ids[1], annas.id, bertils.id
    finally:
        db.close()


ANNA, BERTIL, ANNAS_CHATT, BERTILS_CHATT = _skapa_anvandare_och_chattar()


def _titel(conversation_id):
    db = SessionLocal()
    try:
        return db.get(Conversation, conversation_id).title
    finally:
        db.close()


def test_byta_namn_sparar_titeln_och_returnerar_chatten():
    _som(ANNA)
    svar = client.patch(f"/conversations/{ANNAS_CHATT}", json={"title": "Min kvällsoro"})
    assert svar.status_code == 200 and svar.json()["title"] == "Min kvällsoro"
    assert _titel(ANNAS_CHATT) == "Min kvällsoro"


def test_extra_mellanslag_städas_bort():
    _som(ANNA)
    client.patch(f"/conversations/{ANNAS_CHATT}", json={"title": "  Möte   imorgon  "})
    assert _titel(ANNAS_CHATT) == "Möte imorgon"


def test_tomt_eller_for_langt_namn_nekas_och_ger_inte_andring():
    _som(ANNA)
    före = _titel(ANNAS_CHATT)
    assert client.patch(f"/conversations/{ANNAS_CHATT}", json={"title": "   "}).status_code == 422
    assert client.patch(f"/conversations/{ANNAS_CHATT}", json={"title": "x" * 201}).status_code == 422
    assert client.patch(f"/conversations/{ANNAS_CHATT}", json={}).status_code == 422
    assert _titel(ANNAS_CHATT) == före


def test_man_kan_inte_doepa_om_andras_chattar():
    _som(ANNA)
    svar = client.patch(f"/conversations/{BERTILS_CHATT}", json={"title": "Hackad"})
    assert svar.status_code == 404
    assert _titel(BERTILS_CHATT) == "Bertils chatt"


def test_okand_chatt_ger_404():
    _som(ANNA)
    assert client.patch("/conversations/99999", json={"title": "Nytt"}).status_code == 404


def test_att_byta_namn_flyttar_inte_chatten_i_listan():
    _som(ANNA)
    db = SessionLocal()
    try:
        före = db.get(Conversation, ANNAS_CHATT).updated_at
    finally:
        db.close()
    client.patch(f"/conversations/{ANNAS_CHATT}", json={"title": "Ännu ett namn"})
    db = SessionLocal()
    try:
        efter = db.get(Conversation, ANNAS_CHATT).updated_at
    finally:
        db.close()
    assert efter == före, (före, efter)


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
