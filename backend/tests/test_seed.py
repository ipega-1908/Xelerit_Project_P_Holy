from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.database import create_db_and_tables, create_sqlite_engine
from app.domain.consensus import SUPPORTED_FUEL_TYPES, VoteType
from app.models import Benefit, PriceReport, PriceVote, Station
from app.seed import seed_database


def _make_memory_session() -> Session:
    engine = create_sqlite_engine("sqlite://")
    create_db_and_tables(engine)
    return Session(engine)


def test_seed_database_populates_gdansk_data_and_is_idempotent() -> None:
    now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    with _make_memory_session() as session:
        first_run = seed_database(session, now=now)
        assert first_run is True

        stations = session.exec(select(Station)).all()
        reports = session.exec(select(PriceReport)).all()
        votes = session.exec(select(PriceVote)).all()
        benefits = session.exec(select(Benefit)).all()

        assert 12 <= len(stations) <= 15
        assert len(reports) == len(stations) * len(SUPPORTED_FUEL_TYPES)
        assert len(votes) > 0
        assert len(benefits) >= 5

        # Second run must not duplicate existing seed data.
        second_run = seed_database(session, now=now)
        assert second_run is False
        assert len(session.exec(select(Station)).all()) == len(stations)


def test_price_vote_unique_constraint_per_user_and_report() -> None:
    now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    with _make_memory_session() as session:
        seed_database(session, now=now)
        report = session.exec(select(PriceReport)).first()
        assert report is not None and report.id is not None

        session.add(
            PriceVote(
                report_id=report.id,
                user_id="driver-123",
                vote_type=VoteType.CONFIRM.value,
                created_at=now,
            )
        )
        session.commit()

        session.add(
            PriceVote(
                report_id=report.id,
                user_id="driver-123",
                vote_type=VoteType.REJECT.value,
                created_at=now,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
