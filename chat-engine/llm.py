"""All kommunikation med Gemini. Byter ni leverantör ändras bara den här filen.

Importerna sker först vid första anropet, så att router och tester fungerar
utan nyckel och utan att google-genai är installerat.
"""
import os
from pathlib import Path

import safety_config as cfg

MODELL = "gemini-3.5-flash-lite"  # kontrollera exakt sträng i AI Studio
_klient = None

KLASSIFICERINGS_PROMPT = """\
Du klassificerar meddelanden till en stödapp för social ångest.
Välj EXAKT EN kategori för det SENASTE meddelandet. Väg risk tungt: är du osäker
mellan en riskkategori och en vanlig kategori, välj riskkategorin.
Svara med enbart kategorinamnet, inget annat.

KATEGORIER:
{beskrivning}

Tidigare i samtalet (kan vara tomt):
{historik}

Varningsord som regelmotorn hittade (kan vara tomt): {soft}

SENASTE MEDDELANDET:
{meddelande}
"""


def _hamta_klient():
    global _klient
    if _klient is None:
        from dotenv import load_dotenv
        from google import genai

        load_dotenv(Path(__file__).parent / ".env")  # fungerar oavsett var du kör från
        _klient = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _klient


def _till_gemini(historik):
    """Gemini kräver att samtalet börjar med en användartur, så en inledande
    hälsning från boten (som appen visar först) tas bort."""
    historik = list(historik)
    while historik and historik[0]["role"] != "user":
        historik = historik[1:]
    return [
        {"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["text"]}]}
        for m in historik
    ]


def generate(system_prompt, historik):
    """Svar från Gemini. Kan returnera None om Gemini blockerar svaret."""
    svar = _hamta_klient().models.generate_content(
        model=MODELL,
        contents=_till_gemini(historik),
        config={"system_instruction": system_prompt},
    )
    return svar.text


def classify(meddelande, historik, soft_traffar):
    """Returnerar en kategori ur cfg.KATEGORIER, eller None om svaret inte gick att tolka."""
    senaste = "\n".join(
        f"{'Användare' if m['role'] == 'user' else 'Bot'}: {m['text']}" for m in historik[-4:]
    )
    prompt = KLASSIFICERINGS_PROMPT.format(
        beskrivning=cfg.KATEGORIBESKRIVNING,
        historik=senaste or "(inget)",
        soft=", ".join(soft_traffar) or "(inga)",
        meddelande=meddelande,
    )
    svar = _hamta_klient().models.generate_content(
        model=MODELL, contents=prompt, config={"temperature": 0}
    )
    ord_ = (svar.text or "").strip().upper().split()
    token = ord_[0].strip(".:,;\"'`*") if ord_ else ""
    return token if token in cfg.KATEGORIER else None
