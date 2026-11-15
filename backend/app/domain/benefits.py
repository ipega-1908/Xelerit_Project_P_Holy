from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.domain.calculator import calculate_discount_amount

WARSAW_TZ = ZoneInfo("Europe/Warsaw")


@dataclass(frozen=True)
class BenefitRule:
    """Loyalty app discount rule evaluated against UTC validity and Warsaw local schedule."""

    brand: str
    app_name: str
    discount_per_liter: float
    valid_from: datetime
    valid_to: datetime
    checked_at: datetime
    fuel_type: str | None = None
    max_liters: float | None = None
    active_weekdays: tuple[int, ...] | None = None  # 0=Mon .. 6=Sun in Europe/Warsaw
    start_hour: int | None = None
    end_hour: int | None = None
    description: str = ""
    benefit_id: int | None = None


def ensure_utc(dt: datetime) -> datetime:
    """Normalize naive datetimes (e.g. from SQLite) to UTC or convert aware ones to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _is_hour_in_window(hour: int, start_hour: int | None, end_hour: int | None) -> bool:
    if start_hour is None and end_hour is None:
        return True
    if start_hour is not None and end_hour is not None:
        if start_hour <= end_hour:
            return start_hour <= hour < end_hour
        # Overnight window (e.g. 22:00 - 06:00).
        return hour >= start_hour or hour < end_hour
    if start_hour is not None:
        return hour >= start_hour
    return hour < end_hour  # type: ignore[operator]


def is_benefit_active(rule: BenefitRule, now: datetime) -> bool:
    """Check whether a benefit rule is active at `now` (schedule evaluated in Europe/Warsaw)."""
    now_utc = ensure_utc(now)
    valid_from_utc = ensure_utc(rule.valid_from)
    valid_to_utc = ensure_utc(rule.valid_to)

    if not (valid_from_utc <= now_utc <= valid_to_utc):
        return False

    local_now = now_utc.astimezone(WARSAW_TZ)

    if rule.active_weekdays is not None and local_now.weekday() not in rule.active_weekdays:
        return False

    return _is_hour_in_window(local_now.hour, rule.start_hour, rule.end_hour)


def select_best_benefit(
    rules: list[BenefitRule],
    brand: str,
    fuel_type: str,
    user_apps: set[str] | list[str],
    liters: float,
    now: datetime,
) -> BenefitRule | None:
    """Return the active benefit for the station's brand and user's apps yielding max savings."""
    normalized_brand = brand.strip().lower()
    normalized_fuel = fuel_type.strip().upper()
    normalized_apps = {app.strip().lower() for app in user_apps if app.strip()}

    if not normalized_apps or liters <= 0:
        return None

    matching: list[BenefitRule] = []
    for rule in rules:
        if rule.brand.strip().lower() != normalized_brand:
            continue
        if rule.app_name.strip().lower() not in normalized_apps:
            continue
        if rule.fuel_type is not None and rule.fuel_type.strip().upper() != normalized_fuel:
            continue
        if not is_benefit_active(rule, now):
            continue
        matching.append(rule)

    if not matching:
        return None

    return max(
        matching,
        key=lambda r: (
            calculate_discount_amount(liters, r.discount_per_liter, r.max_liters),
            r.discount_per_liter,
            ensure_utc(r.checked_at),
        ),
    )
