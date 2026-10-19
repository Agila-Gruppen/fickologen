import sys
from dataclasses import dataclass
from pathlib import Path

# Sökningen ligger i chat-engine/knowledge/ (platta imports, som resten av chat-engine).
CHAT_ENGINE_DIR = Path(__file__).resolve().parents[3] / "chat-engine"


@dataclass
class ContextChunk:
    """A piece of retrieved text and where it came from."""
    text: str
    source: str


def _retriever():
    for directory in (CHAT_ENGINE_DIR, CHAT_ENGINE_DIR / "knowledge"):
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))
    import knowledge_retriever
    return knowledge_retriever


def retrieve_context(query: str, k: int = 4) -> list[ContextChunk]:
    """
    Fetch the text chunks most relevant to the user's message.

    The knowledge material is an encrypted package (chat-engine/knowledge/material.enc)
    that is opened with the KNOWLEDGE_KEY environment variable. Without the file or the
    key this returns nothing, and the chat runs on the system prompt alone. Any error
    also returns nothing, so retrieval can never break a reply.

    Args:
        query: The user's latest message
        k: Maximum number of chunks to return

    Returns:
        Relevant chunks, most relevant first
    """
    try:
        hits = _retriever().retrieve(query, k=k)
    except Exception as exc:
        print(f"Retrieval failed: {exc!r}")
        return []
    return [ContextChunk(text=hit.text, source=hit.source) for hit in hits]
