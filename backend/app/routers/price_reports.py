from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from app.database import get_session
from app.dependencies import get_now, get_user_id
from app.schemas import (
    CorrectionCreate,
    CorrectionRead,
    FuelTypeLiteral,
    PriceReportCreate,
    PriceReportRead,
    PriceVoteRead,
)
from app.services import price_reports as price_report_service

router = APIRouter(tags=["price-reports"])

SessionDep = Annotated[Session, Depends(get_session)]
NowDep = Annotated[datetime, Depends(get_now)]
UserIdDep = Annotated[str, Depends(get_user_id)]


@router.get("/stations/{station_id}/price-reports", response_model=list[PriceReportRead])
def list_station_price_reports(
    station_id: int,
    session: SessionDep,
    fuel_type: Annotated[FuelTypeLiteral | None, Query()] = None,
) -> list[PriceReportRead]:
    """List historical price reports for a fuel station."""
    return price_report_service.list_station_price_reports(
        station_id=station_id,
        session=session,
        fuel_type=fuel_type,
    )


@router.post(
    "/stations/{station_id}/price-reports",
    response_model=PriceReportRead,
    status_code=status.HTTP_201_CREATED,
)
def create_price_report(
    station_id: int,
    payload: PriceReportCreate,
    session: SessionDep,
    now: NowDep,
    user_id: UserIdDep,
) -> PriceReportRead:
    """Submit a new fuel price report for a station."""
    return price_report_service.create_price_report(
        station_id=station_id,
        payload=payload,
        user_id=user_id,
        session=session,
        now=now,
    )


@router.post(
    "/price-reports/{report_id}/confirmations",
    response_model=PriceVoteRead,
    status_code=status.HTTP_201_CREATED,
)
def confirm_price_report(
    report_id: int,
    session: SessionDep,
    now: NowDep,
    user_id: UserIdDep,
) -> PriceVoteRead:
    """Confirm an existing fuel price report."""
    return price_report_service.confirm_price_report(
        report_id=report_id,
        user_id=user_id,
        session=session,
        now=now,
    )


@router.post(
    "/price-reports/{report_id}/corrections",
    response_model=CorrectionRead,
    status_code=status.HTTP_201_CREATED,
)
def correct_price_report(
    report_id: int,
    payload: CorrectionCreate,
    session: SessionDep,
    now: NowDep,
    user_id: UserIdDep,
) -> CorrectionRead:
    """Reject an incorrect price report and submit a corrected price atomically."""
    return price_report_service.correct_price_report(
        report_id=report_id,
        payload=payload,
        user_id=user_id,
        session=session,
        now=now,
    )
