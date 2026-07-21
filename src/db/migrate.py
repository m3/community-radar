"""Database migrations.

The schema is owned by alembic (`migrations_pg/`). `migrations_pg/env.py`
resolves the connection from DATABASE_URL, so nothing here needs to know
about credentials.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).parent.parent.parent
ALEMBIC_INI = ROOT / "alembic.ini"


def get_alembic_config() -> Config:
    return Config(str(ALEMBIC_INI))


def run_migrations() -> None:
    """Upgrade the database to the latest revision."""
    command.upgrade(get_alembic_config(), "head")


def stamp_head() -> None:
    """Mark the database as being at the latest revision without running it.

    For a database whose schema was created outside alembic — the original
    Postgres import was built by scripts/migrate_sqlite_to_pg.py, which left
    `alembic_version` empty.
    """
    command.stamp(get_alembic_config(), "head")
