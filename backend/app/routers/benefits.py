from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlmodel import Session

from app.database import get_session
from app.dependencies import get_now, require_admin
from app.schemas import BenefitCreate, BenefitRead, BenefitUpdate
from app.services import benefits as benefit_service

router = APIRouter(prefix="/benefits", tags=["benefits"])

SessionDep = Annotated[Session, Depends(get_session)]
NowDep = Annotated[datetime, Depends(get_now)]
AdminDep = Annotated[str, Depends(require_admin)]


@router.get("", response_model=list[BenefitRead])
def list_benefits(session: SessionDep) -> list[BenefitRead]:
    """List all loyalty app benefits."""
    return benefit_service.list_benefits(session=session)


@router.get("/{benefit_id}", response_model=BenefitRead)
def get_benefit(benefit_id: int, session: SessionDep) -> BenefitRead:
    """Retrieve a single benefit by ID."""
    return benefit_service.get_benefit(benefit_id=benefit_id, session=session)


@router.post("", response_model=BenefitRead, status_code=status.HTTP_201_CREATED)
def create_benefit(
    payload: BenefitCreate,
    session: SessionDep,
    now: NowDep,
    _admin: AdminDep,
) -> BenefitRead:
    """Create a new loyalty app benefit (admin only)."""
    return benefit_service.create_benefit(payload=payload, session=session, now=now)


@router.put("/{benefit_id}", response_model=BenefitRead)
def update_benefit(
    benefit_id: int,
    payload: BenefitUpdate,
    session: SessionDep,
    now: NowDep,
    _admin: AdminDep,
) -> BenefitRead:
    """Update an existing loyalty app benefit (admin only)."""
    return benefit_service.update_benefit(
        benefit_id=benefit_id,
        payload=payload,
        session=session,
        now=now,
    )


@router.delete("/{benefit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_benefit(benefit_id: int, session: SessionDep, _admin: AdminDep) -> Response:
    """Delete a loyalty app benefit (admin only)."""
    benefit_service.delete_benefit(benefit_id=benefit_id, session=session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
