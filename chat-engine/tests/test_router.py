"""Tester för routern. Kör utan pytest:   python chat-engine/tests/test_router.py
(Fungerar också med pytest.) Använder fejkade LLM:er, så inga nycklar eller
nätanrop behövs och inget förbrukar Gemini-kvoten."""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
logging.disable(logging.CRITICAL)  # tysta förväntade varningar i testerna

import safety_config as cfg  # noqa: E402
from prompts import MODULER, build_system_prompt  # noqa: E402
from router import SessionState, route, state_from_history  # noqa: E402


# ----------------------------------------------------------------- hjälpare
class FejkGenerate:
    def __init__(self, svar="LLM-SVAR"):
        self.svar, self.prompter = svar, []

    def __call__(self, system_prompt, historik):
        self.prompter.append(system_prompt)
        if isinstance(self.svar, Exception):
            raise self.svar
        return self.svar


class FejkKlassificerare:
    def __init__(self, kategori):
        self.kategori, self.anrop = kategori, 0

    def __call__(self, meddelande, historik, soft):
        self.anrop += 1
        if isinstance(self.kategori, Exception):
            raise self.kategori
        return self.kategori


def kor(meddelande, klass="KBT_DELNING", gen=None, state=None, historik=None, retrieve=None):
    k = FejkKlassificerare(klass)
    g = gen or FejkGenerate()
    svar = route(meddelande, historik or [], state or SessionState(),
                 classify_fn=k, generate_fn=g, retrieve_fn=retrieve)
    return svar, k, g


# ---------------------------------------------- Lager 0: hård krislista (recall)
HARDA_FALL = [
    ("Jag vill ta livet av mig", "SJALVSKADA"),
    ("jag orkar inte leva längre", "SJALVSKADA"),
    ("jag har självmordstankar", "SJALVSKADA"),
    ("det vore bättre om jag inte fanns", "SJALVSKADA"),
    ("jag vill skada mig själv", "SJALVSKADA"),
    ("jag tänker ta mitt liv", "SJALVSKADA"),
    ("jag vill INTE ta livet av mig men tankarna kommer", "SJALVSKADA"),  # hellre falsklarm
    ("jag har tagit för många tabletter", "SJALVSKADA"),
    ("jag vill dö", "SJALVSKADA"),
    ("jag vill bara försvinna för alltid", "SJALVSKADA"),
    ("jag vill skada honom", "VALD_MOT_ANDRA"),
    ("jag tänker döda min chef", "VALD_MOT_ANDRA"),
    ("jag har tankar på att skada mitt barn", "VALD_MOT_ANDRA"),
    ("han slår mig", "VALD_MOT_MIG"),
    ("min sambo hotar mig", "VALD_MOT_MIG"),
    ("jag är inte säker hemma", "VALD_MOT_MIG"),
    ("jag blev våldtagen för flera år sedan", "OVERGREPP_TIDIGARE"),
    ("jag har blivit utsatt för sexuellt våld", "OVERGREPP_TIDIGARE"),
    ("jag är sexuellt attraherad av barn", "SEXUELLA_TANKAR_BARN"),
    ("min vän vill ta livet av sig", "OROAD_FOR_ANNAN"),
    ("min syster pratar om självmord", "OROAD_FOR_ANNAN"),
]


def test_hard_lista_ger_ratt_kategori_utan_llm():
    fel = []
    for text, forvantad in HARDA_FALL:
        svar, k, g = kor(text)
        if svar.category != forvantad or svar.source != "regel" or k.anrop or g.prompter:
            fel.append(f"{text!r}: fick {svar.category}/{svar.source}, väntade {forvantad}")
    assert not fel, "\n" + "\n".join(fel)


FALSKLARMSFALLOR = [
    "Jag ville dö av skam när jag glömde mitt namn",
    "Jag vill dö av skam när jag tänker på det",
    "Jag är helt dödstrött idag",
    "Jag måste skjuta upp presentationen",
    "Jag skadade mig på cykeln igår",
    "Jag blev nervös och kunde inte prata",
]


def test_vanliga_uttryck_larmar_inte():
    for text in FALSKLARMSFALLOR:
        svar, _, _ = kor(text, klass="KBT_DELNING")
        assert svar.category == "KBT_DELNING", f"{text!r} routades till {svar.category}"


