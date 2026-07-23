"""Scope message de-duplication to the owning client.

The Postgres database imported from SQLite carried UNIQUE(message_id),
global across every tenant. Two clients tracking the same subreddit could
not both store the same post — the collectors emit ON CONFLICT DO NOTHING,
so the second client silently lost the rows rather than erroring.

Databases built from alembic head never had that constraint at all, which
left them with no constraint matching the collectors' ON CONFLICT target,
so every insert failed with InvalidColumnReference.

Both states converge here on UNIQUE(client_id, message_id).

Revision ID: 096a7e1d662f
Revises: 7ec8ee7cafe5
Create Date: 2026-07-21 11:00:52.792380

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '096a7e1d662f'
down_revision: Union[str, Sequence[str], None] = '7ec8ee7cafe5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF EXISTS: databases created from head never had the global constraint,
    # only the one imported from SQLite does.
    op.execute("ALTER TABLE messages DROP CONSTRAINT IF EXISTS uq_messages_message_id")
    op.execute(
        "ALTER TABLE messages ADD CONSTRAINT uq_messages_client_message "
        "UNIQUE (client_id, message_id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE messages DROP CONSTRAINT IF EXISTS uq_messages_client_message")
    # Not restored: re-adding a global UNIQUE(message_id) would fail on any
    # database where two clients have since stored the same message.
