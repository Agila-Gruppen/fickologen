"""Mäter hur bra sökningen är, med frågorna i eval_questions.json (PLAN-113).

    python chat-engine/knowledge/evaluate.py

Kräver att material.enc och KNOWLEDGE_KEY finns, samt GEMINI_API_KEY (ett anrop per fråga).
Frågor med tom lista under "moduler" är medvetet orelaterade: de ska INTE ge några träffar.
Skriptet föreslår ett värde för MIN_SCORE i knowledge_retriever.py.
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import knowledge_retriever  # noqa: E402
import knowledge_store  # noqa: E402


def module_of(hit_id: str) -> int:
    # id börjar med "modul-03-..."
    try:
        return int(hit_id.split("-")[1])
    except (IndexError, ValueError):
        return -1


def is_hit(hit, question: dict) -> bool:
    if module_of(hit.id) not in question["moduler"]:
        return False
    wanted = question.get("rubrik", "").lower()
    return not wanted or wanted in hit.source.lower()


def evaluate(questions: list[dict], store, embed_fn, k: int = 4) -> dict:
    relevant_scores, offtopic_top, results, found_count, relevant_count = [], [], [], 0, 0
    for q in questions:
        hits = knowledge_retriever.retrieve(q["fråga"], k=k, min_score=0.0, store=store, embed_fn=embed_fn)
        top = hits[0].score if hits else 0.0
        if q["moduler"]:
            relevant_count += 1
            ok = any(is_hit(h, q) for h in hits)
            found_count += ok
            relevant_scores.append(top)
        else:
            ok = None
            offtopic_top.append(top)
        results.append((q["fråga"], ok, top, hits[0].source if hits else "-"))
    lowest_relevant = min(relevant_scores) if relevant_scores else 0.0
    highest_offtopic = max(offtopic_top) if offtopic_top else 0.0
    return {
        "results": results, "träff": found_count, "relevanta": relevant_count,
        "lägsta_relevanta": lowest_relevant, "högsta_orelaterad": highest_offtopic,
        "förslag_min_score": round((lowest_relevant + highest_offtopic) / 2, 2) if offtopic_top else None,
    }


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv(HERE.parent / ".env")
    load_dotenv(HERE.parent.parent / ".env")
    store = knowledge_store.load_store()
    if store is None:
        sys.exit("Hittar inget öppningsbart material.enc (saknas filen, eller KNOWLEDGE_KEY?). Kör ingest.py först.")
    questions = json.loads((HERE / "eval_questions.json").read_text(encoding="utf-8"))
    import llm
    report = evaluate(questions, store, lambda t: llm.embed(t, task="RETRIEVAL_QUERY"))
    for question, ok, top, source in report["results"]:
        mark = "  –" if ok is None else (" OK" if ok else "MISS")
        print(f"{mark}  {top:.2f}  {question[:58]:58} -> {source[:60]}")
    print(f"\nRätt avsnitt bland de {4} bästa: {report['träff']}/{report['relevanta']}")
    print(f"Lägsta toppoäng bland relevanta frågor: {report['lägsta_relevanta']:.2f}")
    print(f"Högsta toppoäng bland orelaterade frågor: {report['högsta_orelaterad']:.2f}")
    if report["förslag_min_score"] is not None:
        print(f"Förslag på MIN_SCORE i knowledge_retriever.py: {report['förslag_min_score']}")


if __name__ == "__main__":
    main()
