from dataclasses import dataclass


@dataclass(frozen=True)
class DetourResult:
    """Result of detour profitability calculation."""

    detour_cost: float
    savings: float
    net_gain: float
    min_liters: float | None
    effective_price_per_liter: float
    is_profitable: bool


def calculate_discount_amount(
    liters: float,
    discount_per_liter: float,
    max_liters: float | None = None,
) -> float:
    """Compute total PLN discount respecting an optional per-refuel liter cap."""
    if liters < 0 or discount_per_liter < 0:
        raise ValueError("liters and discount_per_liter cannot be negative")
    if max_liters is not None and max_liters < 0:
        raise ValueError("max_liters cannot be negative")
    if discount_per_liter == 0 or liters == 0:
        return 0.0
    eligible_liters = min(liters, max_liters) if max_liters is not None else liters
    return discount_per_liter * eligible_liters


def calculate_detour_cost(
    extra_km: float,
    consumption_per_100km: float,
    fuel_price: float,
) -> float:
    """Compute fuel cost burned by taking the detour: extra_km * l/100km / 100 * price."""
    if extra_km < 0 or consumption_per_100km < 0 or fuel_price < 0:
        raise ValueError("extra_km, consumption_per_100km, and fuel_price cannot be negative")
    return (extra_km * consumption_per_100km / 100.0) * fuel_price


def calculate_min_liters(
    detour_cost: float,
    usual_price: float,
    target_pump_price: float,
    discount_per_liter: float = 0.0,
    max_liters: float | None = None,
) -> float | None:
    """Calculate minimum liters needed to break even, or None if detour never pays off."""
    if detour_cost < 0 or discount_per_liter < 0:
        raise ValueError("detour_cost and discount_per_liter cannot be negative")
    if max_liters is not None and max_liters < 0:
        raise ValueError("max_liters cannot be negative")

    has_discount = discount_per_liter > 0 and (max_liters is None or max_liters > 0)
    discounted_diff = usual_price - (
        target_pump_price - discount_per_liter if has_discount else target_pump_price
    )
    if discounted_diff <= 0:
        return None
    if detour_cost == 0:
        return 0.0

    liters_at_discounted_rate = detour_cost / discounted_diff
    if max_liters is None or liters_at_discounted_rate <= max_liters:
        return liters_at_discounted_rate

    # Beyond max_liters, only the un-discounted pump price difference contributes to savings.
    savings_within_cap = max_liters * discounted_diff
    remaining_detour_cost = detour_cost - savings_within_cap
    pump_diff = usual_price - target_pump_price
    if pump_diff <= 0:
        return None
    return max_liters + (remaining_detour_cost / pump_diff)


def evaluate_detour(
    extra_km: float,
    consumption_per_100km: float,
    liters: float,
    usual_price: float,
    target_pump_price: float,
    discount_per_liter: float = 0.0,
    max_liters: float | None = None,
) -> DetourResult:
    """Evaluate detour cost, savings with capped discount, net gain, and break-even liters."""
    if liters <= 0:
        raise ValueError("liters must be positive")
    if usual_price <= 0 or target_pump_price <= 0:
        raise ValueError("Fuel prices must be positive")

    total_discount = calculate_discount_amount(liters, discount_per_liter, max_liters)
    effective_price = target_pump_price - (total_discount / liters)

    # Use unit discounted price for detour_cost so break-even threshold does not depend on liters.
    has_discount = discount_per_liter > 0 and (max_liters is None or max_liters > 0)
    detour_fuel_price = (
        target_pump_price - discount_per_liter if has_discount else target_pump_price
    )
    detour_cost = calculate_detour_cost(extra_km, consumption_per_100km, detour_fuel_price)

    savings = liters * (usual_price - effective_price)
    net_gain = savings - detour_cost
    min_liters = calculate_min_liters(
        detour_cost=detour_cost,
        usual_price=usual_price,
        target_pump_price=target_pump_price,
        discount_per_liter=discount_per_liter,
        max_liters=max_liters,
    )

    return DetourResult(
        detour_cost=round(detour_cost, 2),
        savings=round(savings, 2),
        net_gain=round(net_gain, 2),
        min_liters=round(min_liters, 2) if min_liters is not None else None,
        effective_price_per_liter=round(effective_price, 4),
        is_profitable=net_gain > 0,
    )
