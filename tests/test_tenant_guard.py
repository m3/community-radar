"""A tenant-scoped query that ends up with no client_id predicate must not run.

LegacySessionWrapper rewrites SQL to inject client_id, but its escape hatch
(models.py: "client_id" in sql.lower()) assumes any mention of the column
means the query is already filtered. So
`SELECT client_id, COUNT(*) FROM messages GROUP BY client_id` got a bind
param but no WHERE clause and returned every tenant's rows. This guard
inspects the final rewritten SQL and refuses to execute a tenant-scoped
read/write that carries no client_id predicate.
"""

import pytest

from src.db import models
from src.db.models import LegacySessionWrapper, TenantIsolationError


class _StubSession:
    def __init__(self):
        self.executed = []

    def execute(self, stmt, params=None):
        self.executed.append(str(stmt))

        class _R:
            def mappings(self_inner):
                return []

        return _R()


def _wrap(client_id=7):
    return LegacySessionWrapper(_StubSession(), client_id)


# --- the leak the guard exists to stop ---------------------------------------

def test_client_id_in_select_list_without_predicate_is_blocked(monkeypatch):
    monkeypatch.setattr(models, "tenant_guard_mode", lambda: "enforce")
    db = _wrap()
    with pytest.raises(TenantIsolationError):
        db.execute("SELECT client_id, COUNT(*) FROM messages GROUP BY client_id")


def test_group_by_client_id_alone_is_blocked(monkeypatch):
    monkeypatch.setattr(models, "tenant_guard_mode", lambda: "enforce")
    db = _wrap()
    with pytest.raises(TenantIsolationError):
        db.execute("SELECT platform, client_id FROM messages GROUP BY platform, client_id")


# --- legitimate queries must still pass --------------------------------------

def test_explicitly_filtered_query_passes(monkeypatch):
    monkeypatch.setattr(models, "tenant_guard_mode", lambda: "enforce")
    db = _wrap()
    db.execute("SELECT content FROM messages m WHERE m.client_id = :client_id AND m.reactions > 0")


def test_bare_query_gets_a_predicate_injected_and_passes(monkeypatch):
    monkeypatch.setattr(models, "tenant_guard_mode", lambda: "enforce")
    db = _wrap()
    # No client_id in the source at all -> rewriter injects "client_id = 7".
    db.execute("SELECT COUNT(*) as c FROM users")


def test_client_id_in_predicate_passes(monkeypatch):
    monkeypatch.setattr(models, "tenant_guard_mode", lambda: "enforce")
    db = _wrap()
    db.execute("SELECT id FROM messages WHERE client_id = :client_id")


# --- exemptions ---------------------------------------------------------------

def test_tasks_table_is_exempt(monkeypatch):
    monkeypatch.setattr(models, "tenant_guard_mode", lambda: "enforce")
    db = _wrap()
    db.execute("SELECT * FROM tasks ORDER BY id DESC")


def test_insert_is_not_guarded(monkeypatch):
    monkeypatch.setattr(models, "tenant_guard_mode", lambda: "enforce")
    db = _wrap()
    db.execute("INSERT OR IGNORE INTO users (id, role) VALUES (?, ?)", ("u1", "x"))


# --- modes --------------------------------------------------------------------

def test_log_mode_does_not_raise(monkeypatch):
    monkeypatch.setattr(models, "tenant_guard_mode", lambda: "log")
    db = _wrap()
    db.execute("SELECT client_id FROM messages GROUP BY client_id")  # no raise


def test_off_mode_does_not_raise(monkeypatch):
    monkeypatch.setattr(models, "tenant_guard_mode", lambda: "off")
    db = _wrap()
    db.execute("SELECT client_id FROM messages GROUP BY client_id")  # no raise
