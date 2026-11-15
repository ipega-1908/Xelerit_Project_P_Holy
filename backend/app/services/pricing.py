from datetime import datetime

from sqlmodel import Session, or_, select

from app.domain.benefits import BenefitRule, ensure_utc, is_benefit_active
from app.domain.consensus import (
    COMPARISON_RADIUS_KM,
    CONSENSUS_WINDOW_DAYS,
    SUPPORTED_FUEL_TYPES,
    PriceResolution,
    ReportRecord,
    ReportSource,
    VoteRecord,
    VoteType,
    resolve_current_price,
)
from app.domain.distance import haversine_km
from app.models import Benefit, PriceReport, PriceVote, Station
from app.schemas import BenefitRead, FuelPriceSummary


def parse_weekdays(raw: str | None) -> list[int] | None:
    """Parse comma-separated weekday integers from DB into a sorted list."""
    if raw is None or not raw.strip():
        return None
    return sorted({int(part.strip()) for part in raw.split(",") if part.strip()})


def serialize_weekdays(weekdays: list[int] | None) -> str | None:
    """Serialize weekday integers into a canonical comma-separated string."""
    if weekdays is None:
        return None
    return ",".join(str(day) for day in sorted(set(weekdays)))


def benefit_to_rule(benefit: Benefit) -> BenefitRule:
    """Convert a Benefit DB row into a pure domain BenefitRule."""
    weekdays = parse_weekdays(benefit.active_weekdays)
    return BenefitRule(
        benefit_id=benefit.id,
        brand=benefit.brand,
        app_name=benefit.app_name,
        fuel_type=benefit.fuel_type,
        discount_per_liter=benefit.discount_per_liter,
        max_liters=benefit.max_liters,
        active_weekdays=tuple(weekdays) if weekdays is not None else None,
        start_hour=benefit.start_hour,
        end_hour=benefit.end_hour,
        valid_from=ensure_utc(benefit.valid_from),
        valid_to=ensure_utc(benefit.valid_to),
        checked_at=ensure_utc(benefit.checked_at),
        description=benefit.description,
    )


def benefit_to_read(benefit: Benefit, viewer_user_id: int | None = None) -> BenefitRead:
    """Map Benefit DB model to API response schema."""
    assert benefit.id is not None
    return BenefitRead(
        id=benefit.id,
        owner_id=benefit.owner_id,
        is_own=(viewer_user_id is not None and benefit.owner_id == viewer_user_id),
        brand=benefit.brand,
        app_name=benefit.app_name,
        fuel_type=benefit.fuel_type,  # type: ignore[arg-type]
        discount_per_liter=benefit.discount_per_liter,
        max_liters=benefit.max_liters,
        active_weekdays=parse_weekdays(benefit.active_weekdays),
        start_hour=benefit.start_hour,
        end_hour=benefit.end_hour,
        valid_from=ensure_utc(benefit.valid_from),
        valid_to=ensure_utc(benefit.valid_to),
        checked_at=ensure_utc(benefit.checked_at),
        description=benefit.description,
    )


def list_visible_benefits(session: Session, viewer_user_id: int | None) -> list[Benefit]:
    """Return global benefits plus private benefits belonging to the signed-in user."""
    if viewer_user_id is None:
        stmt = select(Benefit).where(Benefit.owner_id.is_(None))  # type: ignore[union-attr]
    else:
        stmt = select(Benefit).where(
            or_(Benefit.owner_id.is_(None), Benefit.owner_id == viewer_user_id)  # type: ignore[union-attr]
        )
    return list(session.exec(stmt.order_by(Benefit.brand, Benefit.id)).all())


def _to_report_record(report: PriceReport) -> ReportRecord:
    assert report.id is not None
    return ReportRecord(
        report_id=report.id,
        price=report.price,
        user_id=report.user_id,
        reported_at=report.reported_at,
        source=ReportSource(report.source),
    )


