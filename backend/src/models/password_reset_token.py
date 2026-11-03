from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..config.database import Base

if TYPE_CHECKING:
    from .user import User


class PasswordResetToken(Base):
    """
    One-time password reset tokens, delivered to the user via email.

    The raw token is sent in the email link; only its SHA-256 hash is stored
    here. 1-hour expiry by default. Marked `used_at` the moment the token is
    consumed, so it can never be re-used. Issuing a new token for a user
    invalidates (marks used) any older unused tokens for the same user.
    """
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # sha256 hex = 64 chars
    expires_at: Mapped[datetime] = mapped_column()
    used_at: Mapped[Optional[datetime]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="password_reset_tokens")

    def __repr__(self):
        return f"<PasswordResetToken(id={self.id}, user_id={self.user_id}, used={self.used_at is not None})>"