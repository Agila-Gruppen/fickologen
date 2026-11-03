"""encrypt diary entries, messages and conversation titles

Revision ID: d8f3b6a2e1c7
Revises: c5e2a8f1d904
Create Date: 2026-10-31 12:00:00.000000

Needs DATA_ENCRYPTION_KEY to be set, since existing rows are encrypted
(upgrade) or decrypted (downgrade) in place.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from cryptography.fernet import InvalidToken

from src.utils.crypto import decrypt, encrypt


# revision identifiers, used by Alembic.
revision: str = 'd8f3b6a2e1c7'
down_revision: Union[str, Sequence[str], None] = 'c5e2a8f1d904'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column) pairs that hold text written by the user.
ENCRYPTED_COLUMNS = [
    ("diary_entries", "title"),
    ("diary_entries", "content"),
    ("messages", "content"),
    ("conversations", "title"),
]


def _is_encrypted(value: str) -> bool:
    try:
        decrypt(value)
        return True
    except (InvalidToken, UnicodeEncodeError):
        return False


def _rewrite(table: str, column: str, transform) -> None:
    """Runs transform on every non-null value in table.column and writes it back."""
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(f"SELECT id, {column} FROM {table} WHERE {column} IS NOT NULL")
    ).fetchall()
    for row_id, value in rows:
        new_value = transform(value)
        if new_value != value:
            conn.execute(
                sa.text(f"UPDATE {table} SET {column} = :value WHERE id = :id"),
                {"value": new_value, "id": row_id},
            )


def upgrade() -> None:
    """Upgrade schema."""
    # Encrypted tokens are longer than the plaintext, so VARCHAR(200) is too short.
    with op.batch_alter_table("diary_entries") as batch_op:
        batch_op.alter_column("title", type_=sa.Text(), existing_type=sa.String(200), existing_nullable=True)
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.alter_column("title", type_=sa.Text(), existing_type=sa.String(200), existing_nullable=True)

    # Skip values that are already encrypted, so a re-run does not double-encrypt.
    for table, column in ENCRYPTED_COLUMNS:
        _rewrite(table, column, lambda v: v if _is_encrypted(v) else encrypt(v))


def downgrade() -> None:
    """Downgrade schema."""
    for table, column in ENCRYPTED_COLUMNS:
        _rewrite(table, column, lambda v: decrypt(v) if _is_encrypted(v) else v)

    with op.batch_alter_table("conversations") as batch_op:
        batch_op.alter_column("title", type_=sa.String(200), existing_type=sa.Text(), existing_nullable=True)
    with op.batch_alter_table("diary_entries") as batch_op:
        batch_op.alter_column("title", type_=sa.String(200), existing_type=sa.Text(), existing_nullable=True)
