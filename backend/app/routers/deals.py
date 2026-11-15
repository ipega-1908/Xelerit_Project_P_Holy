from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.database import get_session
from app.dependencies import get_now, get_optional_actor
from app.domain.auth import AuthActor
from app.schemas import DealsResponse, FuelTypeLiteral
from app.services import deals as deals_service

router = APIRouter(prefix="/deals", tags=["deals"])

SessionDep = Annotated[Session, Depends(get_session)]
NowDep = Annotated[datetime, Depends(get_now)]
OptionalActorDep = Annotated[AuthActor | None, Depends(get_optional_actor)]


@router.get("", response_model=DealsResponse)
def get_deals(
    session: SessionDep,
    now: NowDep,
    actor: OptionalActorDep,
    lat: Annotated[float, Query(ge=-90.0, le=90.0)],
    lon: Annotated[float, Query(ge=-180.0, le=180.0)],
    fuel: Annotated[FuelTypeLiteral, Query()],
    liters: Annotated[float, Query(gt=0.0, le=500.0)] = 45.0,
    consumption: Annotated[float, Query(gt=0.0, le=50.0)] = 7.5,
    apps: Annotated[list[str] | None, Query()] = None,
) -> DealsResponse:
    """Calculate detour profitability ranking for stations from a user-selected start point."""
    parsed_apps = deals_service.parse_apps_param(apps)
    viewer_id = actor.user_id if actor and actor.role == "user" else None
    return deals_service.calculate_deals(
        lat=lat,
        lon=lon,
        fuel_type=fuel,
        liters=liters,
        consumption_per_100km=consumption,
        user_apps=parsed_apps,
        session=session,
        now=now,
        viewer_user_id=viewer_id,
    )
