"""Test isolation.

The default DATABASE_URL in src/db/session.py points at the live
`community_radar` database. Run unguarded, the suite mutated production:
test_queue's fixture truncated the real task queue on every run, and the
API tests created tenant rows there. This redirects the whole suite onto a
dedicated, disposable `community_radar_test` database before any src module
imports the engine.

Set COMMUNITY_RADAR_TEST_DATABASE_URL to override the target.
"""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

# Must run before any `from src.db...` import so the engine binds to the test
# database. conftest.py is imported by pytest ahead of the test modules.
_LIVE_DEFAULT = "postgresql://community_radar:password123@localhost:5432/community_radar"
_SOURCE = os.environ.get("DATABASE_URL", _LIVE_DEFAULT)

_url = make_url(_SOURCE)
if _url.database == "community_radar":
    _url = _url.set(database="community_radar_test")

# render_as_string(hide_password=False): str(URL) masks the password as
# '***' in SQLAlchemy 2.0, which would then be used as the literal password.
TEST_DATABASE_URL = os.environ.get(
    "COMMUNITY_RADAR_TEST_DATABASE_URL", _url.render_as_string(hide_password=False)
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest


def _database_exists(url_str):
    """Whether we can connect to the target database at all."""
    engine = create_engine(url_str)
    try:
        with engine.connect():
            return True
    except OperationalError as exc:
        if "does not exist" in str(exc):
            return False
        raise  # a real problem (auth, host) — surface it, don't mask it
    finally:
        engine.dispose()


def _create_database(url_str):
    """CREATE DATABASE via the postgres maintenance database."""
    url = make_url(url_str)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    """Provision and migrate the disposable test database once per run.

    The common path connects straight to the test database and migrates it —
    the postgres maintenance database is only touched on first-ever setup.
    """
    assert make_url(TEST_DATABASE_URL).database != "community_radar", (
        "refusing to run the suite against the live database"
    )
    if not _database_exists(TEST_DATABASE_URL):
        _create_database(TEST_DATABASE_URL)

    from src.db.migrate import run_migrations

    run_migrations()

    # The RLS migration creates radar_app passwordless; give it a known test
    # password so the RLS integration test can connect as the non-superuser
    # runtime role.
    engine = create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(text(f"ALTER ROLE radar_app PASSWORD '{RADAR_APP_TEST_PASSWORD}'"))
    finally:
        engine.dispose()

    yield


RADAR_APP_TEST_PASSWORD = "radar_app_test"


def radar_app_url():
    """Test-database URL for the non-superuser runtime role."""
    return make_url(TEST_DATABASE_URL).set(
        username="radar_app", password=RADAR_APP_TEST_PASSWORD
    ).render_as_string(hide_password=False)
