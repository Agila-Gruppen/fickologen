from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """
    A single message in the conversation.
    """
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    """
    Schema for a chat request.
    Contains the whole conversation so far, ending with the user's new message.
    """
    messages: list[ChatMessage] = Field(..., min_length=1)
    engine: Literal["router", "legacy"] = "router"


class ChatSource(BaseModel):
    """
    A document the reply was grounded in (filled in once RAG is connected).
    """
    source: str
    text: str


class ChatResponse(BaseModel):
    """
    Schema for a chat response.

    category, via and llm_used describe how the router handled the message and
    are only set by the router engine.
    """
    reply: str
    sources: list[ChatSource] = []
    engine: Literal["router", "legacy"] = "router"
    category: str | None = None
    via: str | None = None
    llm_used: bool | None = None
