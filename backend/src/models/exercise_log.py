from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..config.database import Base

if TYPE_CHECKING:
    from .user import User


class ExerciseLog(Base):
    """
    What a user has done on one exercise in the 12-week CBT program.

    The program text itself lives in backend/src/content/program (not in the
    database); exercise_id points at an exercise there, e.g. "w07-expo1", or is
    "reflektion" for the free reflection that closes each week.
    One row per (user, week, exercise), so saving again updates the same row.
    rating_before / rating_after are optional 0-100 self-ratings (anxiety, or how
    much the user believes a thought; the exercise's measure_label says which).
    """
    __tablename__ = "exercise_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "week", "exercise_id", name="uq_exercise_logs_user_week_exercise"),
        CheckConstraint("week BETWEEN 1 AND 12", name="ck_exercise_logs_week_range"),
        CheckConstraint(
            "rating_before IS NULL OR rating_before BETWEEN 0 AND 100",
            name="ck_exercise_logs_rating_before_range",
        ),
        CheckConstraint(
            "rating_after IS NULL OR rating_after BETWEEN 0 AND 100",
            name="ck_exercise_logs_rating_after_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    week: Mapped[int] = mapped_column()
    exercise_id: Mapped[str] = mapped_column(String(64))
    done: Mapped[bool] = mapped_column(server_default="false")
    reflection: Mapped[Optional[str]] = mapped_column(Text)
    rating_before: Mapped[Optional[int]] = mapped_column()
    rating_after: Mapped[Optional[int]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="exercise_logs")

    def __repr__(self):
        return f"<ExerciseLog(id={self.id}, user_id={self.user_id}, week={self.week}, exercise_id='{self.exercise_id}')>"
