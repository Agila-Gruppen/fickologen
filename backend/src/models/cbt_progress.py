from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..config.database import Base


class CbtProgress(Base):
    """
    A user's progress through the 9-week CBT program.
    One row per user (unique user_id).
    completed_weeks is a JSON array of week numbers already finished, e.g. [1, 2, 3].
    """
    __tablename__ = "cbt_progress"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    current_week: Mapped[int] = mapped_column(server_default="1")
    completed_weeks: Mapped[Optional[list[int]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<CbtProgress(id={self.id}, user_id={self.user_id}, current_week={self.current_week})>"