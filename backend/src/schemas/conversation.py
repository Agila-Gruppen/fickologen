from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MessageData(BaseModel):
    """A single stored message in a conversation."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    category: Optional[str] = None
    via: Optional[str] = None
    llm_used: Optional[bool] = None
    created_at: datetime


class ConversationData(BaseModel):
    """A conversation's metadata, without its messages."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: Optional[str]
    created_at: datetime
    updated_at: datetime


class ConversationWithMessages(ConversationData):
    """A conversation plus all its messages, in chronological order."""
    messages: list[MessageData] = []


class ConversationRename(BaseModel):
    """New title for a conversation. Whitespace is collapsed, and it must not end up empty."""
    title: str = Field(..., max_length=200)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Title must not be blank")
        return cleaned
