"""The startup check warns (or refuses) when the runtime role bypasses RLS.

The test database connects as the superuser owner, so warn_if_superuser sees a
superuser: it must warn by default and hard-fail only when RADAR_REQUIRE_RLS is
set (production), where a superuser connection would silently disable isolation.
"""

import logging

import pytest

from src.db.session import warn_if_superuser


def test_warns_by_default(monkeypatch, caplog):
    monkeypatch.delenv("RADAR_REQUIRE_RLS", raising=False)
    with caplog.at_level(logging.WARNING):
        warn_if_superuser()  # must not raise
    assert any("row-level security is bypassed" in r.message for r in caplog.records)


def test_hard_fails_when_rls_required(monkeypatch):
    monkeypatch.setenv("RADAR_REQUIRE_RLS", "1")
    with pytest.raises(RuntimeError, match="row-level security"):
        warn_if_superuser()
