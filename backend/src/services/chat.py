import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from google import genai

from ..schemas.chat import ChatMessage
from .retrieval import ContextChunk, retrieve_context

load_dotenv()

MODEL = "gemini-3.5-flash-lite"
PROMPT_PATH = Path(__file__).resolve().parents[3] / "chat-engine" / "prompt_v1.txt"


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


async def generate_reply(messages: list[ChatMessage]) -> tuple[str, list[ContextChunk]]:
    """
    Generate the assistant's next reply.

    Args:
        messages: The conversation so far, ending with the user's new message

    Returns:
        The reply text and the context chunks it was grounded in

    Raises:
        RuntimeError: If Gemini returns an empty reply
    """
    chunks = retrieve_context(messages[-1].content)
    response = await _client().aio.models.generate_content(
        model=MODEL,
        contents=_to_gemini_contents(messages),
        config={"system_instruction": _system_instruction(chunks)},
    )
    if not response.text:
        raise RuntimeError("Gemini returned an empty reply")
    return response.text, chunks
