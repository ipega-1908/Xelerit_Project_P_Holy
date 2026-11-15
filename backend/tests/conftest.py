from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session

from app.database import create_db_and_tables, create_sqlite_engine, get_session
from app.dependencies import get_now
from app.main import create_app
from app.seed import seed_database

FIXED_NOW = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    """Create an isolated in-memory SQLite session seeded with deterministic timestamps."""
    engine = create_sqlite_engine(
        "sqlite://",
        poolclass=StaticPool,
    )
    create_db_and_tables(engine)
    with Session(engine) as session:
        seed_database(session, now=FIXED_NOW)
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient wired to the in-memory session and fixed clock."""
    app = create_app(enable_lifespan=False)

    def _override_session() -> Generator[Session, None, None]:
        yield session

    def _override_now() -> datetime:
        return FIXED_NOW

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_now] = _override_now

    with TestClient(app) as client:
        yield client
