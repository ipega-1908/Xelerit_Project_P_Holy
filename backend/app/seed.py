from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from app.domain.auth import hash_password
from app.domain.consensus import VoteType
from app.models import Benefit, PriceReport, PriceVote, Station, User

SEED_STATIONS: list[dict[str, object]] = [
    {
        "name": "Orlen Gdańsk Śródmieście",
        "brand": "Orlen",
        "address": "al. Zwycięstwa 14",
        "district": "Śródmieście",
        "latitude": 54.3612,
        "longitude": 18.6415,
    },
    {
        "name": "Orlen Gdańsk Wrzeszcz",
        "brand": "Orlen",
        "address": "al. Grunwaldzka 141",
        "district": "Wrzeszcz",
        "latitude": 54.3821,
        "longitude": 18.6085,
    },
    {
        "name": "Orlen Gdańsk Oliwa",
        "brand": "Orlen",
        "address": "al. Grunwaldzka 472",
        "district": "Oliwa",
        "latitude": 54.4038,
        "longitude": 18.5724,
    },
    {
        "name": "BP Gdańsk Zaspa",
        "brand": "BP",
        "address": "al. Rzeczypospolitej 33",
        "district": "Zaspa",
        "latitude": 54.3955,
        "longitude": 18.6022,
    },
    {
        "name": "BP Gdańsk Morena",
        "brand": "BP",
        "address": "ul. Piecewska 31",
        "district": "Piecki-Migowo",
        "latitude": 54.3547,
        "longitude": 18.5903,
    },
    {
        "name": "BP Gdańsk Chełm",
        "brand": "BP",
        "address": "ul. Cienista 15",
        "district": "Chełm",
        "latitude": 54.3368,
        "longitude": 18.6132,
    },
    {
        "name": "Circle K Gdańsk Wrzeszcz",
        "brand": "Circle K",
        "address": "al. gen. Józefa Hallera 132",
        "district": "Wrzeszcz",
        "latitude": 54.3915,
        "longitude": 18.6258,
    },
    {
        "name": "Circle K Gdańsk Przymorze",
        "brand": "Circle K",
        "address": "ul. Chłopska 36",
        "district": "Przymorze",
        "latitude": 54.4079,
        "longitude": 18.5944,
    },
    {
        "name": "Circle K Gdańsk Jasień",
        "brand": "Circle K",
        "address": "ul. Jabłoniowa 55",
        "district": "Jasień",
        "latitude": 54.3425,
        "longitude": 18.5572,
    },
    {
        "name": "Shell Gdańsk Siedlce",
        "brand": "Shell",
        "address": "ul. Kartuska 65",
        "district": "Siedlce",
        "latitude": 54.3489,
        "longitude": 18.6214,
    },
    {
        "name": "Shell Gdańsk Przymorze",
        "brand": "Shell",
        "address": "al. Rzeczypospolitej 11",
        "district": "Przymorze",
        "latitude": 54.3992,
        "longitude": 18.5982,
    },
    {
        "name": "Moya Gdańsk Osowa",
        "brand": "Moya",
        "address": "ul. Spacerowa 50",
        "district": "Osowa",
        "latitude": 54.4263,
        "longitude": 18.4875,
    },
    {
        "name": "Moya Gdańsk Orunia",
        "brand": "Moya",
        "address": "Trakt św. Wojciecha 215",
        "district": "Orunia",
        "latitude": 54.3186,
        "longitude": 18.6411,
    },
    {
        "name": "Auchan Gdańsk Szczęśliwa",
        "brand": "Auchan",
        "address": "ul. Szczęśliwa 3",
        "district": "Matarnia",
        "latitude": 54.3456,
        "longitude": 18.5284,
    },
]

# Sample prices (PLN/L) per station index for demo purposes only.
_SAMPLE_PRICES: list[dict[str, float]] = [
    {"PB95": 6.49, "PB98": 7.19, "ON": 6.59, "LPG": 3.09},  # Orlen Srodmiescie
    {"PB95": 6.45, "PB98": 7.15, "ON": 6.55, "LPG": 3.05},  # Orlen Wrzeszcz
    {"PB95": 6.42, "PB98": 7.12, "ON": 6.52, "LPG": 3.04},  # Orlen Oliwa
    {"PB95": 6.47, "PB98": 7.18, "ON": 6.57, "LPG": 3.08},  # BP Zaspa
    {"PB95": 6.44, "PB98": 7.14, "ON": 6.54, "LPG": 3.06},  # BP Morena
    {"PB95": 6.39, "PB98": 7.09, "ON": 6.49, "LPG": 3.02},  # BP Chelm
    {"PB95": 6.52, "PB98": 7.22, "ON": 6.62, "LPG": 3.12},  # Circle K Wrzeszcz
    {"PB95": 6.48, "PB98": 7.17, "ON": 6.58, "LPG": 3.09},  # Circle K Przymorze
    {"PB95": 6.35, "PB98": 7.05, "ON": 6.45, "LPG": 3.01},  # Circle K Jasien
    {"PB95": 6.51, "PB98": 7.21, "ON": 6.61, "LPG": 3.11},  # Shell Siedlce
    {"PB95": 6.46, "PB98": 7.16, "ON": 6.56, "LPG": 3.07},  # Shell Przymorze
    {"PB95": 6.29, "PB98": 6.99, "ON": 6.39, "LPG": 3.01},  # Moya Osowa
    {"PB95": 6.27, "PB98": 6.97, "ON": 6.37, "LPG": 3.00},  # Moya Orunia
    {"PB95": 6.09, "PB98": 6.79, "ON": 6.19, "LPG": 3.00},  # Auchan Szczesliwa (cheapest!)
]


