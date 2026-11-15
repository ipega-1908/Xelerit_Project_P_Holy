from datetime import datetime

from fastapi import HTTPException, status
from sqlmodel import Session, delete, select

from app.domain.benefits import ensure_utc
from app.domain.consensus import SUPPORTED_FUEL_TYPES
from app.models import Benefit, PriceReport, PriceVote, Station
from app.schemas import FuelTypeLiteral, StationCreate, StationRead, StationUpdate
from app.services.pricing import (
    get_active_benefits_for_brand,
    resolution_to_summary,
    resolve_all_station_prices,
)


def _build_station_reads(
    stations: list[Station],
    session: Session,
    now: datetime,
) -> list[StationRead]:
    if not stations:
        return []

    all_stations = list(session.exec(select(Station)).all())
    all_reports = list(session.exec(select(PriceReport)).all())
    all_votes = list(session.exec(select(PriceVote)).all())
    all_benefits = list(session.exec(select(Benefit)).all())

    resolutions = resolve_all_station_prices(all_stations, all_reports, all_votes, now)

    results: list[StationRead] = []
    for station in stations:
        assert station.id is not None
        station_res = resolutions[station.id]
        prices: dict[FuelTypeLiteral, object] = {
            fuel: resolution_to_summary(fuel, station_res[fuel]) for fuel in SUPPORTED_FUEL_TYPES
        }
        results.append(
            StationRead(
                id=station.id,
                name=station.name,
                brand=station.brand,
                address=station.address,
                district=station.district,
                latitude=station.latitude,
                longitude=station.longitude,
                created_at=ensure_utc(station.created_at),
                prices=prices,  # type: ignore[arg-type]
                active_benefits=get_active_benefits_for_brand(all_benefits, station.brand, now),
            )
        )
    return results


def list_stations(session: Session, now: datetime) -> list[StationRead]:
    """List all stations with resolved current prices and active brand benefits."""
    stations = list(session.exec(select(Station).order_by(Station.name)).all())
    return _build_station_reads(stations, session, now)


def get_station(station_id: int, session: Session, now: datetime) -> StationRead:
    """Fetch a single station by ID or raise 404."""
    station = session.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
    return _build_station_reads([station], session, now)[0]


def create_station(payload: StationCreate, session: Session, now: datetime) -> StationRead:
    """Create a new fuel station with server-assigned timestamp."""
    station = Station(
        name=payload.name.strip(),
        brand=payload.brand.strip(),
        address=payload.address.strip(),
        district=payload.district.strip(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        created_at=now,
    )
    session.add(station)
    session.commit()
    session.refresh(station)
    assert station.id is not None
    return get_station(station.id, session, now)


def update_station(
    station_id: int,
    payload: StationUpdate,
    session: Session,
    now: datetime,
) -> StationRead:
    """Update an existing station or raise 404."""
    station = session.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")

    station.name = payload.name.strip()
    station.brand = payload.brand.strip()
    station.address = payload.address.strip()
    station.district = payload.district.strip()
    station.latitude = payload.latitude
    station.longitude = payload.longitude

    session.add(station)
    session.commit()
    session.refresh(station)
    return get_station(station_id, session, now)


def delete_station(station_id: int, session: Session) -> None:
    """Delete a station and its dependent price reports/votes atomically, or raise 404."""
    station = session.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")

    report_ids = list(
        session.exec(select(PriceReport.id).where(PriceReport.station_id == station_id)).all()
    )
    valid_report_ids = [rid for rid in report_ids if rid is not None]
    if valid_report_ids:
        session.exec(delete(PriceVote).where(PriceVote.report_id.in_(valid_report_ids)))  # type: ignore[attr-defined]
        session.exec(delete(PriceReport).where(PriceReport.station_id == station_id))

    session.delete(station)
    session.commit()
