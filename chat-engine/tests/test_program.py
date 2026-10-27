"""Tester för det 12 veckor långa KBT-programmet (PLAN-92): innehållet och /program-API:t.

Kör från repots rot:   python chat-engine/tests/test_program.py
Använder en tillfällig SQLite-databas och ersätter inloggningen, så inget nätverk eller Gemini behövs.
"""
import itertools
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
from backend.src.models import cbt_progress, conversation, diary_entry, exercise_log, message, user  # noqa: E402,F401
from backend.src.models.cbt_progress import CbtProgress  # noqa: E402
from backend.src.models.exercise_log import ExerciseLog  # noqa: E402
from backend.src.models.user import User  # noqa: E402
from backend.src.schemas.auth import CurrentUser  # noqa: E402
from backend.src.services import program_content  # noqa: E402
from backend.src.utils.auth import get_current_user  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(app)  # utan "with": startup-händelserna körs inte
_nummer = itertools.count(1)


def _ny_anvandare():
    """Skapar en påhittad användare och loggar in som den."""
    db = SessionLocal()
    try:
        u = User(username=f"deltagare{next(_nummer)}", password="x", recovery_code="x")
        db.add(u)
        db.commit()
        user_id, username = u.id, u.username
    finally:
        db.close()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(user_id=user_id, username=username)
    return user_id


def _starta():
    return client.post("/program/start")


def _klara_krav(vecka):
    """Sparar alla obligatoriska övningar i veckan som gjorda."""
    for ovning in client.get(f"/program/weeks/{vecka}").json()["exercises"]:
        if ovning["required"]:
            svar = client.put(f"/program/weeks/{vecka}/exercises/{ovning['id']}", json={"done": True})
            assert svar.status_code == 200, svar.text


def _klara_vecka(vecka):
    _klara_krav(vecka)
    svar = client.post(f"/program/weeks/{vecka}/complete")
    assert svar.status_code == 200, svar.text
    return svar.json()


# --- innehållet ---------------------------------------------------------------

def test_alla_12_veckor_finns_i_ordning():
    program = program_content.load_program()
    assert list(program) == list(range(1, 13))
    assert [v.week for v in program.values()] == list(range(1, 13))


def test_varje_vecka_har_en_obligatorisk_ovning_och_en_reflektionsfraga():
    for vecka in program_content.load_program().values():
        assert any(e.required for e in vecka.exercises), vecka.week
        assert vecka.reflection_prompt.strip(), vecka.week


def test_veckorna_ar_inte_for_tunga():
    """Det får inte vara för mycket teori eller för många övningar (användaren ska inte bli överväldigad)."""
    for vecka in program_content.load_program().values():
        ord_i_teorin = len(vecka.theory.split())
        assert ord_i_teorin <= 250, f"vecka {vecka.week}: {ord_i_teorin} ord teori"
        assert len(vecka.exercises) <= 3, f"vecka {vecka.week}: {len(vecka.exercises)} övningar"
        assert vecka.minutes <= 45, f"vecka {vecka.week}: {vecka.minutes} min"
        assert sum(e.minutes for e in vecka.exercises) <= 60, vecka.week


def test_ovnings_id_ar_unika_och_borjar_med_veckans_nummer():
    ids = [e.id for v in program_content.load_program().values() for e in v.exercises]
    assert len(ids) == len(set(ids))
    for nummer, vecka in program_content.load_program().items():
        assert all(e.id.startswith(f"w{nummer:02d}-") for e in vecka.exercises)


