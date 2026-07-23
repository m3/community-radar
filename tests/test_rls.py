"""Row-level security enforces tenant isolation at the database.

This file and test_tenant_isolation.py are the two tests that carry the
isolation guarantee — the only ones that seed *two* tenants and assert a query
sees just one. The rest of the suite runs single-tenant, so it proves queries
still return correct data but would not catch a cross-tenant leak. Do not weaken
these two without replacing the guarantee elsewhere.

These connect as the non-superuser radar_app role (the runtime role) and
verify the policies actually isolate clients — the superuser owner used by the
rest of the suite bypasses RLS, so isolation must be proven here. Also pins the
connection pattern get_db uses: the GUC is per-connection, so it must survive a
commit (a Session that returned its connection to the pool would then see zero
rows).
"""

import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from tests.conftest import TEST_DATABASE_URL, radar_app_url


OWNER = create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
APP = create_engine(radar_app_url())


@pytest.fixture
def two_clients():
    """Seed two clients each with one message; return their ids. Owner bypasses RLS."""
    a, b = 8001, 8002
    tag = uuid.uuid4().hex[:8]
    with OWNER.begin() as c:
        for cid in (a, b):
            c.execute(text("INSERT INTO clients (id, name, created_at, updated_at) VALUES (:id, :n, NOW(), NOW()) ON CONFLICT (id) DO NOTHING"),
                      {"id": cid, "n": f"rls-{cid}"})
            c.execute(text("INSERT INTO servers (id, client_id, name, data_source, total_messages, total_users, created_at, updated_at) "
                           "VALUES (:s, :id, 'S', 'x', 0, 0, NOW(), NOW())"), {"s": f"s{cid}{tag}", "id": cid})
            c.execute(text("INSERT INTO channels (id, client_id, server_id, name, message_count, status, created_at, updated_at) "
                           "VALUES (:ch, :id, :s, 'ch', 0, 'ok', NOW(), NOW())"), {"ch": f"c{cid}{tag}", "id": cid, "s": f"s{cid}{tag}"})
            c.execute(text("INSERT INTO users (id, client_id, role, messages, reactions_given, reactions_received, created_at, updated_at) "
                           "VALUES (:u, :id, 'x', 0, 0, 0, NOW(), NOW())"), {"u": f"u{cid}{tag}", "id": cid})
            c.execute(text("INSERT INTO messages (client_id, message_id, channel_id, user_id, content, timestamp, reactions, platform, created_at) "
                           "VALUES (:id, :m, :ch, :u, 'hi', NOW(), 0, 'reddit', NOW())"),
                      {"id": cid, "m": f"m{cid}{tag}", "ch": f"c{cid}{tag}", "u": f"u{cid}{tag}"})
    yield a, b, tag
    with OWNER.begin() as c:
        for cid in (a, b):
            c.execute(text("DELETE FROM messages WHERE client_id = :id"), {"id": cid})
            c.execute(text("DELETE FROM channels WHERE client_id = :id"), {"id": cid})
            c.execute(text("DELETE FROM users WHERE client_id = :id"), {"id": cid})
            c.execute(text("DELETE FROM servers WHERE client_id = :id"), {"id": cid})
            c.execute(text("DELETE FROM clients WHERE id = :id"), {"id": cid})


def _scoped_session(client_id):
    """Mirror get_db's exact pattern: Session bound to one connection, GUC set
    through the session (not the raw connection)."""
    conn = APP.connect()
    session = Session(bind=conn)
    session.execute(text("SELECT set_config('app.current_client_id', :cid, false)"), {"cid": str(client_id)})
    return conn, session


def test_client_sees_only_its_own_rows(two_clients):
    a, b, tag = two_clients
    conn, s = _scoped_session(a)
    try:
        rows = s.execute(text("SELECT client_id FROM messages WHERE message_id LIKE :t"), {"t": f"%{tag}"}).scalars().all()
        assert rows == [a]
    finally:
        s.close(); conn.close()


def test_switching_client_switches_visibility(two_clients):
    a, b, tag = two_clients
    conn, s = _scoped_session(b)
    try:
        rows = s.execute(text("SELECT client_id FROM messages WHERE message_id LIKE :t"), {"t": f"%{tag}"}).scalars().all()
        assert rows == [b]
    finally:
        s.close(); conn.close()


def test_guc_survives_a_commit(two_clients):
    """The advisor's pitfall: after commit the connection must still be scoped."""
    a, b, tag = two_clients
    conn, s = _scoped_session(a)
    try:
        first = s.execute(text("SELECT count(*) FROM messages WHERE message_id LIKE :t"), {"t": f"%{tag}"}).scalar()
        assert first == 1
        s.commit()
        second = s.execute(text("SELECT count(*) FROM messages WHERE message_id LIKE :t"), {"t": f"%{tag}"}).scalar()
        assert second == 1, "GUC lost after commit — RLS would return zero rows"
    finally:
        s.close(); conn.close()


def test_unset_or_empty_guc_sees_nothing(two_clients):
    """Fail-closed: an unset/empty scope selects no tenant rows (NULLIF handles '')."""
    a, b, tag = two_clients
    conn = APP.connect()
    try:
        # Empty string is what a cleared/never-set GUC yields on a pooled conn.
        conn.execute(text("SELECT set_config('app.current_client_id', '', false)"))
        n = conn.execute(text("SELECT count(*) FROM messages WHERE message_id LIKE :t"), {"t": f"%{tag}"}).scalar()
        assert n == 0
    finally:
        conn.close()


def test_with_check_blocks_cross_tenant_insert(two_clients):
    a, b, tag = two_clients
    conn, s = _scoped_session(a)
    try:
        with pytest.raises(Exception) as exc:
            s.execute(text("INSERT INTO topics (client_id, name, category, mention_count) VALUES (:id, 'x', 'y', 1)"), {"id": b})
            s.commit()
        assert "row-level security" in str(exc.value).lower()
    finally:
        s.close(); conn.close()
