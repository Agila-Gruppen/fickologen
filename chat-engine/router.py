"""Routern: bestämmer HUR ett meddelande ska hanteras.

Ren Python, inga beroenden på Gemini eller FastAPI. LLM-anropen skickas in som
funktioner (classify_fn, generate_fn, retrieve_fn), vilket gör routern testbar
med fejkade LLM:er och gör att backend (PLAN-116) bara kan anropa route().

Lager 0: regler    (hård krislista, triviala meddelanden, frågor om boten)
Lager 1: klassificerare (LLM, via classify_fn)
Lager 2: handler   (fast text, eller LLM med rätt promptmodul)
"""
import logging
import re
from dataclasses import dataclass

import safety_config as cfg
from prompts import build_system_prompt

log = logging.getLogger("fickologen.router")


@dataclass
class SessionState:
    """Lever under en konversation. Efter en kris håller boten sig försiktig."""
    risk_turns_left: int = 0


@dataclass
class Reply:
    text: str
    category: str
    source: str       # "regel" | "klassificerare" | "reserv"
    llm_used: bool    # True om generate_fn anropades


def _kompilera(monster):
    return [re.compile(m, re.IGNORECASE) for m in monster]


_HARD = {k: _kompilera(v) for k, v in cfg.HARDA_MONSTER.items()}
_SOFT = _kompilera(cfg.MJUKA_MONSTER)
_META = _kompilera(cfg.META_MONSTER)
_TRIVIAL = {k: re.compile(v, re.IGNORECASE) for k, v in cfg.TRIVIALA_MONSTER.items()}


def normalisera(text: str) -> str:
    return " ".join(text.lower().split())


def hard_match(t: str) -> str | None:
    traffar = [k for k in cfg.HARD_PRIORITET if any(p.search(t) for p in _HARD[k])]
    return traffar[0] if traffar else None


def trivial_match(t: str) -> str | None:
    if not any(c.isalnum() for c in t):
        return "TOMT"
    utan_tecken = t.strip(" .,!?…:;-\"'")
    for kategori, monster in _TRIVIAL.items():
        if monster.match(utan_tecken):
            return kategori
    return None


def mjuka_traffar(t: str) -> list[str]:
    return [m.group(0) for p in _SOFT if (m := p.search(t))]


_KRISSVAR = {cfg.FASTA_SVAR[k].strip() for k in cfg.FORSIKTIGA_KATEGORIER}


def state_from_history(history) -> SessionState:
    """Bygger om SessionState ur samtalet, för en backend utan minne mellan anrop.

    Har boten nyligen (inom RISK_TURNS svar) skickat en krishanterartext räknas
    försiktigt läge som aktivt, med samma antal turer kvar som om state hade
    legat kvar i minnet.
    """
    botsvar = [m["text"].strip() for m in history if m["role"] == "bot"]
    for avstand, text in enumerate(reversed(botsvar[-cfg.RISK_TURNS:])):
        if text in _KRISSVAR:
            return SessionState(risk_turns_left=cfg.RISK_TURNS - avstand)
    return SessionState()


def route(message, history, state, classify_fn=None, generate_fn=None, retrieve_fn=None) -> Reply:
    """history: lista av {"role": "user"|"bot", "text": str} (tidigare turer)."""
    t = normalisera(message)
    risk_aktiv = state.risk_turns_left > 0
    state.risk_turns_left = max(0, state.risk_turns_left - 1)  # varje tur "kyler av"

    # ---- Lager 0a: hård krislista (ingen LLM)
    hard = hard_match(t)
    if hard:
        state.risk_turns_left = cfg.RISK_TURNS
        return Reply(cfg.FASTA_SVAR[hard], hard, "regel", False)

    # ---- Lager 0b: triviala meddelanden (ingen LLM, ingen mall)
    trivial = trivial_match(t)
    if trivial:
        if risk_aktiv and trivial in ("TACK", "HEJ_DA", "TOMT"):
            return Reply(cfg.FASTA_SVAR["RISK_UPPFOLJNING"], "RISK_UPPFOLJNING", "regel", False)
        return Reply(cfg.FASTA_SVAR[trivial], trivial, "regel", False)

    # ---- Lager 0c: frågor om boten/appen (fast svar, LLM:en får inte gissa)
    if any(p.search(t) for p in _META):
        return Reply(cfg.FASTA_SVAR["META"], "META", "regel", False)

    # ---- Lager 1: klassificerare
    soft = mjuka_traffar(t)
    kategori, kalla = None, "klassificerare"
    if classify_fn is not None:
        try:
            kategori = classify_fn(message, history, soft)
        except Exception as e:
            log.warning("classify_fn misslyckades: %r", e)
            kategori = None
    if kategori not in cfg.KATEGORIER:  # saknas, trasig eller okänd
        kalla = "reserv"
        if soft:
            kategori = "OSAKER"
        elif len(t.split()) <= 3:
            kategori = "KORT_SVAR"
        else:
            kategori = "KBT_DELNING"

    # ---- Lager 2: handler
    if kategori in cfg.FASTA_SVAR:  # fast text (kris, känsligt, OSAKER)
        if kategori in cfg.FORSIKTIGA_KATEGORIER:
            state.risk_turns_left = cfg.RISK_TURNS
        return Reply(cfg.FASTA_SVAR[kategori], kategori, kalla, False)

    if generate_fn is None:
        raise ValueError(f"generate_fn krävs för kategorin {kategori}")
    modul = "forsiktig" if risk_aktiv else cfg.MODUL_FOR[kategori]

    kontext = None
    if retrieve_fn is not None and modul == "kbt":  # RAG: bara KBT-handlern
        try:
            kontext = retrieve_fn(message)
        except Exception as e:
            log.warning("retrieve_fn misslyckades: %r", e)
            kontext = None

    samtal = list(history) + [{"role": "user", "text": message}]
    try:
        text = generate_fn(build_system_prompt(modul, kontext), samtal)
    except Exception as e:
        log.warning("generate_fn misslyckades: %r", e)
        text = None
    if not text or not text.strip():  # Gemini kan blockera eller ge tomt svar
        return Reply(cfg.FASTA_SVAR["FALLBACK"], kategori, "reserv", True)
    return Reply(text.strip(), kategori, kalla, True)
