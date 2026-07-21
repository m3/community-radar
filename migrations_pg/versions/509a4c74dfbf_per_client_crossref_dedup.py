"""Scope cross-reference uniqueness to the owning client.

The imported schema carried
UNIQUE (user_id, platform1, username1, platform2, username2) with no
client_id, so one client's match tuple blocked every other client's
identical tuple. identity.py inserts without ON CONFLICT and has no per-row
error handling, so a single collision aborted the whole sync and cost that
client all of its matches. Only one client has cross-references today, which
is why it has not fired yet.

Databases built from alembic head never had the constraint at all, so the
drop is conditional.

Revision ID: 509a4c74dfbf
Revises: 096a7e1d662f
Create Date: 2026-07-21 11:13:50.601218

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '509a4c74dfbf'
down_revision: Union[str, Sequence[str], None] = '096a7e1d662f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE cross_references DROP CONSTRAINT IF EXISTS uq_cross_refs")
    op.execute(
        "ALTER TABLE cross_references ADD CONSTRAINT uq_cross_refs_client "
        "UNIQUE (client_id, user_id, platform1, username1, platform2, username2)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE cross_references DROP CONSTRAINT IF EXISTS uq_cross_refs_client"
    )
    # Not restored: a global unique would fail on any database where two
    # clients have since recorded the same match tuple.