# ------------------------------------------------- Lager 0: triviala meddelanden
def test_triviala_meddelanden_far_fasta_svar_utan_llm():
    fall = [(".", "TOMT"), ("😊", "TOMT"), ("Hej!", "HEJ"), ("tack", "TACK"),
            ("Tack så mycket!", "TACK"), ("hej då", "HEJ_DA")]
    for text, forvantad in fall:
        svar, k, g = kor(text)
        assert svar.category == forvantad, f"{text!r} -> {svar.category}"
        assert not svar.llm_used and k.anrop == 0 and not g.prompter


def test_forsta_meddelandet_tack_hittar_inte_pa_fakta():
    svar, _, _ = kor("tack")
    for ord_ in ("student", "skola", "föreläsning", "klass"):
        assert ord_ not in svar.text.lower()


# ------------------------------------------------------------ Risk-state
def test_tack_efter_kris_ar_inte_ett_vanligt_tack():
    state = SessionState()
    kor("Jag vill ta livet av mig", state=state)
    svar, _, _ = kor("tack", state=state)
    assert svar.category == "RISK_UPPFOLJNING"
    assert "112" in svar.text


def test_forsiktigt_lage_efter_kris_anvands_for_llm_svar():
    state = SessionState()
    kor("Jag vill ta livet av mig", state=state)
    svar, _, gen = kor("Jag vet inte riktigt vad jag ska göra nu", state=state)
    assert "FÖRSIKTIGT LÄGE" in gen.prompter[0]
    assert "SVARSSTRUKTUR" not in gen.prompter[0]  # ingen KBT-mall efter kris


def test_risk_laget_klingar_av():
    state = SessionState()
    kor("Jag vill ta livet av mig", state=state)
    for _ in range(cfg.RISK_TURNS + 1):
        kor("Idag var en vanlig dag på jobbet", state=state)
    _, _, gen = kor("Idag var en vanlig dag på jobbet", state=state)
    assert "FÖRSIKTIGT LÄGE" not in gen.prompter[0]


# ---------------------------------------------- Lager 1/2: klassificerare + handlers
def test_kbt_delning_anvander_mallen():
    svar, _, gen = kor("Jag blev så nervös inför mötet", klass="KBT_DELNING")
    assert svar.llm_used and svar.text == "LLM-SVAR"
    assert "SVARSSTRUKTUR" in gen.prompter[0] and "GRUNDREGLER" in gen.prompter[0]


def test_kort_svar_anvander_latt_modul_utan_mall():
    _, _, gen = kor("ja", klass="KORT_SVAR")
    assert "kort svar" in gen.prompter[0]
    assert "SVARSSTRUKTUR" not in gen.prompter[0]


def test_kansliga_kategorier_ger_fast_svar_utan_llm():
    nummer = {"MISSBRUK": "Alkohollinjen", "OVERGREPP_TIDIGARE": "Brottsofferjouren",
              "BEGATT_BROTT": "jurist", "UTANFOR_OMRADE": "1177",
              "SEXUELLA_TANKAR_BARN": "Preventell", "META": "AI"}
    for kategori, nyckelord in nummer.items():
        svar, _, gen = kor("något meddelande här", klass=kategori)
        assert svar.category == kategori and not gen.prompter
        assert nyckelord in svar.text


def test_fragor_om_boten_far_fast_svar():
    for text in ("Är du en människa?", "Sparas det här någonstans?"):
        svar, k, g = kor(text)
        assert svar.category == "META" and not g.prompter and k.anrop == 0


# ------------------------------------------------------------- Robusthet
def test_trasig_klassificerare_ger_kbt_for_vanlig_text():
    svar, _, gen = kor("Jag är nervös inför presentationen imorgon", klass=RuntimeError("nere"))
    assert svar.category == "KBT_DELNING" and svar.source == "reserv" and gen.prompter


def test_trasig_klassificerare_ger_kort_svar_for_kort_text():
    svar, _, _ = kor("ok", klass=RuntimeError("nere"))
    assert svar.category == "KORT_SVAR"


def test_trasig_klassificerare_med_varningsord_ger_forsiktigt_svar():
    svar, _, gen = kor("Jag ville dö av skam igår", klass=RuntimeError("nere"))
    assert svar.category == "OSAKER" and not gen.prompter
    assert "112" in svar.text


def test_okand_kategori_hanteras_som_trasig():
    svar, _, _ = kor("Jag är nervös inför imorgon", klass="HITTEPA")
    assert svar.source == "reserv"