def _to_vote_record(vote: PriceVote) -> VoteRecord:
    return VoteRecord(
        report_id=vote.report_id,
        user_id=vote.user_id,
        vote_type=VoteType(vote.vote_type),
        created_at=vote.created_at,
    )


def resolve_all_station_prices(
    stations: list[Station],
    reports: list[PriceReport],
    votes: list[PriceVote],
    now: datetime,
) -> dict[int, dict[str, PriceResolution]]:
    """Resolve current price per (station_id, fuel_type) including nearby-station comparison."""
    votes_by_report: dict[int, list[VoteRecord]] = {}
    for vote in votes:
        votes_by_report.setdefault(vote.report_id, []).append(_to_vote_record(vote))

    reports_by_station_fuel: dict[tuple[int, str], list[ReportRecord]] = {}
    for report in reports:
        key = (report.station_id, report.fuel_type.upper())
        reports_by_station_fuel.setdefault(key, []).append(_to_report_record(report))

    # First pass: determine each station's base consensus price without outlier flagging.
    base_resolutions: dict[tuple[int, str], PriceResolution] = {}
    for station in stations:
        assert station.id is not None
        for fuel_type in SUPPORTED_FUEL_TYPES:
            key = (station.id, fuel_type)
            station_reports = reports_by_station_fuel.get(key, [])
            station_votes = [
                v for r in station_reports for v in votes_by_report.get(r.report_id, [])
            ]
            base_resolutions[key] = resolve_current_price(
                reports=station_reports,
                votes=station_votes,
                now=now,
            )

    max_age_hours = CONSENSUS_WINDOW_DAYS * 24.0
    final_resolutions: dict[int, dict[str, PriceResolution]] = {}

    for station in stations:
        assert station.id is not None
        station_prices: dict[str, PriceResolution] = {}
        for fuel_type in SUPPORTED_FUEL_TYPES:
            key = (station.id, fuel_type)
            nearby_prices: list[float] = []
            for other in stations:
                assert other.id is not None
                if other.id == station.id:
                    continue
                if (
                    haversine_km(
                        station.latitude,
                        station.longitude,
                        other.latitude,
                        other.longitude,
                    )
                    > COMPARISON_RADIUS_KM
                ):
                    continue
                other_res = base_resolutions[(other.id, fuel_type)]
                if (
                    other_res.price is not None
                    and other_res.age_hours is not None
                    and other_res.age_hours <= max_age_hours
                ):
                    nearby_prices.append(other_res.price)

            station_reports = reports_by_station_fuel.get(key, [])
            station_votes = [
                v for r in station_reports for v in votes_by_report.get(r.report_id, [])
            ]
            station_prices[fuel_type] = resolve_current_price(
                reports=station_reports,
                votes=station_votes,
                now=now,
                nearby_prices=nearby_prices,
            )
        final_resolutions[station.id] = station_prices

    return final_resolutions


def resolution_to_summary(fuel_type: str, res: PriceResolution) -> FuelPriceSummary:
    """Convert domain PriceResolution to API FuelPriceSummary schema."""
    return FuelPriceSummary(
        fuel_type=fuel_type,  # type: ignore[arg-type]
        price=res.price,
        status=res.status,
        support=res.support,
        confirmations_count=res.confirmations_count,
        rejections_count=res.rejections_count,
        reported_at=res.reported_at,
        age_hours=res.age_hours,
        winning_report_id=res.winning_report_id,
        needs_warning=res.needs_warning,
    )


def get_active_benefits_for_brand(
    benefits: list[Benefit],
    brand: str,
    now: datetime,
    viewer_user_id: int | None = None,
) -> list[BenefitRead]:
    """Return currently active BenefitRead items for a given station brand."""
    normalized = brand.strip().lower()
    active: list[BenefitRead] = []
    for benefit in benefits:
        if benefit.brand.strip().lower() != normalized:
            continue
        if is_benefit_active(benefit_to_rule(benefit), now):
            active.append(benefit_to_read(benefit, viewer_user_id=viewer_user_id))
    return active
