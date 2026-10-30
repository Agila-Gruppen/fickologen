"""
CSV export of everything stored about a user.

The files are made for Swedish Excel, which is what most users will open
them in: semicolon-separated, UTF-8 with a byte order mark (so å, ä and ö
show correctly) and times in Swedish time. The password and recovery code
hashes are never exported.
"""
import csv
import io
from datetime import datetime, timezone
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from ..models.conversation import Conversation
from ..models.diary_entry import DiaryEntry
from ..models.message import Message
from ..models.user import User

STOCKHOLM = ZoneInfo("Europe/Stockholm")

# A cell starting with one of these is run as a formula by Excel. Prefixing
# with an apostrophe makes it plain text. "-" only counts when not followed
# by a space, so ordinary "- " lists in diary entries are left alone.
FORMULA_PREFIXES = ("=", "+", "@", "\t", "\r")

SENDERS = {"user": "Du", "assistant": "Fickologen"}


def _time(value: Optional[datetime]) -> str:
    """Stored times are naive UTC; show them in Swedish time."""
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(STOCKHOLM).strftime("%Y-%m-%d %H:%M")


def _cell(value) -> str:
    if value is None:
        return ""
    text = str(value)
    if text.startswith(FORMULA_PREFIXES) or (text.startswith("-") and not text.startswith("- ")):
        return "'" + text
    return text


def _to_csv(header: list[str], rows: Iterable[list]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([_cell(value) for value in row])
    return buffer.getvalue().encode("utf-8-sig")


def account_csv(user: User) -> bytes:
    """The account's own fields, one per row."""
    rows = [
        ["Konto-ID", user.id],
        ["Användarnamn", user.username],
        ["E-post", user.email],
        ["Förnamn", user.first_name],
        ["Efternamn", user.last_name],
        ["Födelseår", user.birth_year],
        ["Telefon", user.phone],
        ["Kön", user.gender],
        ["Ort", user.city],
        ["Roll", user.role],
        ["Chatt-tillgång", "Ja" if user.can_chat else "Nej"],
        ["Veckopåminnelser via e-post", "Ja" if user.reminders_enabled else "Nej"],
        ["Senaste påminnelse skickad", _time(user.last_reminder_sent_at)],
        ["Konto skapat", _time(user.created_at)],
        ["Senast ändrat", _time(user.updated_at)],
        ["Lösenord", "Sparas bara krypterat och kan inte exporteras"],
    ]
    return _to_csv(["Uppgift", "Värde"], rows)


def chats_csv(user_id: int, db: Session) -> bytes:
    """Every message in every conversation, one per row, oldest conversation first."""
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.created_at, Conversation.id)
        .all()
    )
    rows = []
    for conv in conversations:
        messages = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id)
            .order_by(Message.created_at, Message.id)
            .all()
        )
        if not messages:
            rows.append([conv.id, conv.title, _time(conv.created_at), "", "", ""])
        for message in messages:
            rows.append([
                conv.id,
                conv.title,
                _time(conv.created_at),
                _time(message.created_at),
                SENDERS.get(message.role, message.role),
                message.content,
            ])
    return _to_csv(["Chatt-ID", "Chattens titel", "Chatten startad", "Tidpunkt", "Avsändare", "Meddelande"], rows)


def diary_csv(user_id: int, db: Session) -> bytes:
    """Every diary entry, one per row, oldest first."""
    entries = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.user_id == user_id)
        .order_by(DiaryEntry.created_at, DiaryEntry.id)
        .all()
    )
    rows = [
        [entry.id, _time(entry.created_at), _time(entry.updated_at), entry.title, entry.mood, entry.content]
        for entry in entries
    ]
    return _to_csv(["Anteckning-ID", "Skriven", "Senast ändrad", "Rubrik", "Humör (1–5)", "Text"], rows)
