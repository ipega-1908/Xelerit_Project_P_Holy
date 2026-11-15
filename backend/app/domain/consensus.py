from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from statistics import median

from app.domain.benefits import ensure_utc

MIN_PRICE_PLN = 3.00
MAX_PRICE_PLN = 15.00
MAX_DEVIATION_PLN = 1.0
MIN_CONFIRMATIONS = 2
CONSENSUS_WINDOW_DAYS = 3
MIN_NEARBY_STATIONS = 3
COMPARISON_RADIUS_KM = 10.0

SUPPORTED_FUEL_TYPES: tuple[str, ...] = ("PB95", "PB98", "ON", "LPG")


class PriceStatus(StrEnum):
    """Confidence and freshness state of a station's resolved fuel price."""

    VERIFIED = "verified"
    UNCONFIRMED = "unconfirmed"
    SUSPICIOUS = "suspicious"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class VoteType(StrEnum):
    """User vote on a specific price report."""

    CONFIRM = "confirm"
    REJECT = "reject"


class ReportSource(StrEnum):
    """Origin of a fuel price report; verified photos carry initial trust."""

    MANUAL = "manual"
    PHOTO = "photo"


@dataclass(frozen=True)
class ReportRecord:
    """Pure domain representation of a price report."""

    report_id: int
    price: float
    user_id: str
    reported_at: datetime
    source: ReportSource = ReportSource.MANUAL


@dataclass(frozen=True)
class VoteRecord:
    """Pure domain representation of a vote on a price report."""

    report_id: int
    user_id: str
    vote_type: VoteType
    created_at: datetime


@dataclass(frozen=True)
class PriceResolution:
    """Resolved current price for a station and fuel type."""

    price: float | None
    status: PriceStatus
    support: int
    confirmations_count: int
    rejections_count: int
    reported_at: datetime | None
    winning_report_id: int | None
    age_hours: float | None

    @property
    def needs_warning(self) -> bool:
        """Whether calculator should warn user about price reliability or age."""
        return self.status != PriceStatus.VERIFIED


def validate_price_range(price: float) -> None:
    """Ensure fuel price falls within the accepted 3.00-15.00 PLN range."""
    rounded = round(price, 2)
    if rounded < MIN_PRICE_PLN or rounded > MAX_PRICE_PLN:
        raise ValueError(f"Price must be between {MIN_PRICE_PLN:.2f} and {MAX_PRICE_PLN:.2f} PLN")


def validate_correction(previous_price: float, new_price: float) -> None:
    """Validate correction price range and ensure it differs from the rejected price."""
    validate_price_range(new_price)
    if round(new_price, 2) == round(previous_price, 2):
        raise ValueError("Correction price must differ from the previous price")


def is_price_suspicious(price: float, nearby_prices: list[float] | None) -> bool:
    """Check if price deviates by > 1.00 PLN from nearby median (requires >= 3 stations)."""
    if not nearby_prices or len(nearby_prices) < MIN_NEARBY_STATIONS:
        return False
    area_median = median(nearby_prices)
    return abs(price - area_median) > MAX_DEVIATION_PLN


@dataclass
class _PriceGroup:
    price: float
    supporters: set[str]
    confirmers: set[str]
    rejectors: set[str]
    latest_reported_at: datetime
    latest_report_id: int
    latest_photo_key: tuple[datetime, int] | None = None
    rejected_photo_ids: set[int] | None = None

    @property
    def is_trusted_photo(self) -> bool:
        """Return True if the newest photo report at this price has not been rejected."""
        if self.latest_photo_key is None:
            return False
        rejected = self.rejected_photo_ids or set()
        return self.latest_photo_key[1] not in rejected

    @property
    def support(self) -> int:
        raw_support = len(self.supporters) - len(self.rejectors)
        if self.is_trusted_photo:
            return max(raw_support, MIN_CONFIRMATIONS)
        return raw_support


