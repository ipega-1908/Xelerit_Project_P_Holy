from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlmodel import Session

from app.database import get_session
from app.dependencies import get_now, get_optional_actor, require_actor
from app.domain.auth import AuthActor
from app.schemas import BenefitCreate, BenefitRead, BenefitUpdate
from app.services import benefits as benefit_service

router = APIRouter(prefix="/benefits", tags=["benefits"])

SessionDep = Annotated[Session, Depends(get_session)]
NowDep = Annotated[datetime, Depends(get_now)]
OptionalActorDep = Annotated[AuthActor | None, Depends(get_optional_actor)]
ActorDep = Annotated[AuthActor, Depends(require_actor)]


@router.get("", response_model=list[BenefitRead])
def list_benefits(session: SessionDep, actor: OptionalActorDep) -> list[BenefitRead]:
    """List global benefits and (when signed in) the current user's private benefits."""
    return benefit_service.list_benefits(session=session, actor=actor)


@router.get("/{benefit_id}", response_model=BenefitRead)
def get_benefit(
    benefit_id: int,
    session: SessionDep,
    actor: OptionalActorDep,
) -> BenefitRead:
    """Retrieve a single visible benefit by ID."""
    return benefit_service.get_benefit(benefit_id=benefit_id, session=session, actor=actor)


@router.post("", response_model=BenefitRead, status_code=status.HTTP_201_CREATED)
def create_benefit(
    payload: BenefitCreate,
    session: SessionDep,
    now: NowDep,
    actor: ActorDep,
) -> BenefitRead:
    """Create a private benefit (user) or global benefit (admin)."""
    return benefit_service.create_benefit(payload=payload, session=session, now=now, actor=actor)


@router.put("/{benefit_id}", response_model=BenefitRead)
def update_benefit(
    benefit_id: int,
    payload: BenefitUpdate,
    session: SessionDep,
    now: NowDep,
    actor: ActorDep,
) -> BenefitRead:
    """Update a benefit owned by the authenticated user or a global benefit as admin."""
    return benefit_service.update_benefit(
        benefit_id=benefit_id,
        payload=payload,
        session=session,
        now=now,
        actor=actor,
    )


@router.delete("/{benefit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_benefit(benefit_id: int, session: SessionDep, actor: ActorDep) -> Response:
    """Delete a benefit owned by the authenticated user or a global benefit as admin."""
    benefit_service.delete_benefit(benefit_id=benefit_id, session=session, actor=actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
