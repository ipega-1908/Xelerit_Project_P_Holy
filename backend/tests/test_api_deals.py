from fastapi.testclient import TestClient


def test_deals_ranking_without_and_with_apps(client: TestClient) -> None:
    # Start point: Gdansk Srodmiescie (near Orlen Srodmiescie)
    params_no_apps = {
        "lat": 54.3610,
        "lon": 18.6410,
        "fuel": "PB95",
        "liters": 50.0,
        "consumption": 7.0,
    }
    resp_no_apps = client.get("/deals", params=params_no_apps)
    assert resp_no_apps.status_code == 200
    data = resp_no_apps.json()

    assert data["reference_station_name"] == "Orlen Gdańsk Śródmieście"
    assert data["reference_price"] == 6.49
    assert len(data["deals"]) == 14

    # Deals must be sorted by net_gain descending.
    net_gains = [d["net_gain"] for d in data["deals"]]
    assert net_gains == sorted(net_gains, reverse=True)

    # Auchan Szczesliwa (6.09 PLN) should yield a profitable detour for 50 L vs 6.49 PLN.
    auchan = next(d for d in data["deals"] if d["station"]["brand"] == "Auchan")
    assert auchan["is_profitable"] is True
    assert auchan["net_gain"] > 0
    assert auchan["applied_benefit"] is None

    # With Orlen Vitay active on Sunday (0.35 PLN/L off at nearest Orlen -> ref becomes 6.14 PLN),
    # Orlen's effective price drops and Auchan's relative advantage shrinks!
    resp_with_vitay = client.get(
        "/deals",
        params={**params_no_apps, "apps": "Orlen Vitay"},
    )
    assert resp_with_vitay.status_code == 200
    vitay_data = resp_with_vitay.json()
    assert vitay_data["reference_price"] == 6.14

    orlen_deal = next(
        d for d in vitay_data["deals"] if d["station"]["name"] == "Orlen Gdańsk Śródmieście"
    )
    assert orlen_deal["applied_benefit"]["app_name"] == "Orlen Vitay"
    assert orlen_deal["effective_price_per_liter"] == 6.14
    assert orlen_deal["extra_km"] == 0.0


def test_deals_flags_expired_and_suspicious_prices(client: TestClient) -> None:
    # Moya Orunia has an expired LPG report in seed data.
    lpg_resp = client.get(
        "/deals",
        params={
            "lat": 54.3520,
            "lon": 18.6466,
            "fuel": "LPG",
            "liters": 35.0,
            "consumption": 9.0,
        },
    )
    assert lpg_resp.status_code == 200
    moya_orunia = next(
        d for d in lpg_resp.json()["deals"] if d["station"]["name"] == "Moya Gdańsk Orunia"
    )
    assert moya_orunia["price_status"] == "expired"
    assert moya_orunia["needs_warning"] is True
    assert moya_orunia["warning_message"] is not None

    # Submit a suspiciously low PB95 price (3.50 PLN) on one station -> warning flagged.
    stations = client.get("/stations").json()
    target_station = next(s for s in stations if s["brand"] == "BP")
    # Reject existing report and submit 3.50 PLN as new price? Or add station with 3.50 PLN.
    new_station = client.post(
        "/stations",
        json={
            "name": "Test Podejrzana Stacja",
            "brand": "Test",
            "address": "ul. Testowa 1",
            "district": "Wrzeszcz",
            "latitude": target_station["latitude"],
            "longitude": target_station["longitude"],
        },
    ).json()
    client.post(
        f"/stations/{new_station['id']}/price-reports",
        json={"fuel_type": "PB95", "price": 3.50},
        headers={"X-User-Id": "outlier-reporter"},
    )

    pb95_deals = client.get(
        "/deals",
        params={"lat": 54.3520, "lon": 18.6466, "fuel": "PB95", "liters": 40.0},
    ).json()["deals"]
    suspect = next(d for d in pb95_deals if d["station"]["id"] == new_station["id"])
    assert suspect["price_status"] == "suspicious"
    assert suspect["needs_warning"] is True
    assert suspect["warning_message"] is not None


def test_deals_validation_returns_422(client: TestClient) -> None:
    assert (
        client.get(
            "/deals",
            params={"lat": 54.35, "lon": 18.64, "fuel": "DIESEL", "liters": 40},
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/deals",
            params={"lat": 54.35, "lon": 18.64, "fuel": "PB95", "liters": 0},
        ).status_code
        == 422
    )
