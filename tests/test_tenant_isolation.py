"""Tenant isolation lives in the database (row-level security), not in a
SQL-rewriting guard.

Finding #17: `SELECT client_id, COUNT(*) FROM messages GROUP BY client_id`
mentions client_id in its SELECT list. The old LegacySessionWrapper escape hatch
read that as "already filtered", injected no WHERE clause, and returned every
tenant's rows. A Python guard (TenantIsolationError) was bolted on to *refuse*
such queries. Both are gone now: get_db connects as the non-superuser radar_app
role and sets the per-connection `app.current_client_id` GUC, and the RLS
policies scope the query at the database.

This is the same assertion the guard's tests made — isolation holds — proven
through the real get_db path against the mechanism that now enforces it. The
query that used to leak is run verbatim and must return only the caller's rows.
"""

import uuid

import pytest
from sqlalchemy import create_engine, text

from src.db import models
from src.db.models import get_db
from tests.conftest import TEST_DATABASE_URL


# Owner engine bypasses RLS — used only to seed two tenants' fixture rows.
OWNER = create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")

CLIENT_A, NAME_A = 8101, "isolation-a"
CLIENT_B, NAME_B = 8102, "isolation-b"


@pytest.fixture
def two_seeded_clients(monkeypatch):
    """Two clients, each with one message. get_db accepts them because they are
    declared as known; the owner seeds the rows so both tenants exist."""
    monkeypatch.setattr(models, "known_client_names", lambda: {NAME_A, NAME_B})
    tag = uuid.uuid4().hex[:8]
    with OWNER.begin() as c:
        for cid, name in ((CLIENT_A, NAME_A), (CLIENT_B, NAME_B)):
            c.execute(text("INSERT INTO clients (id, name, created_at, updated_at) "
                           "VALUES (:id, :n, NOW(), NOW()) ON CONFLICT (id) DO NOTHING"),
                      {"id": cid, "n": name})
            c.execute(text("INSERT INTO servers (id, client_id, name, data_source, total_messages, total_users, created_at, updated_at) "
                           "VALUES (:s, :id, 'S', 'reddit', 0, 0, NOW(), NOW())"),
                      {"s": f"s{cid}{tag}", "id": cid})
            c.execute(text("INSERT INTO channels (id, client_id, server_id, name, message_count, status, created_at, updated_at) "
                           "VALUES (:ch, :id, :s, 'ch', 0, 'ok', NOW(), NOW())"),
                      {"ch": f"c{cid}{tag}", "id": cid, "s": f"s{cid}{tag}"})
            c.execute(text("INSERT INTO users (id, client_id, role, messages, reactions_given, reactions_received, created_at, updated_at) "
                           "VALUES (:u, :id, 'x', 0, 0, 0, NOW(), NOW())"),
                      {"u": f"u{cid}{tag}", "id": cid})
            c.execute(text("INSERT INTO messages (client_id, message_id, channel_id, user_id, content, timestamp, reactions, platform, created_at) "
                           "VALUES (:id, :m, :ch, :u, 'hi', NOW(), 0, 'reddit', NOW())"),
                      {"id": cid, "m": f"m{cid}{tag}", "ch": f"c{cid}{tag}", "u": f"u{cid}{tag}"})
    yield tag
    with OWNER.begin() as c:
        for cid in (CLIENT_A, CLIENT_B):
            c.execute(text("DELETE FROM messages WHERE client_id = :id"), {"id": cid})
            c.execute(text("DELETE FROM channels WHERE client_id = :id"), {"id": cid})
            c.execute(text("DELETE FROM users WHERE client_id = :id"), {"id": cid})
            c.execute(text("DELETE FROM servers WHERE client_id = :id"), {"id": cid})
            c.execute(text("DELETE FROM clients WHERE id = :id"), {"id": cid})


# --- the leak the guard existed to stop, now closed by RLS -------------------

def test_selecting_client_id_no_longer_crosses_tenants(two_seeded_clients):
    """The exact finding-#17 query: mentions client_id in the SELECT list and
    has no WHERE clause. It returned every tenant before; RLS now scopes it."""
    tag = two_seeded_clients
    db = get_db(NAME_A)
    try:
        rows = db.execute(
            "SELECT client_id, COUNT(*) AS n FROM messages "
            "WHERE message_id LIKE :t GROUP BY client_id",
            {"t": f"%{tag}"},
        ).all()
    finally:
        db.close()
    seen = {r["client_id"] for r in rows}
    assert seen == {CLIENT_A}, f"cross-tenant leak: query saw {seen}"


def test_bare_scan_is_scoped_to_the_caller(two_seeded_clients):
    """A query with no client_id predicate at all — the wrapper no longer
    injects one, so isolation rests entirely on RLS."""
    tag = two_seeded_clients
    db = get_db(NAME_B)
    try:
        rows = db.execute(
            "SELECT client_id FROM messages WHERE message_id LIKE :t",
            {"t": f"%{tag}"},
        ).all()
    finally:
        db.close()
    assert [r["client_id"] for r in rows] == [CLIENT_B]


def test_cross_tenant_insert_is_rejected(two_seeded_clients):
    """WITH CHECK: scoped to A, a write naming client B's id is refused by RLS."""
    db = get_db(NAME_A)
    try:
        with pytest.raises(Exception) as exc:
            db.execute(
                "INSERT INTO topics (client_id, name, category, mention_count) "
                "VALUES (:cid, 'x', 'y', 1)",
                {"cid": CLIENT_B},
            )
            db.commit()
        assert "row-level security" in str(exc.value).lower()
    finally:
        db.close()
