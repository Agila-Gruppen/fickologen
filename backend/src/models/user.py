from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..config.database import Base


if TYPE_CHECKING:
    from .conversation import Conversation
    from .diary_entry import DiaryEntry


class User(Base):
    """
    SQLAlchemy model for the users table.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(255))  # bcrypt hash
    recovery_code: Mapped[Optional[str]] = mapped_column(String(255))  # bcrypt hash of the one-time recovery code
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(32), server_default="user")
    can_chat: Mapped[bool] = mapped_column(server_default="false")
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    birth_year: Mapped[Optional[int]] = mapped_column()
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    gender: Mapped[Optional[str]] = mapped_column(String(32))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="Conversation.updated_at.desc()",
    )
    diary_entries: Mapped[list["DiaryEntry"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="DiaryEntry.created_at.desc()",
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"