def test_lasaren_vagrar_saknad_vecka_eller_fel_id():
    kopia = Path(tempfile.mkdtemp())
    for fil in program_content.CONTENT_DIR.glob("week-*.md"):
        (kopia / fil.name).write_text(fil.read_text(encoding="utf-8"), encoding="utf-8")
    program_content.load_program(kopia)  # hel kopia är giltig

    (kopia / "week-12.md").unlink()
    program_content.load_program.cache_clear()
    try:
        program_content.load_program(kopia)
        assert False, "saknad vecka borde ge fel"
    except ValueError as e:
        assert "week-12.md" in str(e)

    (kopia / "week-12.md").write_text(
        (program_content.CONTENT_DIR / "week-11.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    program_content.load_program.cache_clear()
    try:
        program_content.load_program(kopia)
        assert False, "fel veckonummer borde ge fel"
    except ValueError as e:
        assert "week-12.md" in str(e)
    program_content.load_program.cache_clear()


# --- API:t --------------------------------------------------------------------

def test_innan_start_ar_allt_last_och_en_vecka_kan_inte_oppnas():
    _ny_anvandare()
    oversikt = client.get("/program/").json()
    assert oversikt["started"] is False and len(oversikt["weeks"]) == 12
    assert all(v["status"] == "locked" for v in oversikt["weeks"])
    assert client.get("/program/weeks/1").status_code == 409


def test_start_oppnar_vecka_1_och_start_igen_aterstaller_inget():
    _ny_anvandare()
    oversikt = _starta().json()
    assert oversikt["started"] is True and oversikt["current_week"] == 1
    status = {v["week"]: v["status"] for v in oversikt["weeks"]}
    assert status[1] == "open" and status[2] == "locked"
    _klara_vecka(1)
    assert _starta().json()["current_week"] == 2


def test_last_vecka_ger_403_och_okand_vecka_404():
    _ny_anvandare()
    _starta()
    assert client.get("/program/weeks/2").status_code == 403
    assert client.get("/program/weeks/13").status_code == 404
    assert client.get("/program/weeks/0").status_code == 404


def test_veckan_kommer_med_teori_ovningar_och_inget_sparat_an():
    _ny_anvandare()
    _starta()
    vecka = client.get("/program/weeks/1").json()
    assert vecka["title"] and vecka["theory"] and vecka["exercises"]
    assert vecka["logs"] == [] and vecka["can_complete"] is False


def test_spara_ovning_uppdaterar_samma_rad_och_hamtas_tillbaka():
    _ny_anvandare()
    _starta()
    ovning = client.get("/program/weeks/1").json()["exercises"][0]["id"]
    url = f"/program/weeks/1/exercises/{ovning}"
    assert client.put(url, json={"done": False, "reflection": "  Första försöket  "}).status_code == 200
    svar = client.put(url, json={"done": True, "reflection": "Andra försöket", "rating_before": 60, "rating_after": 35})
    assert svar.status_code == 200
    loggar = client.get("/program/weeks/1").json()["logs"]
    assert len(loggar) == 1
    assert loggar[0]["reflection"] == "Andra försöket"
    assert loggar[0]["done"] is True and loggar[0]["rating_before"] == 60 and loggar[0]["rating_after"] == 35


def test_tom_text_sparas_som_ingen_text_och_ogiltiga_varden_nekas():
    _ny_anvandare()
    _starta()
    ovning = client.get("/program/weeks/1").json()["exercises"][0]["id"]
    url = f"/program/weeks/1/exercises/{ovning}"
    svar = client.put(url, json={"done": True, "reflection": "   "})
    assert svar.status_code == 200 and svar.json()["reflection"] is None
    assert client.put(url, json={"rating_before": 101}).status_code == 422
    assert client.put(url, json={"rating_after": -1}).status_code == 422
    assert client.put(url, json={"reflection": "x" * 5001}).status_code == 422


def test_okand_ovning_nekas_men_veckans_reflektion_gar_att_spara():
    _ny_anvandare()
    _starta()
    assert client.put("/program/weeks/1/exercises/w07-expo1", json={"done": True}).status_code == 404
    assert client.put("/program/weeks/1/exercises/finns-inte", json={"done": True}).status_code == 404
    svar = client.put("/program/weeks/1/exercises/reflektion", json={"reflection": "Jag kände igen mig i cirkeln."})
    assert svar.status_code == 200
    # reflektionen räknas inte som en obligatorisk övning
    assert client.get("/program/weeks/1").json()["can_complete"] is False


def test_man_kan_inte_spara_pa_en_last_vecka():
    _ny_anvandare()
    _starta()
    assert client.put("/program/weeks/2/exercises/w02-tankedagbok", json={"done": True}).status_code == 403


def test_vecka_kan_inte_avslutas_for_obligatoriska_ovningar_ar_klara():
    _ny_anvandare()
    _starta()
    assert client.post("/program/weeks/1/complete").status_code == 409
    forsta = client.get("/program/weeks/1").json()["exercises"][0]["id"]
    client.put(f"/program/weeks/1/exercises/{forsta}", json={"done": True})
    assert client.post("/program/weeks/1/complete").status_code == 409  # vecka 1 har två obligatoriska
    assert client.get("/program/").json()["current_week"] == 1


def test_att_avsluta_en_vecka_oppnar_nasta_och_ar_idempotent():
    _ny_anvandare()
    _starta()
    oversikt = _klara_vecka(1)
    status = {v["week"]: v["status"] for v in oversikt["weeks"]}
    assert status[1] == "done" and status[2] == "open" and status[3] == "locked"
    assert oversikt["completed_weeks"] == [1] and oversikt["current_week"] == 2
    igen = client.post("/program/weeks/1/complete").json()
    assert igen["completed_weeks"] == [1] and igen["current_week"] == 2
    assert client.get("/program/weeks/2").status_code == 200


def test_att_gora_om_en_gammal_vecka_flyttar_inte_framsteget_bakat():
    _ny_anvandare()
    _starta()
    _klara_vecka(1)
    _klara_vecka(2)
    assert client.post("/program/weeks/1/complete").json()["current_week"] == 3


def test_hela_programmet_kan_goras_och_vecka_12_ger_finished():
    _ny_anvandare()
    _starta()
    for vecka in range(1, 13):
        oversikt = _klara_vecka(vecka)
        assert oversikt["finished"] is (vecka == 12)
    assert oversikt["completed_weeks"] == list(range(1, 13))
    assert oversikt["current_week"] == 12
    assert all(v["status"] == "done" for v in oversikt["weeks"])


def test_anvandare_ser_bara_sitt_eget():
    _ny_anvandare()
    _starta()
    _klara_vecka(1)
    _ny_anvandare()
    oversikt = client.get("/program/").json()
    assert oversikt["started"] is False and oversikt["completed_weeks"] == []
    _starta()
    assert client.get("/program/weeks/1").json()["logs"] == []


def test_aterstall_tar_bort_framsteg_och_allt_sparat():
    anvandare = _ny_anvandare()
    _starta()
    _klara_vecka(1)
    svar = client.delete("/program/")
    assert svar.status_code == 200 and svar.json()["deleted"] >= 2
    assert client.get("/program/").json()["started"] is False
    db = SessionLocal()
    try:
        assert db.query(ExerciseLog).filter(ExerciseLog.user_id == anvandare).count() == 0
        assert db.query(CbtProgress).filter(CbtProgress.user_id == anvandare).count() == 0
    finally:
        db.close()


def test_radera_mitt_innehall_tar_ocksa_bort_programmet_men_inte_kontot():
    anvandare = _ny_anvandare()
    _starta()
    _klara_vecka(1)
    svar = client.delete("/users/me/data")
    assert svar.status_code == 200, svar.text
    db = SessionLocal()
    try:
        assert db.query(ExerciseLog).filter(ExerciseLog.user_id == anvandare).count() == 0
        assert db.query(CbtProgress).filter(CbtProgress.user_id == anvandare).count() == 0
        assert db.get(User, anvandare) is not None
    finally:
        db.close()


def test_att_radera_kontot_tar_bort_programmets_loggar():
    anvandare = _ny_anvandare()
    _starta()
    _klara_vecka(1)
    db = SessionLocal()
    try:
        db.delete(db.get(User, anvandare))
        db.commit()
        assert db.query(ExerciseLog).filter(ExerciseLog.user_id == anvandare).count() == 0
    finally:
        db.close()


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
