from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


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