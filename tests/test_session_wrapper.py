"""Tests for LegacySessionWrapper's transaction handling.

The queue worker calls db.rollback() in three except blocks. The wrapper
did not implement rollback, so a failing task raised AttributeError inside
the handler meant to record the failure: the task stayed 'running' forever
and the worker loop died.
"""

import pytest
from sqlalchemy.exc import DBAPIError

from src.db.orm import Task
from src.db.queue import get_queue_db
from src.db.session import SessionLocal


@pytest.fixture
def clean_tasks():
    session = SessionLocal()
    session.query(Task).delete()
    session.commit()
    session.close()
    yield
    session = SessionLocal()
    session.query(Task).delete()
    session.commit()
    session.close()


def test_wrapper_exposes_rollback():
    db = get_queue_db()
    try:
        assert hasattr(db, "rollback"), "worker error paths call db.rollback()"
    finally:
        db.close()


def test_rollback_recovers_the_session_after_a_failed_statement(clean_tasks):
    """The worker's except-block path: a statement blows up, then rollback."""
    db = get_queue_db()
    try:
        with pytest.raises(DBAPIError):
            db.execute("UPDATE tasks SET status='running' WHERE no_such_column = 1")

        db.rollback()

        # Session is usable again — without the rollback Postgres refuses
        # every subsequent statement in the aborted transaction.
        db.execute(
            "INSERT INTO tasks (command, status, created_at) VALUES (?, ?, NOW())",
            ("status", "pending"),
        )
        db.commit()
    finally:
        db.close()

    session = SessionLocal()
    assert session.query(Task).count() == 1
    session.close()


def test_rollback_discards_uncommitted_writes(clean_tasks):
    db = get_queue_db()
    try:
        db.execute(
            "INSERT INTO tasks (command, status, created_at) VALUES (?, ?, NOW())",
            ("status", "pending"),
        )
        db.rollback()
    finally:
        db.close()

    session = SessionLocal()
    assert session.query(Task).count() == 0
    session.close()
