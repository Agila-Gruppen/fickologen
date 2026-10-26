"""merge recovery_code and composite index branches

Revision ID: 62f4eb7b9ea4
Revises: 0d47e78dbaf5, b7d41e2c9f03
Create Date: 2026-10-15 12:39:07.218388

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '62f4eb7b9ea4'
down_revision: Union[str, Sequence[str], None] = ('0d47e78dbaf5', 'b7d41e2c9f03')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
