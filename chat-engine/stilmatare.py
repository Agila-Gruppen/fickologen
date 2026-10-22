"""Stilmätare: mäter hur stolpiga och upprepande botens svar är (PLAN-113, naturligare ton).

Kör:   python chat-engine/stilmatare.py                  # sammanfattning
       python chat-engine/stilmatare.py --visa           # visar också varje svar
       python chat-engine/stilmatare.py --spara fil.json # sparar svaren
       python chat-engine/stilmatare.py --analysera fil.json  # räknar om sparade svar utan nya anrop

Kör ca 15 påhittade meddelanden genom samma kedja som version 3 (routing + RAG), med riktiga
Gemini-anrop (ca 40 stycken), och räknar mönster som gjorde svaren ensidiga. Siffrorna går att
jämföra före och efter en ändring i prompts.py. Räknar bara svar som Gemini skrivit, inte de fasta
krisdtexterna.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "knowledge"))

ENSKILDA = [
    # kunskapsfrågor
    "Vad är tankeläsning?",
    "Hur länge ska en exponeringsövning pågå?",
    "Vad är säkerhetsbeteenden och varför är de ett problem?",
    "Vad är skillnaden mellan bakslag och återfall?",
    "Hur säger jag nej utan att få dåligt samvete?",
    "Hur inleder jag en konversation med någon jag inte känner?",
    # personliga inlägg
    "Jag blev så nervös på mötet idag",
    "Jag tänker alltid att alla tycker att jag är tråkig",
    "Jag vågade räcka upp handen på föreläsningen men blev röd i ansiktet",
    "Jag hann inte svara när chefen frågade något och kände mig dum",
    "Jag är rädd för att åka på festen på lördag",
]
DIALOG = ["Vad är tankeläsning?", "och hur övar jag på det?", "Vad är tankeläsning?"]  # sista är samma fråga igen

MONSTER = {
    "börjar med tack/beröm": r"^\W*(tack|det är en (jätte)?bra|vad bra|vilken (bra|viktig)|en (jätte)?bra fråga|bra fråga)",
    '"kort sagt"/"det korta svaret"': r"\bkort sagt\b|\bdet korta svaret\b",
    '"misslyckande"': r"misslyck",
    '"tumregel"/"konkret verktyg"': r"tumregel|konkret verktyg",
    '"hjärnan skyddar oss"': r"(skydda|skyddar|skydd)\W+(oss|dig)|hjärnans? .{0,25}skydd",
    'börjar med "Du ..." (upprepar)': r"^\W*du\s",
    '"det låter jobbigt"': r"det låter (som|så)?\s*(att )?(en |ett )?(riktigt |väldigt )?(jobbig|tuff|jobbigt|tufft)",
    '"vill du ha ett exempel"': r"vill du ha (ett|några) exempel",
    "avslutar med fråga": None,   # specialfall: en fråga i de två sista meningarna
    'frågan innehåller "brukar"': None,
}


def meningar(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def analysera(svar: list[str]) -> dict:
    """Andel svar (0–1) som har varje mönster, plus genomsnittlig längd. Tom lista ger tomma värden."""
    n = len(svar)
    if n == 0:
        return {"antal": 0}
    res = {"antal": n}
    for namn, monster in MONSTER.items():
        if monster is not None:
            traffar = sum(1 for t in svar if re.search(monster, t, re.IGNORECASE))
        elif namn == "avslutar med fråga":
            traffar = sum(1 for t in svar if "?" in " ".join(meningar(t)[-2:]))
        else:
            traffar = sum(1 for t in svar if "?" in " ".join(meningar(t)[-2:]) and "brukar" in " ".join(meningar(t)[-2:]).lower())
        res[namn] = traffar / n
    langder = [len(t.split()) for t in svar]
    res["genomsnitt ord"] = sum(langder) / n
    res["andel över 150 ord"] = sum(1 for x in langder if x > 150) / n
    return res


def upprepade_oppningar(svar: list[str]) -> int:
    """Hur många svar i ett samtal som börjar med samma tre ord som ett tidigare svar."""
    sett, upprepningar = set(), 0
    for t in svar:
        borjan = " ".join(re.findall(r"\w+", t.lower())[:3])
        upprepningar += borjan in sett
        sett.add(borjan)
    return upprepningar


def _kedja():
    import llm
    import router
    try:
        import knowledge_retriever
    except Exception:
        knowledge_retriever = None

    def retrieve(query):
        if knowledge_retriever is None:
            return None
        traffar = knowledge_retriever.retrieve(query)
        return "\n\n".join(f"[{h.source}]\n{h.text}" for h in traffar) if traffar else None

    def svara(text, historik):
        reply = router.route(text, historik, router.state_from_history(historik),
                             classify_fn=llm.classify, generate_fn=llm.generate, retrieve_fn=retrieve)
        return reply

    return svara


def _skriv(res, kategorier, antal_meddelanden, dialog_svar):
    print()
    print(f"STILMÄTARE: {res['antal']} svar skrivna av Gemini (av {antal_meddelanden} meddelanden)")
    if kategorier:
        print("kategorier:", kategorier)
    for namn in MONSTER:
        print(f"  {namn:34} {res[namn] * 100:5.0f} %")
    print(f"  {'genomsnitt ord':34} {res['genomsnitt ord']:5.0f}")
    print(f"  {'andel över 150 ord':34} {res['andel över 150 ord'] * 100:5.0f} %")
    print(f"  {'upprepade öppningar i dialogen':34} {upprepade_oppningar(dialog_svar):5d} (av {len(dialog_svar)} svar)")


def main() -> None:
    import json
    if "--analysera" in sys.argv:
        data = json.loads(Path(sys.argv[sys.argv.index("--analysera") + 1]).read_text(encoding="utf-8"))
        _skriv(analysera(data["skrivna"]), data.get("kategorier"), data["meddelanden"], data["dialog"])
        return
    visa = "--visa" in sys.argv
    svara = _kedja()
    skrivna, kategorier, alla = [], {}, []
    for text in ENSKILDA:
        r = svara(text, [])
        kategorier[r.category] = kategorier.get(r.category, 0) + 1
        alla.append((text, r))
        if r.llm_used:
            skrivna.append(r.text)
    hist, dialog_svar = [], []
    for text in DIALOG:
        r = svara(text, hist)
        alla.append((text, r))
        hist += [{"role": "user", "text": text}, {"role": "bot", "text": r.text}]
        if r.llm_used:
            skrivna.append(r.text)
            dialog_svar.append(r.text)
    if visa:
        for text, r in alla:
            print(f"\n> {text}   [{r.category}]\n{r.text}")
    res = analysera(skrivna)
    if "--spara" in sys.argv:
        Path(sys.argv[sys.argv.index("--spara") + 1]).write_text(
            json.dumps({"skrivna": skrivna, "dialog": dialog_svar, "kategorier": kategorier, "meddelanden": len(alla)}, ensure_ascii=False),
            encoding="utf-8")
    _skriv(res, kategorier, len(alla), dialog_svar)


if __name__ == "__main__":
    main()
