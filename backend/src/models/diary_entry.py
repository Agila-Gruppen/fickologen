from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..config.database import Base

if TYPE_CHECKING:
    from .user import User


class DiaryEntry(Base):
    """
    A single diary entry written by a user.

    mood is an optional 1-5 self-rating; the frontend decides what the scale means.
    The CheckConstraint enforces the range at the DB level too, so a bad value
    can never land there even if a client bypasses Pydantic.
    """
    __tablename__ = "diary_entries"
    __table_args__ = (
        Index("ix_diary_entries_user_created", "user_id", "created_at"),
        CheckConstraint(
            "mood IS NULL OR mood BETWEEN 1 AND 5",
            name="ck_diary_entries_mood_range",
        ),
        CheckConstraint(
            "length(trim(content)) > 0",
            name="ck_diary_entries_content_not_blank",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    mood: Mapped[Optional[int]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="diary_entries")

    def __repr__(self):
        return f"<DiaryEntry(id={self.id}, user_id={self.user_id})>"