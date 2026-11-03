from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..config.database import Base
from ..utils.crypto import EncryptedText

if TYPE_CHECKING:
    from .conversation import Conversation


class Message(Base):
    """
    A single message in a conversation.
    role is "user" or "assistant".
    category/via/llm_used mirror what the chat router returns.
    content is encrypted at rest (see utils/crypto.py).
    """
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(EncryptedText)
    category: Mapped[Optional[str]] = mapped_column(String(64))
    via: Mapped[Optional[str]] = mapped_column(String(32))
    llm_used: Mapped[Optional[bool]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    
    def __repr__(self):
        return f"<Message(id={self.id}, conversation_id={self.conversation_id}, role='{self.role}')>"