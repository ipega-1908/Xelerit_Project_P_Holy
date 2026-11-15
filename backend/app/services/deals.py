from datetime import datetime

from sqlmodel import Session, select

from app.domain.benefits import ensure_utc, select_best_benefit
from app.domain.calculator import calculate_discount_amount, evaluate_detour
from app.domain.consensus import SUPPORTED_FUEL_TYPES, PriceStatus
from app.domain.distance import calculate_extra_km, estimated_road_distance_km
from app.models import PriceReport, PriceVote, Station
from app.schemas import DealItemRead, DealsResponse, FuelTypeLiteral, StationRead
from app.services.pricing import (
    benefit_to_rule,
    get_active_benefits_for_brand,
    list_visible_benefits,
    resolution_to_summary,
    resolve_all_station_prices,
)

WARNING_MESSAGES: dict[PriceStatus, str] = {
    PriceStatus.SUSPICIOUS: (
        "Cena odbiega o ponad 1,00 zł od mediany w okolicy i nie została jeszcze potwierdzona."
    ),
    PriceStatus.EXPIRED: ("Ostatnie zgłoszenie ma ponad 3 dni — cena może być już nieaktualna."),
    PriceStatus.UNCONFIRMED: (
        "Cena pochodzi z pojedynczego źródła i czeka na dodatkowe potwierdzenie."
    ),
}


def parse_apps_param(apps: list[str] | None) -> list[str]:
    """Support both repeated ?apps=A&apps=B and comma-separated ?apps=A,B query params."""
    if not apps:
        return []
    parsed: list[str] = []
    for item in apps:
        for part in item.split(","):
            cleaned = part.strip()
            if cleaned:
                parsed.append(cleaned)
    return parsed


def calculate_deals(
    *,
    lat: float,
    lon: float,
    fuel_type: FuelTypeLiteral,
    liters: float,
    consumption_per_100km: float,
    user_apps: list[str],
    session: Session,
    now: datetime,
    viewer_user_id: int | None = None,
) -> DealsResponse:
    """Rank fuel stations by detour net gain relative to the nearest station with fuel price."""
    stations = list(session.exec(select(Station)).all())
    reports = list(session.exec(select(PriceReport)).all())
    votes = list(session.exec(select(PriceVote)).all())
    benefits = list_visible_benefits(session, viewer_user_id)

    resolutions = resolve_all_station_prices(stations, reports, votes, now)
    benefit_rules = [benefit_to_rule(b) for b in benefits]
    benefit_by_id = {b.id: b for b in benefits if b.id is not None}

    candidates: list[tuple[Station, float]] = []
    for station in stations:
        assert station.id is not None
        res = resolutions[station.id][fuel_type]
        if res.price is None:
            continue
        dist_km = estimated_road_distance_km(lat, lon, station.latitude, station.longitude)
        candidates.append((station, dist_km))

    if not candidates:
        return DealsResponse(
            fuel_type=fuel_type,
            liters=liters,
            consumption_per_100km=consumption_per_100km,
            reference_station_id=None,
            reference_station_name=None,
            reference_price=None,
            deals=[],
        )

    ref_station, ref_distance_km = min(candidates, key=lambda pair: pair[1])
    assert ref_station.id is not None
    ref_res = resolutions[ref_station.id][fuel_type]
    assert ref_res.price is not None

    ref_benefit = select_best_benefit(
        rules=benefit_rules,
        brand=ref_station.brand,
        fuel_type=fuel_type,
        user_apps=user_apps,
        liters=liters,
        now=now,
    )
    ref_discount_total = (
        calculate_discount_amount(
            liters=liters,
            discount_per_liter=ref_benefit.discount_per_liter,
            max_liters=ref_benefit.max_liters,
        )
        if ref_benefit is not None
        else 0.0
    )
    ref_effective_price = ref_res.price - (ref_discount_total / liters)

    deals: list[DealItemRead] = []
    for station, dist_km in candidates:
        assert station.id is not None
        station_res_map = resolutions[station.id]
        res = station_res_map[fuel_type]
        assert res.price is not None

        best_benefit = select_best_benefit(
            rules=benefit_rules,
            brand=station.brand,
            fuel_type=fuel_type,
            user_apps=user_apps,
            liters=liters,
            now=now,
        )
        discount_per_liter = best_benefit.discount_per_liter if best_benefit else 0.0
        max_liters = best_benefit.max_liters if best_benefit else None
        total_discount = calculate_discount_amount(liters, discount_per_liter, max_liters)

        extra_km = calculate_extra_km(dist_km, ref_distance_km)
        detour = evaluate_detour(
            extra_km=extra_km,
            consumption_per_100km=consumption_per_100km,
            liters=liters,
            usual_price=ref_effective_price,
            target_pump_price=res.price,
            discount_per_liter=discount_per_liter,
            max_liters=max_liters,
        )

        active_benefits = get_active_benefits_for_brand(
            benefits,
            station.brand,
            now,
            viewer_user_id=viewer_user_id,
        )
        applied_benefit_read = None
        if best_benefit is not None and best_benefit.benefit_id in benefit_by_id:
            applied_benefit_read = next(
                (b for b in active_benefits if b.id == best_benefit.benefit_id),
                None,
            )

        station_read = StationRead(
            id=station.id,
            name=station.name,
            brand=station.brand,
            address=station.address,
            district=station.district,
            latitude=station.latitude,
            longitude=station.longitude,
            created_at=ensure_utc(station.created_at),
            prices={
                fuel: resolution_to_summary(fuel, station_res_map[fuel])
                for fuel in SUPPORTED_FUEL_TYPES
            },  # type: ignore[arg-type]
            active_benefits=active_benefits,
        )

        deals.append(
            DealItemRead(
                station=station_read,
                fuel_type=fuel_type,
                pump_price=res.price,
                effective_price_per_liter=round(detour.effective_price_per_liter, 2),
                applied_benefit=applied_benefit_read,
                total_discount=round(total_discount, 2),
                distance_km=round(dist_km, 2),
                extra_km=round(extra_km, 2),
                detour_cost=detour.detour_cost,
                savings=detour.savings,
                net_gain=detour.net_gain,
                min_liters=detour.min_liters,
                is_profitable=detour.is_profitable,
                is_reference_station=(station.id == ref_station.id),
                price_status=res.status,
                price_age_hours=res.age_hours,
                needs_warning=res.needs_warning,
                warning_message=WARNING_MESSAGES.get(res.status),
            )
        )

    deals.sort(
        key=lambda item: (
            -item.net_gain,
            item.effective_price_per_liter,
            item.distance_km,
        )
    )

    return DealsResponse(
        fuel_type=fuel_type,
        liters=liters,
        consumption_per_100km=consumption_per_100km,
        reference_station_id=ref_station.id,
        reference_station_name=ref_station.name,
        reference_price=round(ref_effective_price, 2),
        deals=deals,
    )