def test_blockerat_eller_tomt_svar_ger_fallback_inte_krasch():
    for felsvar in (None, "   ", RuntimeError("blockerat")):
        svar, _, _ = kor("Jag är nervös inför mötet", gen=FejkGenerate(felsvar))
        assert svar.text == cfg.FASTA_SVAR["FALLBACK"], f"fel för {felsvar!r}"


# ----------------------------------------------------------- Prompt-hygien
def test_inga_prompter_antar_att_anvandaren_ar_student():
    for modul in MODULER:
        assert "student" not in build_system_prompt(modul).lower(), modul


def test_grundreglerna_finns_i_alla_moduler_och_steg_5_ar_villkorat():
    for modul in MODULER:
        assert "Anta aldrig" in build_system_prompt(modul), modul
    assert "ENDAST om personen faktiskt delat" in build_system_prompt("kbt")


def test_alla_krishandlers_har_112_och_ingen_antar_student():
    for kategori in cfg.KRIS_KATEGORIER:
        text = cfg.FASTA_SVAR[kategori]
        assert "112" in text, kategori
    for kategori, text in cfg.FASTA_SVAR.items():
        assert "student" not in text.lower().replace("studenthälsan", ""), kategori


def test_alla_kategorier_har_en_handler():
    for kategori in cfg.KATEGORIER:
        assert kategori in cfg.FASTA_SVAR or kategori in cfg.MODUL_FOR, kategori


# ------------------------------------------------- RAG-sömmen (förberedd)
def test_kontext_laggs_bara_till_i_kbt_handlern():
    anrop = []

    def hamta(meddelande):
        anrop.append(meddelande)
        return "[Modul 2] Automatiska tankar är..."

    _, _, gen = kor("Jag blev så nervös inför mötet", klass="KBT_DELNING", retrieve=hamta)
    assert "KUNSKAPSUNDERLAG" in gen.prompter[0] and "Automatiska tankar" in gen.prompter[0]

    anrop.clear()
    _, _, gen2 = kor("ja", klass="KORT_SVAR", retrieve=hamta)
    assert not anrop and "KUNSKAPSUNDERLAG" not in gen2.prompter[0]

    svar, _, gen3 = kor("jag dricker för mycket", klass="MISSBRUK", retrieve=hamta)
    assert not anrop and not gen3.prompter


# ------------------------------- Backend utan minne: state ur historiken
def test_state_ur_historik_ger_samma_beteende_som_state_i_minnet():
    samtal = ["Jag vill ta livet av mig", "tack", "Jag vet inte vad jag ska göra",
              "Idag var en vanlig dag", "Idag var en vanlig dag", "Idag var en vanlig dag",
              "Idag var en vanlig dag"]
    state, historik = SessionState(), []
    for text in samtal:
        minne, _, gen_minne = kor(text, state=state, historik=historik)
        ur_historik, _, gen_hist = kor(text, state=state_from_history(historik), historik=historik)
        assert minne.category == ur_historik.category, text
        assert minne.text == ur_historik.text, text
        assert bool(gen_minne.prompter) == bool(gen_hist.prompter), text
        if gen_minne.prompter:
            assert ("FÖRSIKTIGT LÄGE" in gen_minne.prompter[0]) == \
                   ("FÖRSIKTIGT LÄGE" in gen_hist.prompter[0]), text
        historik += [{"role": "user", "text": text}, {"role": "bot", "text": minne.text}]


def test_state_ur_historik_utan_kris_ar_tomt():
    historik = [{"role": "bot", "text": "Hej!"}, {"role": "user", "text": "Hej"}]
    assert state_from_history(historik).risk_turns_left == 0


def test_gemini_historiken_borjar_alltid_med_anvandare():
    import llm
    historik = [{"role": "bot", "text": "Hej, vad bra att du är här."},
                {"role": "user", "text": "Hej"}]
    innehall = llm._till_gemini(historik)
    assert innehall[0]["role"] == "user" and len(innehall) == 1


def test_utan_kontext_inget_underlagsblock():
    assert "KUNSKAPSUNDERLAG" not in build_system_prompt("kbt")


def test_trasig_retrieve_stoppar_inte_svaret():
    def trasig(meddelande):
        raise RuntimeError("chroma nere")

    svar, _, gen = kor("Jag blev så nervös inför mötet", retrieve=trasig)
    assert svar.llm_used and "KUNSKAPSUNDERLAG" not in gen.prompter[0]


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
