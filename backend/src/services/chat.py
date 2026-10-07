import asyncio
import os
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from dotenv import load_dotenv
from google import genai

from ..schemas.chat import ChatMessage
from .retrieval import ContextChunk, retrieve_context

load_dotenv()

MODEL = "gemini-3.5-flash-lite"
CHAT_ENGINE_DIR = Path(__file__).resolve().parents[3] / "chat-engine"
PROMPT_PATH = CHAT_ENGINE_DIR / "prompt_v1.txt"


@dataclass
class ChatResult:
    """A reply plus how it was produced (the router fills in category, via and llm_used)."""
    reply: str
    chunks: list[ContextChunk] = field(default_factory=list)
    category: str | None = None
    via: str | None = None
    llm_used: bool | None = None


@lru_cache
def _client() -> genai.Client:
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


@lru_cache
def _system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _system_instruction(chunks: list[ContextChunk]) -> str:
    """The system prompt, extended with retrieved context when there is any."""
    if not chunks:
        return _system_prompt()
    context = "\n\n".join(f"[{chunk.source}]\n{chunk.text}" for chunk in chunks)
    return (
        f"{_system_prompt()}\n\n"
        "KUNSKAPSUNDERLAG: Använd följande utdrag som stöd när de är relevanta "
        "för det användaren skriver. Hitta inte på innehåll utöver dem.\n\n"
        f"{context}"
    )


def _to_gemini_contents(messages: list[ChatMessage]) -> list[dict]:
    """Convert the conversation to Gemini's format, which must start with a user turn."""
    while messages and messages[0].role != "user":
        messages = messages[1:]
    return [
        {
            "role": "user" if message.role == "user" else "model",
            "parts": [{"text": message.content}],
        }
        for message in messages
    ]


async def _generate_reply_legacy(messages: list[ChatMessage]) -> ChatResult:
    """The original engine: one prompt template for every message."""
    chunks = retrieve_context(messages[-1].content)
    response = await _client().aio.models.generate_content(
        model=MODEL,
        contents=_to_gemini_contents(messages),
        config={"system_instruction": _system_instruction(chunks)},
    )
    if not response.text:
        raise RuntimeError("Gemini returned an empty reply")
    return ChatResult(reply=response.text, chunks=chunks)


@lru_cache
def _load_engine() -> SimpleNamespace:
    """
    Load the router from chat-engine/.

    Its modules use flat imports, so the folder is put on sys.path. Loading is
    lazy, so the legacy engine keeps working even if chat-engine/ is missing.
    """
    if str(CHAT_ENGINE_DIR) not in sys.path:
        sys.path.insert(0, str(CHAT_ENGINE_DIR))
    import llm
    import router

    return SimpleNamespace(
        route=router.route,
        state_from_history=router.state_from_history,
        classify=llm.classify,
        generate=llm.generate,
    )


async def _generate_reply_router(messages: list[ChatMessage]) -> ChatResult:
    """
    The router engine: fixed, reviewed texts for crisis and sensitive topics,
    short fixed replies for greetings and thanks, and Gemini with the right
    prompt module for everything else.
    """
    engine = _load_engine()
    # The backend keeps no state between requests, so the router rebuilds its
    # "careful mode" from the conversation itself.
    history = [
        {"role": "user" if message.role == "user" else "bot", "text": message.content}
        for message in messages[:-1]
    ]
    used_chunks: list[ContextChunk] = []

    def retrieve(query: str) -> str | None:
        # The router only calls this for ordinary CBT questions, never for crisis.
        chunks = retrieve_context(query)
        used_chunks[:] = chunks
        if not chunks:
            return None
        return "\n\n".join(f"[{chunk.source}]\n{chunk.text}" for chunk in chunks)

    # The router and its Gemini client are synchronous, so keep them off the event loop.
    reply = await asyncio.to_thread(
        engine.route,
        messages[-1].content,
        history,
        engine.state_from_history(history),
        engine.classify,
        engine.generate,
        retrieve,
    )
    return ChatResult(
        reply=reply.text,
        chunks=used_chunks,
        category=reply.category,
        via=reply.source,
        llm_used=reply.llm_used,
    )


async def generate_reply(
    messages: list[ChatMessage],
    engine: Literal["router", "legacy"] = "router",
) -> ChatResult:
    """
    Generate the assistant's next reply.

    Args:
        messages: The conversation so far, ending with the user's new message
        engine: "router" for the routing engine, "legacy" for the original single-template engine

    Returns:
        The reply, the context chunks it was grounded in, and how it was produced

    Raises:
        RuntimeError: If the legacy engine gets an empty reply from Gemini
    """
    if engine == "legacy":
        return await _generate_reply_legacy(messages)
    return await _generate_reply_router(messages)