def resolve_current_price(
    reports: list[ReportRecord],
    votes: list[VoteRecord],
    now: datetime,
    nearby_prices: list[float] | None = None,
) -> PriceResolution:
    """Determine the prevailing price via consensus within the active time window."""
    now_utc = ensure_utc(now)
    window_start = now_utc - timedelta(days=CONSENSUS_WINDOW_DAYS)

    historical_reports = [r for r in reports if ensure_utc(r.reported_at) <= now_utc]
    if not historical_reports:
        return PriceResolution(
            price=None,
            status=PriceStatus.UNKNOWN,
            support=0,
            confirmations_count=0,
            rejections_count=0,
            reported_at=None,
            winning_report_id=None,
            age_hours=None,
        )

    fresh_reports = [r for r in historical_reports if ensure_utc(r.reported_at) >= window_start]
    if not fresh_reports:
        latest_old = max(
            historical_reports,
            key=lambda r: (ensure_utc(r.reported_at), r.report_id),
        )
        latest_old_at = ensure_utc(latest_old.reported_at)
        age_hours = max(0.0, (now_utc - latest_old_at).total_seconds() / 3600.0)
        return PriceResolution(
            price=round(latest_old.price, 2),
            status=PriceStatus.EXPIRED,
            support=0,
            confirmations_count=0,
            rejections_count=0,
            reported_at=latest_old_at,
            winning_report_id=latest_old.report_id,
            age_hours=round(age_hours, 2),
        )

    report_by_id: dict[int, ReportRecord] = {r.report_id: r for r in fresh_reports}
    groups: dict[float, _PriceGroup] = {}

    for report in fresh_reports:
        normalized_price = round(report.price, 2)
        reported_at_utc = ensure_utc(report.reported_at)
        photo_key = (
            (reported_at_utc, report.report_id) if report.source == ReportSource.PHOTO else None
        )
        group = groups.get(normalized_price)
        if group is None:
            groups[normalized_price] = _PriceGroup(
                price=normalized_price,
                supporters={report.user_id},
                confirmers=set(),
                rejectors=set(),
                latest_reported_at=reported_at_utc,
                latest_report_id=report.report_id,
                latest_photo_key=photo_key,
                rejected_photo_ids=set(),
            )
        else:
            group.supporters.add(report.user_id)
            if (reported_at_utc, report.report_id) > (
                group.latest_reported_at,
                group.latest_report_id,
            ):
                group.latest_reported_at = reported_at_utc
                group.latest_report_id = report.report_id
            if photo_key is not None and (
                group.latest_photo_key is None or photo_key > group.latest_photo_key
            ):
                group.latest_photo_key = photo_key

    for vote in votes:
        vote_at_utc = ensure_utc(vote.created_at)
        if not (window_start <= vote_at_utc <= now_utc):
            continue
        report = report_by_id.get(vote.report_id)
        if report is None:
            continue

        group = groups[round(report.price, 2)]
        if vote.vote_type == VoteType.CONFIRM:
            # Report author cannot boost their own submission by confirming it.
            if vote.user_id == report.user_id:
                continue
            group.supporters.add(vote.user_id)
            group.confirmers.add(vote.user_id)
        elif vote.vote_type == VoteType.REJECT:
            group.rejectors.add(vote.user_id)
            if report.source == ReportSource.PHOTO and group.rejected_photo_ids is not None:
                group.rejected_photo_ids.add(report.report_id)

    winner = max(
        groups.values(),
        key=lambda g: (g.is_trusted_photo, g.support, g.latest_reported_at, g.latest_report_id),
    )

    if winner.support >= MIN_CONFIRMATIONS:
        status = PriceStatus.VERIFIED
    elif is_price_suspicious(winner.price, nearby_prices):
        status = PriceStatus.SUSPICIOUS
    else:
        status = PriceStatus.UNCONFIRMED

    age_hours = max(0.0, (now_utc - winner.latest_reported_at).total_seconds() / 3600.0)
    return PriceResolution(
        price=winner.price,
        status=status,
        support=winner.support,
        confirmations_count=len(winner.confirmers),
        rejections_count=len(winner.rejectors),
        reported_at=winner.latest_reported_at,
        winning_report_id=winner.latest_report_id,
        age_hours=round(age_hours, 2),
    )
