"""get_db must not invent tenants.

It used to create a clients row for any name it was handed, so a typo in a
--client flag or a config key silently produced a new empty tenant instead
of an error. Production accumulated 10 clients against 3 in config.yaml,
including `pure_pool_pro` alongside the real `pure-pool-pro`.

config.yaml is the authority for which tenants exist.
"""

import pytest

from src.db import models
from src.db.models import UnknownClientError, get_db


@pytest.fixture
def known(monkeypatch):
    monkeypatch.setattr(models, "known_client_names", lambda: {"real-client"})


def test_unknown_client_raises(known):
    with pytest.raises(UnknownClientError):
        get_db("not-a-real-client")


def test_the_underscore_typo_that_created_a_tenant_in_production(known):
    monkeyed = "real_client"  # real one is 'real-client'
    with pytest.raises(UnknownClientError):
        get_db(monkeyed)


def test_unknown_client_does_not_leave_a_session_open(known):
    """The guard must close its session, not leak a connection per attempt."""
    engine = models.SessionLocal.kw["bind"]
    before = engine.pool.checkedout()
    for _ in range(5):
        with pytest.raises(UnknownClientError):
            get_db("nope")
    assert engine.pool.checkedout() == before


def test_no_client_name_is_still_allowed(known):
    """The queue uses get_db(None) for the global context."""
    db = get_db(None)
    try:
        assert db.client_id == 0
    finally:
        db.close()


def test_known_client_is_accepted(known, monkeypatch):
    """A name present in config.yaml must still resolve."""
    created = {}

    class _Client:
        id = 42

    class _Query:
        def filter_by(self, **kw):
            created.update(kw)
            return self

        def first(self):
            return _Client()

    class _Session:
        def query(self, *a):
            return _Query()

        def close(self):
            pass

    monkeypatch.setattr(models, "SessionLocal", lambda: _Session())
    db = get_db("real-client")
    assert db.client_id == 42
    assert created["name"] == "real-client"
