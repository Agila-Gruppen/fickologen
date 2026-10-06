from dataclasses import dataclass


@dataclass
class ContextChunk:
    """A piece of retrieved text and where it came from."""
    text: str
    source: str


def retrieve_context(query: str, k: int = 4) -> list[ContextChunk]:
    """
    Fetch the text chunks most relevant to the user's message.

    RAG is not connected yet, so this returns nothing and the chat runs on the
    system prompt alone. To connect ChromaDB, query the collection here and
    map the hits to ContextChunk - the chat service already adds whatever this
    returns to the prompt and reports it as sources.

    Args:
        query: The user's latest message
        k: Maximum number of chunks to return

    Returns:
        Relevant chunks, most relevant first
    """
    return []
