from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlmodel import Session

from app.database import get_session
from app.dependencies import get_now, get_optional_actor, require_admin
from app.domain.auth import AuthActor
from app.schemas import StationCreate, StationRead, StationUpdate
from app.services import stations as station_service

router = APIRouter(prefix="/stations", tags=["stations"])

SessionDep = Annotated[Session, Depends(get_session)]
NowDep = Annotated[datetime, Depends(get_now)]
AdminDep = Annotated[str, Depends(require_admin)]
OptionalActorDep = Annotated[AuthActor | None, Depends(get_optional_actor)]


@router.get("", response_model=list[StationRead])
def list_stations(
    session: SessionDep,
    now: NowDep,
    actor: OptionalActorDep,
) -> list[StationRead]:
    """List all fuel stations with current resolved prices and active app benefits."""
    viewer_id = actor.user_id if actor and actor.role == "user" else None
    return station_service.list_stations(session=session, now=now, viewer_user_id=viewer_id)


@router.get("/{station_id}", response_model=StationRead)
def get_station(
    station_id: int,
    session: SessionDep,
    now: NowDep,
    actor: OptionalActorDep,
) -> StationRead:
    """Retrieve a single fuel station by ID."""
    viewer_id = actor.user_id if actor and actor.role == "user" else None
    return station_service.get_station(
        station_id=station_id,
        session=session,
        now=now,
        viewer_user_id=viewer_id,
    )


@router.post("", response_model=StationRead, status_code=status.HTTP_201_CREATED)
def create_station(payload: StationCreate, session: SessionDep, now: NowDep) -> StationRead:
    """Create a new fuel station."""
    return station_service.create_station(payload=payload, session=session, now=now)


@router.put("/{station_id}", response_model=StationRead)
def update_station(
    station_id: int,
    payload: StationUpdate,
    session: SessionDep,
    now: NowDep,
    _admin: AdminDep,
) -> StationRead:
    """Update an existing fuel station (admin only)."""
    return station_service.update_station(
        station_id=station_id,
        payload=payload,
        session=session,
        now=now,
    )


@router.delete("/{station_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_station(station_id: int, session: SessionDep, _admin: AdminDep) -> Response:
    """Delete a fuel station and its historical price reports (admin only)."""
    station_service.delete_station(station_id=station_id, session=session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
