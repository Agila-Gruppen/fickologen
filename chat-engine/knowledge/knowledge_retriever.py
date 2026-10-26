"""Slår upp de bitar i kunskapsmaterialet som bäst passar en användares fråga.

Anropas av backend/src/services/retrieval.py, och bara när routern har bedömt att
meddelandet är en vanlig KBT-fråga (aldrig vid kris). Alla fel ger en tom lista, så
att chatten fortsätter att fungera utan kunskapsunderlag.
"""
import logging
from dataclasses import dataclass
from functools import lru_cache

import knowledge_store

log = logging.getLogger("fickologen.knowledge")

TOP_K = 4
# Bitar med lägre likhet än så här skickas inte med. Mätt med evaluate.py: relevanta kunskapsfrågor fick
# minst 0,73, orelaterade frågor högst 0,58, och vardagliga samtalsmeddelanden som "tack, det hjälpte" upp
# till 0,69. 0,70 släpper igenom kunskapsfrågor men inte småprat. Justera om materialet eller modellen ändras.
MIN_SCORE = 0.70


@dataclass
class Hit:
    score: float
    id: str
    source: str   # t.ex. "Modul 3: Tankefällor > Tankeläsning"
    text: str     # själva texten (utan rubrikväg)
    typ: str


@lru_cache(maxsize=1)
def _default_store():
    return knowledge_store.load_store()


def reset() -> None:
    """Glöm det inlästa paketet (används av tester, och om nyckeln ändras)."""
    _default_store.cache_clear()


def _embed_query(query: str) -> list[float]:
    import llm  # lazy, så att modulen går att importera utan google-genai
    return llm.embed(query, task="RETRIEVAL_QUERY")


def retrieve(query: str, k: int = TOP_K, min_score: float = MIN_SCORE, store=None, embed_fn=None) -> list[Hit]:
    store = store if store is not None else _default_store()
    if store is None or not query.strip():
        return []
    try:
        vector = (embed_fn or _embed_query)(query)
        found = store.search(vector, k=k, min_score=min_score)
    except Exception as exc:
        log.warning("Sökning i kunskapsmaterialet misslyckades: %r", exc)
        return []
    return [
        Hit(score=score, id=r["id"], source=r["source"], text=r["text"], typ=r.get("typ", ""))
        for score, r in found
    ]
