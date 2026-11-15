from datetime import datetime

from fastapi import HTTPException, status
from sqlmodel import Session

from app.domain.auth import AuthActor
from app.domain.benefits import ensure_utc
from app.models import Benefit
from app.schemas import BenefitCreate, BenefitRead, BenefitUpdate
from app.services.pricing import benefit_to_read, list_visible_benefits, serialize_weekdays


def _viewer_user_id(actor: AuthActor | None) -> int | None:
    if actor is None or actor.role != "user":
        return None
    return actor.user_id


def _ensure_can_modify(benefit: Benefit, actor: AuthActor) -> None:
    """Enforce ownership: admins manage global benefits; users manage only their own."""
    if actor.role == "admin":
        if benefit.owner_id is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator zarządza wyłącznie globalnymi rabatami",
            )
        return

    if benefit.owner_id != actor.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Możesz edytować i usuwać tylko własne rabaty",
        )


def list_benefits(session: Session, actor: AuthActor | None = None) -> list[BenefitRead]:
    """Return global benefits plus private benefits owned by the signed-in user."""
    viewer_id = _viewer_user_id(actor)
    benefits = list_visible_benefits(session, viewer_id)
    return [benefit_to_read(b, viewer_user_id=viewer_id) for b in benefits]


def get_benefit(
    benefit_id: int,
    session: Session,
    actor: AuthActor | None = None,
) -> BenefitRead:
    """Fetch a single visible benefit by ID or raise 403/404."""
    benefit = session.get(Benefit, benefit_id)
    if benefit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benefit not found")
    viewer_id = _viewer_user_id(actor)
    if benefit.owner_id is not None and benefit.owner_id != viewer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Brak dostępu do prywatnego rabatu innego użytkownika",
        )
    return benefit_to_read(benefit, viewer_user_id=viewer_id)


def create_benefit(
    payload: BenefitCreate,
    session: Session,
    now: datetime,
    actor: AuthActor,
) -> BenefitRead:
    """Create a global (admin) or private (user) benefit with server checked_at."""
    owner_id = actor.user_id if actor.role == "user" else None
    benefit = Benefit(
        owner_id=owner_id,
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
    return benefit_to_read(benefit, viewer_user_id=_viewer_user_id(actor))


def update_benefit(
    benefit_id: int,
    payload: BenefitUpdate,
    session: Session,
    now: datetime,
    actor: AuthActor,
) -> BenefitRead:
    """Update an existing benefit owned by the caller and refresh checked_at."""
    benefit = session.get(Benefit, benefit_id)
    if benefit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benefit not found")
    _ensure_can_modify(benefit, actor)

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
    return benefit_to_read(benefit, viewer_user_id=_viewer_user_id(actor))


def delete_benefit(benefit_id: int, session: Session, actor: AuthActor) -> None:
    """Delete an existing benefit owned by the caller or raise 403/404."""
    benefit = session.get(Benefit, benefit_id)
    if benefit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benefit not found")
    _ensure_can_modify(benefit, actor)
    session.delete(benefit)
    session.commit()
