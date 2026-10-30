"""add exercise_logs for the 12-week CBT program

Revision ID: a3c91d7e5b24
Revises: 051e3506d93a
Create Date: 2026-10-27 10:12:44.118305

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c91d7e5b24'
down_revision: Union[str, Sequence[str], None] = '051e3506d93a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('exercise_logs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('week', sa.Integer(), nullable=False),
    sa.Column('exercise_id', sa.String(length=64), nullable=False),
    sa.Column('done', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('reflection', sa.Text(), nullable=True),
    sa.Column('rating_before', sa.Integer(), nullable=True),
    sa.Column('rating_after', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('rating_after IS NULL OR rating_after BETWEEN 0 AND 100', name='ck_exercise_logs_rating_after_range'),
    sa.CheckConstraint('rating_before IS NULL OR rating_before BETWEEN 0 AND 100', name='ck_exercise_logs_rating_before_range'),
    sa.CheckConstraint('week BETWEEN 1 AND 12', name='ck_exercise_logs_week_range'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'week', 'exercise_id', name='uq_exercise_logs_user_week_exercise')
    )
    op.create_index(op.f('ix_exercise_logs_id'), 'exercise_logs', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_exercise_logs_id'), table_name='exercise_logs')
    op.drop_table('exercise_logs')
