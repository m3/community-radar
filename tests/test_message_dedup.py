"""Message de-duplication must be scoped per tenant.

The imported Postgres schema carried UNIQUE(message_id) — global across
every client. Two clients tracking the same subreddit could therefore not
both store the same post: whichever collected first won, and the other got
`ON CONFLICT DO NOTHING` and silently lost the rows. (chess-infinity had
673 r/pcgaming messages; poker-club had the channels and zero messages.)

The ORM never declared that constraint at all, so a database built from
alembic head had no matching constraint and *every* collector insert failed
with InvalidColumnReference.

Both are fixed by UNIQUE(client_id, message_id) plus a conflict target that
names it.
"""

import re

from sqlalchemy import UniqueConstraint

from src.db.models import LegacySessionWrapper
from src.db.orm import Message


class _StubSession:
    """Captures the SQL the wrapper compiles without touching a database."""

    def __init__(self):
        self.statements = []

    def execute(self, stmt, params=None):
        self.statements.append(str(stmt))
        return None


def _emit(sql, params=None, client_id=7):
    session = _StubSession()
    LegacySessionWrapper(session, client_id).execute(sql, params)
    return session.statements[-1]


COLLECTOR_INSERT = """
    INSERT OR IGNORE INTO messages (message_id, channel_id, user_id, content, timestamp, reactions, platform)
    VALUES (?, ?, ?, ?, ?, ?, ?)
"""


def test_orm_declares_a_tenant_scoped_unique_constraint_on_messages():
    uniques = [c for c in Message.__table__.constraints if isinstance(c, UniqueConstraint)]
    targets = [tuple(col.name for col in c.columns) for c in uniques]
    assert ("client_id", "message_id") in targets


def test_orm_does_not_declare_a_global_unique_on_message_id():
    uniques = [c for c in Message.__table__.constraints if isinstance(c, UniqueConstraint)]
    targets = [tuple(col.name for col in c.columns) for c in uniques]
    assert ("message_id",) not in targets, "global uniqueness breaks multi-tenant collection"


def test_collector_insert_uses_a_tenant_scoped_conflict_target():
    sql = _emit(COLLECTOR_INSERT, ("m1", "c1", "u1", "hi", "2026-01-01", 0, "reddit"))
    normalized = re.sub(r"\s+", " ", sql)
    assert "ON CONFLICT (client_id, message_id) DO NOTHING" in normalized


def test_collector_insert_still_injects_client_id_into_the_column_list():
    sql = _emit(COLLECTOR_INSERT, ("m1", "c1", "u1", "hi", "2026-01-01", 0, "reddit"))
    normalized = re.sub(r"\s+", " ", sql)
    assert "INSERT INTO messages (client_id, message_id," in normalized


def test_tasks_table_conflict_target_stays_global():
    """tasks has no client_id, so its conflict target must not gain one."""
    sql = _emit("INSERT OR IGNORE INTO tasks (id, command) VALUES (?, ?)", (1, "status"))
    normalized = re.sub(r"\s+", " ", sql)
    assert "ON CONFLICT (id) DO NOTHING" in normalized
    assert "client_id" not in normalized
