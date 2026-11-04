"""
Password reset via email: issue one-time tokens, mail them to the user,
and consume them to set a new password.

The raw token is sent in the email link; only its SHA-256 hash is stored
in the database. Tokens expire after 1 hour. Older unused tokens for the
same user are invalidated when a new one is issued.
"""
import hashlib
import html
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.password_reset_token import PasswordResetToken
from ..models.user import User
from . import email

TOKEN_TTL_HOURS = 1


def app_url() -> str:
    return os.environ.get("APP_URL", "http://localhost:8501").rstrip("/")


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def find_user(db: Session, email_or_username: str) -> Optional[User]:
    """Finds a user whose username OR email matches, case-insensitively on email."""
    identifier = email_or_username.strip()
    if not identifier:
        return None
    return (
        db.query(User)
        .filter(or_(User.username == identifier, User.email.ilike(identifier)))
        .first()
    )


def issue_token(user: User, db: Session) -> str:
    """
    Creates a fresh reset token for the user, invalidating any older unused
    tokens. Returns the raw token (to be mailed) — the hash goes to the DB.
    """
    now = _utc_now()
    # Invalidate any older unused tokens so a user can't have two live links.
    (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .update({"used_at": now}, synchronize_session=False)
    )

    raw = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(raw),
        expires_at=now + timedelta(hours=TOKEN_TTL_HOURS),
    ))
    db.commit()
    return raw


def redeem_token(raw_token: str, db: Session) -> Optional[User]:
    """
    Finds the unused, unexpired token matching `raw_token`, marks it used,
    and returns the user it belongs to. Returns None if no such token.
    The caller is responsible for setting the new password.
    """
    now = _utc_now()
    row = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == _hash_token(raw_token),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .first()
    )
    if row is None:
        return None
    row.used_at = now
    db.commit()
    return row.user


def send_reset_email(user: User, raw_token: str) -> None:
    """
    Sends the reset mail with the token link. Raises email.EmailNotConfigured
    if SMTP is not configured.
    """
    if not user.email:
        return
    link = f"{app_url()}/?reset={raw_token}"
    greeting = f"Hej {user.first_name}!" if user.first_name else "Hej!"
    text = (
        f"{greeting}\n\n"
        "Vi fick en förfrågan om att återställa lösenordet till ditt Fickologen-konto.\n\n"
        f"Klicka på länken nedan för att välja ett nytt lösenord. Länken gäller i {TOKEN_TTL_HOURS} timme.\n\n"
        f"{link}\n\n"
        "Om du inte bad om detta kan du ignorera mejlet — ditt lösenord ändras inte.\n\n"
        "--\n"
        "Fickologen\n"
    )
    body_html = f"""\
<div style="font-family: Arial, Helvetica, sans-serif; color: #33312D; background: #FAF7F1; padding: 24px;">
  <div style="max-width: 520px; margin: 0 auto; background: #FFFFFF; border: 1px solid #EAE3D7; border-radius: 16px; padding: 28px;">
    <p style="margin: 0 0 12px 0; font-size: 16px;">{html.escape(greeting)}</p>
    <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6;">
      Vi fick en förfrågan om att återställa lösenordet till ditt Fickologen-konto.
    </p>
    <p style="margin: 0 0 20px 0; font-size: 15px; line-height: 1.6;">
      Klicka på knappen nedan för att välja ett nytt lösenord. Länken gäller i {TOKEN_TTL_HOURS} timme.
    </p>
    <a href="{html.escape(link)}" style="display: inline-block; background: #C96649; color: #FFFFFF; text-decoration: none; padding: 12px 22px; border-radius: 12px; font-weight: bold;">Välj nytt lösenord</a>
    <p style="margin: 24px 0 0 0; font-size: 12px; color: #7A7468; line-height: 1.5;">
      Om du inte bad om detta kan du ignorera mejlet — ditt lösenord ändras inte.
    </p>
  </div>
</div>
"""
    email.send_email(
        user.email,
        "Återställ ditt lösenord på Fickologen",
        text,
        body_html,
    )