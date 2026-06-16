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
        # In a more advanced implementation, we could set a global
        # variable or use a filter here to ensure all queries
        # automatically include 'client_id=client_id'
        yield session
    finally:
        session.close()
