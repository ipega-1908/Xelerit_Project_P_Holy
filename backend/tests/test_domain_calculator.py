import pytest

from app.domain.calculator import (
    calculate_detour_cost,
    calculate_discount_amount,
    calculate_min_liters,
    evaluate_detour,
)
from app.domain.distance import calculate_extra_km, estimated_road_distance_km, haversine_km


def test_haversine_and_road_factor() -> None:
    # Gdansk Glowny -> Wrzeszcz (~3.8 km straight line)
    straight = haversine_km(54.3557, 18.6443, 54.3812, 18.6095)
    road = estimated_road_distance_km(54.3557, 18.6443, 54.3812, 18.6095)

    assert 3.0 < straight < 4.5
    assert road == pytest.approx(straight * 1.3)


def test_calculate_extra_km_round_trip() -> None:
    assert calculate_extra_km(distance_to_station_km=5.0, distance_to_reference_km=1.5) == 7.0
    # Station closer than or equal to reference cannot produce negative detour
    assert calculate_extra_km(distance_to_station_km=1.0, distance_to_reference_km=2.0) == 0.0


def test_evaluate_detour_profitable_without_discount() -> None:
    # extra_km=10, consumption=8 l/100km, price=6.00 -> detour_cost = 4.80
    # savings = 50 * (6.50 - 6.00) = 25.00 -> net_gain = 20.20, min_liters = 4.80 / 0.50 = 9.60
    result = evaluate_detour(
        extra_km=10.0,
        consumption_per_100km=8.0,
        liters=50.0,
        usual_price=6.50,
        target_pump_price=6.00,
    )

    assert result.detour_cost == 4.80
    assert result.savings == 25.00
    assert result.net_gain == 20.20
    assert result.min_liters == 9.60
    assert result.effective_price_per_liter == 6.00
    assert result.is_profitable is True


def test_evaluate_detour_zero_and_negative_price_difference() -> None:
    zero_diff = evaluate_detour(
        extra_km=6.0,
        consumption_per_100km=7.0,
        liters=40.0,
        usual_price=6.40,
        target_pump_price=6.40,
    )
    assert zero_diff.savings == 0.0
    assert zero_diff.net_gain < 0
    assert zero_diff.min_liters is None
    assert zero_diff.is_profitable is False

    negative_diff = evaluate_detour(
        extra_km=6.0,
        consumption_per_100km=7.0,
        liters=40.0,
        usual_price=6.20,
        target_pump_price=6.50,
    )
    assert negative_diff.savings < 0
    assert negative_diff.min_liters is None
    assert negative_diff.is_profitable is False


def test_discount_with_max_liters_cap() -> None:
    assert calculate_discount_amount(liters=30.0, discount_per_liter=0.30, max_liters=50.0) == 9.0
    assert calculate_discount_amount(liters=70.0, discount_per_liter=0.30, max_liters=50.0) == 15.0

    # Refuel 80 L with 0.40 PLN/L discount capped at 50 L:
    # Pump price 6.40, usual price 6.50 -> base diff 0.10/L + capped 20.00 PLN = 28.00 PLN savings.
    result = evaluate_detour(
        extra_km=10.0,
        consumption_per_100km=8.0,
        liters=80.0,
        usual_price=6.50,
        target_pump_price=6.40,
        discount_per_liter=0.40,
        max_liters=50.0,
    )
    # detour_cost = 10 * 8 / 100 * 6.00 = 4.80
    assert result.detour_cost == 4.80
    assert result.savings == 28.00
    assert result.net_gain == 23.20
    assert result.effective_price_per_liter == 6.15
    assert result.min_liters == 9.60


def test_min_liters_beyond_max_liters_cap() -> None:
    # First 10 L save 0.50/L = 5.00 PLN; remaining detour_cost = 4.00 PLN.
    # Pump price 6.40 vs usual 6.50 -> 0.10/L after cap -> 4.00 / 0.10 = 40 more liters -> 50 L.
    min_liters = calculate_min_liters(
        detour_cost=9.00,
        usual_price=6.50,
        target_pump_price=6.40,
        discount_per_liter=0.40,
        max_liters=10.0,
    )
    assert min_liters == pytest.approx(50.0)

    # If pump price equals usual price, break-even beyond cap is impossible.
    impossible = calculate_min_liters(
        detour_cost=9.00,
        usual_price=6.40,
        target_pump_price=6.40,
        discount_per_liter=0.40,
        max_liters=10.0,
    )
    assert impossible is None


def test_zero_detour_cost_yields_zero_min_liters() -> None:
    assert calculate_detour_cost(extra_km=0.0, consumption_per_100km=8.0, fuel_price=6.20) == 0.0
    assert (
        calculate_min_liters(
            detour_cost=0.0,
            usual_price=6.50,
            target_pump_price=6.20,
        )
        == 0.0
    )
