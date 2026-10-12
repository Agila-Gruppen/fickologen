"""Bäddar in kunskapsmaterialet och skriver det krypterade paketet material.enc (PLAN-113).

Körs lokalt av den som har modulerna, en gång (och om materialet ändras):

    python chat-engine/knowledge/ingest.py --new-key   # skriver ut en ny nyckel (spara den!)
    python chat-engine/knowledge/ingest.py --dry-run   # visar antal bitar, anropar inget
    python chat-engine/knowledge/ingest.py             # bäddar in och skriver material.enc

Nyckeln läses ur KNOWLEDGE_KEY (miljövariabel, chat-engine/.env eller .env i repots rot).
Samma nyckel ska läggas som variabeln KNOWLEDGE_KEY i Railway. Utan den är kunskapen avstängd.

OBS: varje bit skickas till Gemini för att få sin vektor. Gratisnivån kan användas av Google för
produktförbättring, så kör bara detta om du är bekväm med att modultexten skickas dit.
Mellanresultat sparas i data/_embeddings_cache.json (ignoreras av git), så att ett avbrott
(t.ex. slut på kvot) kan fortsätta där det slutade.
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import chunker  # noqa: E402
import knowledge_store  # noqa: E402

DATA_DIR = HERE / "data"
CACHE_FILE = DATA_DIR / "_embeddings_cache.json"
PAUSE_SECONDS = 0.6   # lugnt tempo mot kvotgränsen
MAX_RETRIES = 6


def to_records(chunks) -> list[dict]:
    return [
        {"id": c.id, "source": " > ".join([c.titel] + c.path), "text": c.body, "typ": c.typ, "doc_id": c.doc_id}
        for c in chunks
    ]


def embed_all(texts: list[str], embed_fn, cache: dict, pause: float = 0.0, sleep=time.sleep, on_progress=None) -> list[list[float]]:
    """En vektor per text. Redan inbäddade texter (samma innehåll) hämtas ur cachen.

    Vid fel (t.ex. kvot) görs nya försök med växande väntetid. Efter MAX_RETRIES avbryts körningen,
    och det som hunnits klart ligger kvar i cachen.
    """
    vectors = []
    for i, text in enumerate(texts, start=1):
        key = hashlib.sha1(text.encode("utf-8")).hexdigest()
        if key not in cache:
            for attempt in range(MAX_RETRIES):
                try:
                    cache[key] = embed_fn(text)
                    break
                except Exception:
                    if attempt == MAX_RETRIES - 1:
                        raise
                    sleep(2 ** attempt * 2)
            sleep(pause)
        vectors.append(cache[key])
        if on_progress and i % 25 == 0:
            on_progress(i, len(texts))
    return vectors


def _load_env() -> None:
    from dotenv import load_dotenv
    load_dotenv(HERE.parent / ".env")
    load_dotenv(HERE.parent.parent / ".env")


def main() -> None:
    if "--new-key" in sys.argv:
        print(knowledge_store.new_key())
        return
    chunks = chunker.chunk_directory(DATA_DIR)
    if not chunks:
        sys.exit(f"Inga markdown-filer i {DATA_DIR}. Kör först convert_docx.py.")
    print(f"{len(chunks)} bitar från {len({c.doc_id for c in chunks})} filer")
    if "--dry-run" in sys.argv:
        print("Torrkörning: inga anrop gjordes. Det blir ett anrop till Gemini per bit.")
        return

    _load_env()
    key = os.environ.get("KNOWLEDGE_KEY")
    if not key:
        sys.exit("KNOWLEDGE_KEY saknas. Skapa en med --new-key och lägg den i chat-engine/.env")
    import llm

    cache = json.loads(CACHE_FILE.read_text(encoding="utf-8")) if CACHE_FILE.exists() else {}
    texts = [c.text for c in chunks]  # rubrikväg + text, så att korta bitar får sitt sammanhang
    try:
        vectors = embed_all(
            texts, lambda t: llm.embed(t, task="RETRIEVAL_DOCUMENT"), cache, pause=PAUSE_SECONDS,
            on_progress=lambda i, n: print(f"  {i}/{n}"),
        )
    finally:
        CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")
    blob = knowledge_store.pack(to_records(chunks), vectors, llm.EMBEDDING_MODELL, key)
    knowledge_store.DEFAULT_PATH.write_bytes(blob)
    print(f"Skrev {knowledge_store.DEFAULT_PATH} ({len(blob) / 1e6:.1f} MB, krypterad)")


if __name__ == "__main__":
    main()
