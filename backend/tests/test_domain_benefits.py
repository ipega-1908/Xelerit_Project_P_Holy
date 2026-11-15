from datetime import UTC, datetime

from app.domain.benefits import BenefitRule, is_benefit_active, select_best_benefit


def _make_rule(
    *,
    brand: str = "Orlen",
    app_name: str = "Orlen Vitay",
    discount_per_liter: float = 0.30,
    fuel_type: str | None = None,
    max_liters: float | None = 50.0,
    valid_from: datetime = datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
    valid_to: datetime = datetime(2026, 12, 31, 23, 59, tzinfo=UTC),
    active_weekdays: tuple[int, ...] | None = None,
    start_hour: int | None = None,
    end_hour: int | None = None,
) -> BenefitRule:
    return BenefitRule(
        brand=brand,
        app_name=app_name,
        discount_per_liter=discount_per_liter,
        fuel_type=fuel_type,
        max_liters=max_liters,
        valid_from=valid_from,
        valid_to=valid_to,
        checked_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        active_weekdays=active_weekdays,
        start_hour=start_hour,
        end_hour=end_hour,
    )


def test_weekend_rule_warsaw_vs_utc_boundary() -> None:
    # Weekend rule: Saturday (5) and Sunday (6) in Europe/Warsaw.
    weekend_rule = _make_rule(active_weekdays=(5, 6))

    # Friday 23:30 in Warsaw (CET = UTC+1) -> 22:30 UTC on Friday 2026-11-13 -> still Friday.
    friday_2330_warsaw = datetime(2026, 11, 13, 22, 30, tzinfo=UTC)
    assert is_benefit_active(weekend_rule, friday_2330_warsaw) is False

    # Friday 23:30 UTC -> 00:30 Saturday in Warsaw -> weekend rule IS already active!
    friday_2330_utc = datetime(2026, 11, 13, 23, 30, tzinfo=UTC)
    assert is_benefit_active(weekend_rule, friday_2330_utc) is True

    # Friday-only rule evaluated at 23:30 Warsaw (22:30 UTC) must still be active.
    friday_rule = _make_rule(active_weekdays=(4,))
    assert is_benefit_active(friday_rule, friday_2330_warsaw) is True


def test_warsaw_hour_window_including_dst() -> None:
    # Happy hours 15:00-18:00 Warsaw time.
    happy_hours = _make_rule(start_hour=15, end_hour=18)

    # In July (CEST = UTC+2), 13:30 UTC is 15:30 in Warsaw -> active.
    summer_active = datetime(2026, 7, 15, 13, 30, tzinfo=UTC)
    assert is_benefit_active(happy_hours, summer_active) is True

    # In November (CET = UTC+1), 13:30 UTC is 14:30 in Warsaw -> not active yet.
    winter_inactive = datetime(2026, 11, 15, 13, 30, tzinfo=UTC)
    assert is_benefit_active(happy_hours, winter_inactive) is False


def test_expired_and_not_yet_valid_benefits() -> None:
    rule = _make_rule(
        valid_from=datetime(2026, 11, 10, 0, 0, tzinfo=UTC),
        valid_to=datetime(2026, 11, 14, 23, 59, tzinfo=UTC),
    )

    assert is_benefit_active(rule, datetime(2026, 11, 9, 23, 59, tzinfo=UTC)) is False
    assert is_benefit_active(rule, datetime(2026, 11, 12, 12, 0, tzinfo=UTC)) is True
    assert is_benefit_active(rule, datetime(2026, 11, 15, 0, 0, tzinfo=UTC)) is False


def test_select_best_benefit_respects_apps_fuel_and_liter_cap() -> None:
    now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)  # Sunday in Warsaw
    rules = [
        _make_rule(
            brand="Orlen",
            app_name="Orlen Vitay",
            discount_per_liter=0.40,
            max_liters=20.0,  # 8.00 PLN max savings for 60 L
        ),
        _make_rule(
            brand="Orlen",
            app_name="Orlen Vitay",
            discount_per_liter=0.25,
            max_liters=60.0,  # 15.00 PLN savings for 60 L -> better for large tank!
        ),
        _make_rule(
            brand="Orlen",
            app_name="Orlen Vitay",
            discount_per_liter=0.50,
            fuel_type="LPG",
            max_liters=None,
        ),
        _make_rule(
            brand="BP",
            app_name="BPme",
            discount_per_liter=0.50,
            max_liters=None,
        ),
    ]

    # For 60 L of PB95, the 0.25 PLN/L (up to 60 L) rule saves 15 PLN vs 8 PLN.
    best_large = select_best_benefit(
        rules=rules,
        brand="Orlen",
        fuel_type="PB95",
        user_apps=["Orlen Vitay"],
        liters=60.0,
        now=now,
    )
    assert best_large is not None
    assert best_large.discount_per_liter == 0.25

    # For 20 L of PB95, the 0.40 PLN/L (up to 20 L) rule saves 8 PLN vs 5 PLN.
    best_small = select_best_benefit(
        rules=rules,
        brand="Orlen",
        fuel_type="PB95",
        user_apps=["Orlen Vitay"],
        liters=20.0,
        now=now,
    )
    assert best_small is not None
    assert best_small.discount_per_liter == 0.40

    # Without the station's app, no benefit applies.
    no_app = select_best_benefit(
        rules=rules,
        brand="Orlen",
        fuel_type="PB95",
        user_apps=["BPme"],
        liters=40.0,
        now=now,
    )
    assert no_app is None