def _ensure_demo_user(session: Session, now: datetime) -> None:
    """Create default demo driver account (demo/demo) if not present yet."""
    existing_user = session.exec(select(User).where(User.username == "demo")).first()
    if existing_user is None:
        session.add(
            User(
                username="demo",
                password_hash=hash_password("demo"),
                created_at=now,
            )
        )
        session.commit()


def seed_database(session: Session, now: datetime | None = None) -> bool:
    """Populate Gdansk stations, sample prices, votes, and app benefits if DB is empty."""
    base_now = now if now is not None else datetime.now(UTC)
    _ensure_demo_user(session, base_now)

    existing = session.exec(select(Station)).first()
    if existing is not None:
        return False

    stations: list[Station] = []
    for item in SEED_STATIONS:
        station = Station(
            name=str(item["name"]),
            brand=str(item["brand"]),
            address=str(item["address"]),
            district=str(item["district"]),
            latitude=float(item["latitude"]),  # type: ignore[arg-type]
            longitude=float(item["longitude"]),  # type: ignore[arg-type]
            created_at=base_now - timedelta(days=30),
        )
        session.add(station)
        stations.append(station)

    session.flush()  # Assign primary keys before inserting reports.

    for idx, station in enumerate(stations):
        assert station.id is not None
        prices = _SAMPLE_PRICES[idx]
        for fuel_idx, (fuel_type, price) in enumerate(prices.items()):
            # Make Moya Orunia (idx=12) LPG expired (> 4 days old) to showcase warning state.
            age_hours = 100 if (idx == 12 and fuel_type == "LPG") else (2 + idx + fuel_idx)
            report = PriceReport(
                station_id=station.id,
                fuel_type=fuel_type,
                price=price,
                user_id=f"seed-user-{(idx % 3) + 1}",
                reported_at=base_now - timedelta(hours=age_hours),
            )
            session.add(report)
            session.flush()
            assert report.id is not None

            # Verify first 10 stations so the UI displays a mix of verified and unconfirmed prices.
            if idx < 10:
                vote = PriceVote(
                    report_id=report.id,
                    user_id=f"seed-verifier-{(idx % 2) + 1}",
                    vote_type=VoteType.CONFIRM.value,
                    created_at=base_now - timedelta(hours=max(1, age_hours - 1)),
                )
                session.add(vote)

    valid_from = base_now - timedelta(days=30)
    valid_to = base_now + timedelta(days=180)
    checked_at = base_now - timedelta(days=1)

    benefits = [
        Benefit(
            brand="Orlen",
            app_name="Orlen Vitay",
            fuel_type=None,
            discount_per_liter=0.35,
            max_liters=50.0,
            active_weekdays="4,5,6",
            valid_from=valid_from,
            valid_to=valid_to,
            checked_at=checked_at,
            description="Weekendowy rabat Vitay (pt-nd), limit 50 l",
        ),
        Benefit(
            brand="Orlen",
            app_name="Orlen Vitay",
            fuel_type=None,
            discount_per_liter=0.20,
            max_liters=50.0,
            active_weekdays="0,1,2,3",
            valid_from=valid_from,
            valid_to=valid_to,
            checked_at=checked_at,
            description="Rabat Vitay w dni robocze (pn-czw), limit 50 l",
        ),
        Benefit(
            brand="BP",
            app_name="BPme",
            fuel_type=None,
            discount_per_liter=0.30,
            max_liters=60.0,
            active_weekdays=None,
            valid_from=valid_from,
            valid_to=valid_to,
            checked_at=checked_at,
            description="Stały rabat w aplikacji BPme, limit 60 l",
        ),
        Benefit(
            brand="Circle K",
            app_name="Circle K EXTRA",
            fuel_type=None,
            discount_per_liter=0.25,
            max_liters=50.0,
            active_weekdays=None,
            valid_from=valid_from,
            valid_to=valid_to,
            checked_at=checked_at,
            description="Rabat z kartą Circle K EXTRA, limit 50 l",
        ),
        Benefit(
            brand="Shell",
            app_name="Shell ClubSmart",
            fuel_type=None,
            discount_per_liter=0.30,
            max_liters=50.0,
            active_weekdays=None,
            start_hour=15,
            end_hour=20,
            valid_from=valid_from,
            valid_to=valid_to,
            checked_at=checked_at,
            description="Popołudniowy rabat Shell ClubSmart (15:00-20:00), limit 50 l",
        ),
        Benefit(
            brand="Moya",
            app_name="Super MOYA",
            fuel_type=None,
            discount_per_liter=0.25,
            max_liters=50.0,
            active_weekdays=None,
            valid_from=valid_from,
            valid_to=valid_to,
            checked_at=checked_at,
            description="Rabat w aplikacji Super MOYA, limit 50 l",
        ),
    ]
    session.add_all(benefits)
    session.commit()
    return True
