"""Tester för att demo-inställningarna bara syns för inloggade admins.

Kör från repots rot:   python chat-engine/tests/test_demo_synlighet.py
Kör Streamlit-appen i testläge, utan nätverk: inloggningen sätts direkt i sessionen.
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "frontend" / "src"))
os.environ["BACKEND_URL"] = "http://127.0.0.1:9"  # ingen server: inget i testet ska nå nätet

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(REPO / "frontend" / "src" / "app.py")
SVAR = {"role": "assistant", "content": "Hej!", "engine": "rag", "category": "KBT_DELNING",
        "via": "klassificerare", "llm_used": True, "sources": ["Modul 3 > Tankeläsning"]}


def starta(roll=None, **session):
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params["view"] = "chat"
    if roll:
        at.session_state["fk_token"] = "test"
        at.session_state["fk_user"] = {"user_id": 1, "username": "t", "role": roll}
    for nyckel, varde in session.items():
        at.session_state[nyckel] = varde
    at.run()
    assert not at.exception, at.exception
    return at


def expanders(at):
    return [e.label for e in at.sidebar.expander]


def test_utloggad_ser_inga_demo_installningar():
    assert "Demo-inställningar" not in expanders(starta())


def test_vanlig_anvandare_ser_inga_demo_installningar():
    assert "Demo-inställningar" not in expanders(starta("user"))


def test_admin_ser_demo_installningar_med_tre_versioner_och_senaste_som_standard():
    at = starta("admin")
    assert "Demo-inställningar" in expanders(at)
    radio = at.sidebar.radio(key="fk_engine_choice")
    assert len(radio.options) == 3 and radio.value == "rag"


def test_roll_saknas_raknas_som_vanlig_anvandare():
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params["view"] = "chat"
    at.session_state["fk_token"] = "test"
    at.session_state["fk_user"] = {"user_id": 1, "username": "t"}  # äldre session utan roll
    at.run()
    assert "Demo-inställningar" not in expanders(at)


def test_vanlig_anvandare_far_alltid_senaste_motorn_aven_om_gammalt_val_ligger_kvar():
    from chat_engine import DEFAULT_ENGINE, get_engine
    at = starta("user", fk_engine="legacy")
    assert at.session_state["fk_engine"] == "legacy"      # kvarlämnat val från en tidigare admin-session
    import streamlit as st
    st.session_state.clear()
    # get_engine läser sessionen, så vi provar logiken direkt med fejkad session
    import auth
    original = auth.is_admin
    try:
        auth.is_admin = lambda: False
        st.session_state["fk_engine"] = "legacy"
        assert get_engine() == DEFAULT_ENGINE
        auth.is_admin = lambda: True
        assert get_engine() == "legacy"
    finally:
        auth.is_admin = original


def test_teknisk_info_och_kallor_visas_bara_for_admin():
    gemensamt = dict(fk_messages=[{"role": "user", "content": "Vad är tankeläsning?"}, dict(SVAR)], fk_show_tech=True)
    admin = starta("admin", **gemensamt)
    assert any("Källor" in c.value for c in admin.caption)
    anvandare = starta("user", **gemensamt)
    assert not any("Källor" in c.value or "Kategori" in c.value for c in anvandare.caption)


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
