"""Tester för att dagbok och chatt krypteras i databasen (DATA_ENCRYPTION_KEY).

Kör från repots rot:   python chat-engine/tests/test_encryption.py
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
os.environ["DATA_ENCRYPTION_KEY"] = "81_35OPrUSSzx-DSO81sLnCN5cWyysSICmBRRnVIOYw="

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from backend.src.config.database import Base, SessionLocal, engine  # noqa: E402
from backend.src.main import app  # noqa: E402
from backend.src.models import cbt_progress, conversation, diary_entry, exercise_log, message, user  # noqa: E402,F401
from backend.src.models.conversation import Conversation  # noqa: E402
from backend.src.models.message import Message  # noqa: E402
from backend.src.models.user import User  # noqa: E402
from backend.src.schemas.auth import CurrentUser  # noqa: E402
from backend.src.utils import crypto  # noqa: E402
from backend.src.utils.auth import get_current_user  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(app)  # utan "with": startup-händelserna körs inte


def _skapa_anvandare():
    db = SessionLocal()
    try:
        anna = User(username="anna", password="x", recovery_code="x")
        db.add(anna)
        db.commit()
        return anna.id
    finally:
        db.close()


ANNA = _skapa_anvandare()
app.dependency_overrides[get_current_user] = lambda: CurrentUser(user_id=ANNA, username="anna")


def _ra_varde(sql, **params):
    """Läser det som faktiskt ligger i databasen, förbi den krypterande kolumntypen."""
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar_one()


def test_dagboken_sparas_krypterad_men_lases_i_klartext():
    svar = client.post("/diary/", json={"title": "Hemlig rubrik", "content": "Jag var orolig idag", "mood": 2})
    assert svar.status_code == 201, svar.text
    data = svar.json()
    assert data["title"] == "Hemlig rubrik" and data["content"] == "Jag var orolig idag"

    rubrik = _ra_varde("SELECT title FROM diary_entries WHERE id = :id", id=data["id"])
    text_i_db = _ra_varde("SELECT content FROM diary_entries WHERE id = :id", id=data["id"])
    assert "Hemlig" not in rubrik and "orolig" not in text_i_db, (rubrik, text_i_db)
    assert crypto.decrypt(text_i_db) == "Jag var orolig idag"

    lista = client.get("/diary/").json()
    assert any(e["content"] == "Jag var orolig idag" for e in lista)


def test_redigerad_dagbok_ar_fortfarande_krypterad():
    entry_id = client.post("/diary/", json={"content": "Första versionen"}).json()["id"]
    svar = client.patch(f"/diary/{entry_id}", json={"content": "Andra versionen"})
    assert svar.json()["content"] == "Andra versionen"
    assert "versionen" not in _ra_varde("SELECT content FROM diary_entries WHERE id = :id", id=entry_id)


def test_sokning_fungerar_trots_kryptering():
    client.post("/diary/", json={"title": "Promenad", "content": "Gick runt SJÖN i solen"})
    client.post("/diary/", json={"content": "Något helt annat"})
    traffar = client.get("/diary/", params={"search": "sjön"}).json()
    assert [e["content"] for e in traffar] == ["Gick runt SJÖN i solen"], traffar
    traffar = client.get("/diary/", params={"search": "promenad"}).json()
    assert len(traffar) == 1, traffar


def test_chattmeddelanden_och_titel_sparas_krypterade():
    db = SessionLocal()
    try:
        konv = Conversation(user_id=ANNA, title="Jag dricker för mycket")
        db.add(konv)
        db.flush()
        db.add(Message(conversation_id=konv.id, role="user", content="Jag dricker för mycket"))
        db.commit()
        konv_id = konv.id
    finally:
        db.close()

    assert "dricker" not in _ra_varde("SELECT title FROM conversations WHERE id = :id", id=konv_id)
    assert "dricker" not in _ra_varde("SELECT content FROM messages WHERE conversation_id = :id", id=konv_id)

    db = SessionLocal()
    try:
        assert db.get(Conversation, konv_id).messages[0].content == "Jag dricker för mycket"
    finally:
        db.close()


def test_nyckelbyte_kan_lasa_gammal_data():
    gammal = crypto.encrypt("skrivet med gamla nyckeln")
    nu = os.environ["DATA_ENCRYPTION_KEY"]
    os.environ["DATA_ENCRYPTION_KEY"] = f"{crypto.Fernet.generate_key().decode()},{nu}"
    crypto._fernet.cache_clear()
    try:
        assert crypto.decrypt(gammal) == "skrivet med gamla nyckeln"
    finally:
        os.environ["DATA_ENCRYPTION_KEY"] = nu
        crypto._fernet.cache_clear()


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
