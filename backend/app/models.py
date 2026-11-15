from datetime import UTC, datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.domain.consensus import ReportSource


def utc_now() -> datetime:
    """Return current timezone-aware UTC timestamp for server-side DB defaults."""
    return datetime.now(UTC)


class Station(SQLModel, table=True):
    """Fuel station entity located in Gdansk."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    brand: str = Field(index=True)
    address: str
    district: str = Field(index=True)
    latitude: float
    longitude: float
    created_at: datetime = Field(default_factory=utc_now)


class PriceReport(SQLModel, table=True):
    """Immutable historical fuel price submission (never overwritten)."""

    id: int | None = Field(default=None, primary_key=True)
    station_id: int = Field(foreign_key="station.id", index=True)
    fuel_type: str = Field(index=True)
    price: float
    user_id: str = Field(index=True)
    source: str = Field(default=ReportSource.MANUAL.value)
    reported_at: datetime = Field(default_factory=utc_now, index=True)


class PriceVote(SQLModel, table=True):
    """User vote (confirm/reject) on a specific price report; one vote per user per report."""

    __table_args__ = (UniqueConstraint("report_id", "user_id", name="uq_pricevote_report_user"),)

    id: int | None = Field(default=None, primary_key=True)
    report_id: int = Field(foreign_key="pricereport.id", index=True)
    user_id: str = Field(index=True)
    vote_type: str
    created_at: datetime = Field(default_factory=utc_now)


class User(SQLModel, table=True):
    """Registered driver account used to manage private loyalty discounts."""

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    created_at: datetime = Field(default_factory=utc_now)


class Benefit(SQLModel, table=True):
    """Loyalty app discount rule with explicit validity range and verification timestamp."""

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    brand: str = Field(index=True)
    app_name: str
    fuel_type: str | None = Field(default=None, index=True)
    discount_per_liter: float
    max_liters: float | None = None
    active_weekdays: str | None = None  # Comma-separated 0..6 (Mon..Sun) in Europe/Warsaw
    start_hour: int | None = None
    end_hour: int | None = None
    valid_from: datetime
    valid_to: datetime
    checked_at: datetime
    description: str = ""
