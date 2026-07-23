import os
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .orm import Base

# Default database URL for local development
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://community_radar:password123@localhost:5432/community_radar"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def warn_if_superuser():
    """Warn when the runtime connects as a superuser — RLS is bypassed then.

    Migrations and local/test runs legitimately use the superuser owner, so
    this only hard-fails when RADAR_REQUIRE_RLS is set (production), where a
    superuser connection would silently disable tenant isolation.
    """
    import logging
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            is_super = conn.execute(text("SHOW is_superuser")).scalar()
    except Exception:
        return  # DB unreachable at import time — nothing to check yet.

    if str(is_super).lower() in ("on", "true", "t", "yes"):
        msg = (
            "Database role is a SUPERUSER; row-level security is bypassed and "
            "tenant isolation is NOT enforced by the database. Connect as the "
            "non-superuser radar_app role in production."
        )
        if os.getenv("RADAR_REQUIRE_RLS"):
            raise RuntimeError(msg)
        logging.getLogger(__name__).warning("tenant-isolation: %s", msg)


def init_db():
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)


def get_session() -> Generator[Session, None, None]:
    """Dependency for getting a DB session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def tenant_session(client_id: int) -> Generator[Session, None, None]:
    """
    Context manager for a session scoped to a specific tenant.
    This can be expanded to use SQLAlchemy's 'with_loader_criteria'
    or other filtering mechanisms for automatic multi-tenancy.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
