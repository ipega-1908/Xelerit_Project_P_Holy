from datetime import datetime

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.domain.benefits import ensure_utc
from app.models import Benefit
from app.schemas import BenefitCreate, BenefitRead, BenefitUpdate
from app.services.pricing import benefit_to_read, serialize_weekdays


def list_benefits(session: Session) -> list[BenefitRead]:
    """Return all configured loyalty app benefits."""
    benefits = list(session.exec(select(Benefit).order_by(Benefit.brand, Benefit.id)).all())
    return [benefit_to_read(b) for b in benefits]


def get_benefit(benefit_id: int, session: Session) -> BenefitRead:
    """Fetch a single benefit by ID or raise 404."""
    benefit = session.get(Benefit, benefit_id)
    if benefit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benefit not found")
    return benefit_to_read(benefit)


def create_benefit(payload: BenefitCreate, session: Session, now: datetime) -> BenefitRead:
    """Create a loyalty app benefit with server-assigned checked_at timestamp."""
    benefit = Benefit(
        brand=payload.brand.strip(),
        app_name=payload.app_name.strip(),
        fuel_type=payload.fuel_type,
        discount_per_liter=round(payload.discount_per_liter, 2),
        max_liters=payload.max_liters,
        active_weekdays=serialize_weekdays(payload.active_weekdays),
        start_hour=payload.start_hour,
        end_hour=payload.end_hour,
        valid_from=ensure_utc(payload.valid_from),
        valid_to=ensure_utc(payload.valid_to),
        checked_at=now,
        description=payload.description.strip(),
    )
    session.add(benefit)
    session.commit()
    session.refresh(benefit)
    return benefit_to_read(benefit)


def update_benefit(
    benefit_id: int,
    payload: BenefitUpdate,
    session: Session,
    now: datetime,
) -> BenefitRead:
    """Update an existing benefit and refresh checked_at to server time, or raise 404."""
    benefit = session.get(Benefit, benefit_id)
    if benefit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benefit not found")

    benefit.brand = payload.brand.strip()
    benefit.app_name = payload.app_name.strip()
    benefit.fuel_type = payload.fuel_type
    benefit.discount_per_liter = round(payload.discount_per_liter, 2)
    benefit.max_liters = payload.max_liters
    benefit.active_weekdays = serialize_weekdays(payload.active_weekdays)
    benefit.start_hour = payload.start_hour
    benefit.end_hour = payload.end_hour
    benefit.valid_from = ensure_utc(payload.valid_from)
    benefit.valid_to = ensure_utc(payload.valid_to)
    benefit.checked_at = now
    benefit.description = payload.description.strip()

    session.add(benefit)
    session.commit()
    session.refresh(benefit)
    return benefit_to_read(benefit)


def delete_benefit(benefit_id: int, session: Session) -> None:
    """Delete a benefit by ID or raise 404."""
    benefit = session.get(Benefit, benefit_id)
    if benefit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benefit not found")
    session.delete(benefit)
    session.commit()
