from typing import Literal, Optional

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
    engine: Literal["legacy", "router", "rag"] = "rag"
    conversation_id: Optional[int] = Field(
        default=None,
        description="Which conversation to append to. Omit (null) to start a new one.",
    )
    program_week: Optional[int] = Field(
        default=None,
        ge=1,
        le=12,
        description="Set when the user chats from a week of the exercise program, so the "
        "reply can help with that week. The server adds the week's text itself.",
    )


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
    engine: Literal["legacy", "router", "rag"] = "rag"
    category: str | None = None
    via: str | None = None
    llm_used: bool | None = None
    conversation_id: int | None = None
