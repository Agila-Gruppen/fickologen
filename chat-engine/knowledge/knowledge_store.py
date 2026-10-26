"""Krypterat kunskapspaket: bitar + deras vektorer i en enda fil (material.enc).

Varför så här (PLAN-113):
  - Modulernas text ska inte ligga som läsbar text i det publika repot. Paketet är
    krypterat (Fernet, AES) och kan bara läsas av den som har nyckeln (KNOWLEDGE_KEY).
  - Servern behöver ingen extra databas eller volym: paketet följer med koden och
    avkrypteras i minnet vid start. Sökningen är vanlig vektormatematik. Med ca 275
    bitar är en vektordatabas onödig.
  - Saknas fil eller nyckel är kunskapen helt enkelt av, och chatten fungerar som förut.

Beroenden: bara standardbiblioteket och `cryptography` (finns redan i requirements.txt).
"""
import base64
import json
import logging
import os
from array import array
from dataclasses import dataclass
from math import sqrt
from operator import mul
from pathlib import Path

log = logging.getLogger("fickologen.knowledge")

DEFAULT_PATH = Path(__file__).parent / "material.enc"


def new_key() -> str:
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


def normalize(vector: list[float]) -> list[float]:
    norm = sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def pack(records: list[dict], vectors: list[list[float]], model: str, key: str) -> bytes:
    """Krypterar bitarna och deras (normaliserade) vektorer till en bytesträng."""
    from cryptography.fernet import Fernet
    if len(records) != len(vectors) or not records:
        raise ValueError("records och vectors måste vara lika många och inte tomma")
    packed = array("f")
    for vector in vectors:
        packed.extend(normalize(vector))
    payload = {
        "model": model,
        "dim": len(vectors[0]),
        "records": records,
        "vectors": base64.b64encode(packed.tobytes()).decode(),
    }
    return Fernet(key.encode()).encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8"))


@dataclass
class KnowledgeStore:
    records: list[dict]
    dim: int
    model: str
    vectors: array

    def search(self, query_vector: list[float], k: int = 4, min_score: float = 0.0) -> list[tuple[float, dict]]:
        """De k bitar som liknar frågan mest (cosinus-likhet), bäst först, minst min_score."""
        if len(query_vector) != self.dim:
            raise ValueError(f"fel vektorlängd: {len(query_vector)} (förväntade {self.dim})")
        q = normalize(query_vector)
        scored = []
        for i, record in enumerate(self.records):
            row = self.vectors[i * self.dim:(i + 1) * self.dim]
            scored.append((sum(map(mul, q, row)), record))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [(s, r) for s, r in scored[:k] if s >= min_score]


def unpack(blob: bytes, key: str) -> KnowledgeStore:
    """Avkrypterar paketet. Fel nyckel eller skadad fil ger cryptography.fernet.InvalidToken."""
    from cryptography.fernet import Fernet
    payload = json.loads(Fernet(key.encode()).decrypt(blob).decode("utf-8"))
    vectors = array("f")
    vectors.frombytes(base64.b64decode(payload["vectors"]))
    return KnowledgeStore(records=payload["records"], dim=payload["dim"], model=payload["model"], vectors=vectors)


def _read_key() -> str | None:
    """KNOWLEDGE_KEY ur miljön, annars ur chat-engine/.env eller .env i repots rot (om dotenv finns)."""
    key = os.environ.get("KNOWLEDGE_KEY")
    if key:
        return key
    try:
        from dotenv import load_dotenv
        here = Path(__file__).parent
        for env_file in (here.parent / ".env", here.parent.parent / ".env"):
            load_dotenv(env_file)
    except ImportError:
        pass
    return os.environ.get("KNOWLEDGE_KEY")


def load_store(path: str | Path | None = None, key: str | None = None) -> KnowledgeStore | None:
    """Läser paketet. Returnerar None (och loggar varför) om kunskapen inte kan användas."""
    path = Path(path or os.environ.get("KNOWLEDGE_FILE") or DEFAULT_PATH)
    key = key or _read_key()
    if not path.exists():
        log.warning("Kunskapspaket saknas (%s): kunskapen är avstängd", path)
        return None
    if not key:
        log.warning("KNOWLEDGE_KEY saknas: kunskapen är avstängd")
        return None
    try:
        return unpack(path.read_bytes(), key)
    except Exception as exc:
        log.warning("Kunde inte öppna kunskapspaketet (fel nyckel?): %r", exc)
        return None
