"""Tests for the alembic migration entry point.

The schema is owned by migrations_pg/ (alembic). These tests cover the
wiring — that something actually invokes `upgrade head` — because the
previous `migrate` command printed success while doing nothing at all.
"""

from pathlib import Path

import pytest

from src.db import migrate

ROOT = Path(__file__).parent.parent


def test_run_migrations_upgrades_to_head(monkeypatch):
    calls = {}
    monkeypatch.setattr(
        migrate.command, "upgrade", lambda cfg, rev: calls.update(cfg=cfg, rev=rev)
    )

    migrate.run_migrations()

    assert calls["rev"] == "head"


def test_run_migrations_uses_the_repo_alembic_config(monkeypatch):
    calls = {}
    monkeypatch.setattr(
        migrate.command, "upgrade", lambda cfg, rev: calls.update(cfg=cfg, rev=rev)
    )

    migrate.run_migrations()

    assert Path(calls["cfg"].config_file_name) == ROOT / "alembic.ini"


def test_alembic_config_exists_and_points_at_the_migrations_dir():
    assert (ROOT / "alembic.ini").exists()
    assert (ROOT / "migrations_pg" / "versions").is_dir()


def test_migration_chain_is_linear_with_a_single_head():
    """A branched history would make `upgrade head` ambiguous and fail."""
    versions = list((ROOT / "migrations_pg" / "versions").glob("*.py"))
    assert versions, "no alembic revisions found"

    revisions, down_revisions = set(), set()
    for path in versions:
        for line in path.read_text().splitlines():
            if line.startswith("revision:"):
                revisions.add(line.split("=", 1)[1].strip().strip("'\""))
            elif line.startswith("down_revision:"):
                down_revisions.add(line.split("=", 1)[1].strip().strip("'\""))

    heads = revisions - down_revisions
    assert len(heads) == 1, f"expected exactly one head, found {heads}"


def test_sqlite_migration_runner_is_gone():
    """The old SQLite runner and its .sql files must not come back."""
    assert not hasattr(migrate, "apply_migrations")
    assert not (ROOT / "src" / "db" / "migrations").exists()
