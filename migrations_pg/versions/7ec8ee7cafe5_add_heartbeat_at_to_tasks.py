"""add_heartbeat_at_to_tasks

Revision ID: 7ec8ee7cafe5
Revises: 3eb08a5ffee0
Create Date: 2026-06-22 09:42:02.966970

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7ec8ee7cafe5'
down_revision: Union[str, Sequence[str], None] = '3eb08a5ffee0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tasks', sa.Column('heartbeat_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tasks', 'heartbeat_at')
