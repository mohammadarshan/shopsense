"""Database connection setup: the SQLAlchemy engine, session factory and model base class."""
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# The engine manages a pool of connections that is reused across requests.
engine = create_engine(
    # URL.create escapes special characters in the password, which a
    # hand-built "postgresql://user:pass@..." string would not.
    URL.create(
        "postgresql+psycopg2",
        username=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.postgres_host,
        port=settings.postgres_host_port,
        database=settings.postgres_db,
    ),
    # Test each pooled connection before use, so a DB restart doesn't cause
    # "connection closed" errors on the next request.
    pool_pre_ping=True,
)

# autoflush=False: changes are only sent to the DB when we commit or flush,
# which makes it easier to reason about when SQL actually runs.
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    """Parent class for all ORM models; it collects their table definitions."""

    pass


def get_db():
    """FastAPI dependency that gives each request its own DB session.

    Using yield means the code after it runs once the response is sent, so the
    session is always closed (returned to the pool), even if the route raised.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()