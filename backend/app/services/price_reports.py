from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.benefits import ensure_utc
from app.domain.consensus import ReportSource, VoteType, validate_correction, validate_price_range
from app.models import PriceReport, PriceVote, Station
from app.schemas import (
    CorrectionCreate,
    CorrectionRead,
    FuelTypeLiteral,
    PriceReportCreate,
    PriceReportRead,
    PriceVoteRead,
)


def _to_report_read(
    report: PriceReport,
    confirmations_count: int,
    rejections_count: int,
) -> PriceReportRead:
    assert report.id is not None
    return PriceReportRead(
        id=report.id,
        station_id=report.station_id,
        fuel_type=report.fuel_type,  # type: ignore[arg-type]
        price=round(report.price, 2),
        user_id=report.user_id,
        source=ReportSource(report.source),
        reported_at=ensure_utc(report.reported_at),
        confirmations_count=confirmations_count,
        rejections_count=rejections_count,
    )


def _to_vote_read(vote: PriceVote) -> PriceVoteRead:
    assert vote.id is not None
    return PriceVoteRead(
        id=vote.id,
        report_id=vote.report_id,
        user_id=vote.user_id,
        vote_type=VoteType(vote.vote_type),
        created_at=ensure_utc(vote.created_at),
    )


def list_station_price_reports(
    station_id: int,
    session: Session,
    fuel_type: FuelTypeLiteral | None = None,
) -> list[PriceReportRead]:
    """List historical price reports for a station, newest first."""
    if session.get(Station, station_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")

    stmt = select(PriceReport).where(PriceReport.station_id == station_id)
    if fuel_type is not None:
        stmt = stmt.where(PriceReport.fuel_type == fuel_type)
    stmt = stmt.order_by(PriceReport.reported_at.desc(), PriceReport.id.desc())  # type: ignore[union-attr]

    reports = list(session.exec(stmt).all())
    if not reports:
        return []

    report_ids = [r.id for r in reports if r.id is not None]
    votes = list(
        session.exec(
            select(PriceVote).where(PriceVote.report_id.in_(report_ids))  # type: ignore[attr-defined]
        ).all()
    )

    counts: dict[int, tuple[int, int]] = {rid: (0, 0) for rid in report_ids}
    for vote in votes:
        conf, rej = counts[vote.report_id]
        if vote.vote_type == VoteType.CONFIRM.value:
            counts[vote.report_id] = (conf + 1, rej)
        elif vote.vote_type == VoteType.REJECT.value:
            counts[vote.report_id] = (conf, rej + 1)

    return [
        _to_report_read(report, *counts[report.id])  # type: ignore[arg-type]
        for report in reports
    ]


def create_price_report(
    station_id: int,
    payload: PriceReportCreate,
    user_id: str,
    session: Session,
    now: datetime,
) -> PriceReportRead:
    """Insert a new immutable price report with server-assigned timestamp."""
    if session.get(Station, station_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")

    try:
        validate_price_range(payload.price)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    report = PriceReport(
        station_id=station_id,
        fuel_type=payload.fuel_type,
        price=round(payload.price, 2),
        user_id=user_id,
        source=payload.source.value,
        reported_at=now,
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return _to_report_read(report, confirmations_count=0, rejections_count=0)


def confirm_price_report(
    report_id: int,
    user_id: str,
    session: Session,
    now: datetime,
) -> PriceVoteRead:
    """Confirm an existing price report; blocks self-confirmations and duplicate votes (409)."""
    report = session.get(PriceReport, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Price report not found")

    if report.user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Author cannot confirm their own price report",
        )

    vote = PriceVote(
        report_id=report_id,
        user_id=user_id,
        vote_type=VoteType.CONFIRM.value,
        created_at=now,
    )
    session.add(vote)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User has already voted on this price report",
        ) from exc

    session.refresh(vote)
    return _to_vote_read(vote)


def correct_price_report(
    report_id: int,
    payload: CorrectionCreate,
    user_id: str,
    session: Session,
    now: datetime,
) -> CorrectionRead:
    """Atomically reject a report and insert a new corrected PriceReport in one transaction."""
    old_report = session.get(PriceReport, report_id)
    if old_report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Price report not found")

    try:
        validate_correction(previous_price=old_report.price, new_price=payload.price)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    existing_vote = session.exec(
        select(PriceVote).where(
            PriceVote.report_id == report_id,
            PriceVote.user_id == user_id,
        )
    ).first()
    if existing_vote is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User has already voted on this price report",
        )

    reject_vote = PriceVote(
        report_id=report_id,
        user_id=user_id,
        vote_type=VoteType.REJECT.value,
        created_at=now,
    )
    new_report = PriceReport(
        station_id=old_report.station_id,
        fuel_type=old_report.fuel_type,
        price=round(payload.price, 2),
        user_id=user_id,
        reported_at=now,
    )

    try:
        session.add(reject_vote)
        session.add(new_report)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User has already voted on this price report",
        ) from exc

    session.refresh(reject_vote)
    session.refresh(new_report)
    return CorrectionRead(
        rejected_report_id=report_id,
        vote=_to_vote_read(reject_vote),
        new_report=_to_report_read(new_report, confirmations_count=0, rejections_count=0),
    )
