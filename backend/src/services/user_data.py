"""
Bulk deletion of a user's stored content.

Each function deletes rows but leaves committing to the caller, so several
can run in one transaction. Messages are deleted explicitly rather than left
to ON DELETE CASCADE, so nothing is left behind even on a database where
foreign keys are not enforced (e.g. SQLite without PRAGMA foreign_keys).
"""
from sqlalchemy.orm import Session

from ..models.cbt_progress import CbtProgress
from ..models.conversation import Conversation
from ..models.diary_entry import DiaryEntry
from ..models.message import Message


def delete_conversations(user_id: int, db: Session) -> int:
    """Deletes all the user's conversations and their messages. Returns how many conversations."""
    own_conversations = db.query(Conversation.id).filter(Conversation.user_id == user_id)
    db.query(Message).filter(Message.conversation_id.in_(own_conversations.scalar_subquery())).delete(
        synchronize_session=False
    )
    return db.query(Conversation).filter(Conversation.user_id == user_id).delete(synchronize_session=False)


def delete_diary_entries(user_id: int, db: Session) -> int:
    """Deletes all the user's diary entries. Returns how many."""
    return db.query(DiaryEntry).filter(DiaryEntry.user_id == user_id).delete(synchronize_session=False)


def delete_cbt_progress(user_id: int, db: Session) -> int:
    """Deletes the user's CBT program progress. Returns how many rows (0 or 1)."""
    return db.query(CbtProgress).filter(CbtProgress.user_id == user_id).delete(synchronize_session=False)
