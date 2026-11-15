from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, event, text
from sqlmodel import Session, SQLModel, create_engine

DEFAULT_DATABASE_URL = "sqlite:///./fuel_deals.db"


def create_sqlite_engine(database_url: str = DEFAULT_DATABASE_URL, **kwargs: Any) -> Engine:
    """Create a SQLite engine with foreign key enforcement enabled."""
    connect_args = kwargs.pop("connect_args", {})
    if database_url.startswith("sqlite"):
        connect_args.setdefault("check_same_thread", False)

    engine = create_engine(database_url, connect_args=connect_args, **kwargs)

    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = create_sqlite_engine()


def create_db_and_tables(target_engine: Engine = engine) -> None:
    """Create all SQLModel tables and ensure additive SQLite columns exist."""
    SQLModel.metadata.create_all(target_engine)
    if target_engine.dialect.name == "sqlite":
        with target_engine.begin() as conn:
            report_columns = {
                row[1] for row in conn.execute(text("PRAGMA table_info(pricereport)"))
            }
            if "source" not in report_columns:
                conn.execute(
                    text(
                        "ALTER TABLE pricereport "
                        "ADD COLUMN source VARCHAR NOT NULL DEFAULT 'manual'"
                    )
                )
            benefit_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(benefit)"))}
            if "owner_id" not in benefit_columns:
                conn.execute(
                    text("ALTER TABLE benefit ADD COLUMN owner_id INTEGER REFERENCES user(id)")
                )


def get_session() -> Generator[Session, None, None]:
    """Yield a SQLModel session for FastAPI dependency injection."""
    with Session(engine) as session:
        yield session
