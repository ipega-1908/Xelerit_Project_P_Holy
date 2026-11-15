import pytest
from fastapi.testclient import TestClient


def _login_admin(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setenv("ADMIN_USERNAME", "test-admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-pass-123")
    resp = client.post(
        "/admin/login",
        json={"username": "test-admin", "password": "test-pass-123"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_and_get_stations_includes_resolved_prices_and_benefits(
    client: TestClient,
) -> None:
    response = client.get("/stations")
    assert response.status_code == 200
    stations = response.json()
    assert len(stations) == 14

    first = stations[0]
    assert set(first["prices"].keys()) == {"PB95", "PB98", "ON", "LPG"}

    # Moya Orunia LPG was seeded 100h old -> status must be expired.
    moya_orunia = next(s for s in stations if s["name"] == "Moya Gdańsk Orunia")
    assert moya_orunia["prices"]["LPG"]["status"] == "expired"
    assert moya_orunia["prices"]["LPG"]["needs_warning"] is True

    # On Sunday 12:00 UTC (13:00 Warsaw), Orlen's weekend Vitay benefit is active.
    orlen = next(s for s in stations if s["brand"] == "Orlen")
    assert len(orlen["active_benefits"]) == 1
    assert orlen["active_benefits"][0]["app_name"] == "Orlen Vitay"
    assert orlen["active_benefits"][0]["discount_per_liter"] == 0.35

    detail = client.get(f"/stations/{orlen['id']}")
    assert detail.status_code == 200
    assert detail.json()["name"] == orlen["name"]

    missing = client.get("/stations/99999")
    assert missing.status_code == 404


def test_stations_crud_lifecycle(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_headers = _login_admin(client, monkeypatch)
    create_payload = {
        "name": "Lotos Gdańsk Stogi",
        "brand": "Mol",
        "address": "ul. Stryjewskiego 12",
        "district": "Stogi",
        "latitude": 54.3652,
        "longitude": 18.7041,
    }
    created = client.post("/stations", json=create_payload)
    assert created.status_code == 201
    station_id = created.json()["id"]
    assert created.json()["prices"]["PB95"]["status"] == "unknown"

    update_payload = {**create_payload, "name": "MOL Gdańsk Stogi"}
    updated = client.put(
        f"/stations/{station_id}",
        json=update_payload,
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "MOL Gdańsk Stogi"

    deleted = client.delete(f"/stations/{station_id}", headers=admin_headers)
    assert deleted.status_code == 204
    assert client.get(f"/stations/{station_id}").status_code == 404

    # Deleting a seeded station with reports & votes must cascade cleanly.
    seeded_id = client.get("/stations").json()[0]["id"]
    assert client.delete(f"/stations/{seeded_id}", headers=admin_headers).status_code == 204


def test_station_validation_returns_422(client: TestClient) -> None:
    invalid_payload = {
        "name": "",
        "brand": "Orlen",
        "address": "ul. Testowa 1",
        "district": "Wrzeszcz",
        "latitude": 120.0,  # out of [-90, 90]
        "longitude": 18.6,
    }
    response = client.post("/stations", json=invalid_payload)
    assert response.status_code == 422


def test_benefits_crud_and_validation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_headers = _login_admin(client, monkeypatch)
    list_resp = client.get("/benefits")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 5

    create_payload = {
        "brand": "Amic",
        "app_name": "Amic Club",
        "fuel_type": "PB95",
        "discount_per_liter": 0.25,
        "max_liters": 40.0,
        "active_weekdays": [2, 3],
        "start_hour": 10,
        "end_hour": 18,
        "valid_from": "2026-11-01T00:00:00Z",
        "valid_to": "2026-12-31T23:59:59Z",
        "description": "Rabat środowo-czwartkowy",
    }
    created = client.post("/benefits", json=create_payload, headers=admin_headers)
    assert created.status_code == 201
    benefit_id = created.json()["id"]
    assert created.json()["active_weekdays"] == [2, 3]
    assert created.json()["checked_at"] == "2026-11-15T12:00:00Z"

    detail = client.get(f"/benefits/{benefit_id}")
    assert detail.status_code == 200

    updated = client.put(
        f"/benefits/{benefit_id}",
        json={**create_payload, "discount_per_liter": 0.35},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["discount_per_liter"] == 0.35

    deleted = client.delete(f"/benefits/{benefit_id}", headers=admin_headers)
    assert deleted.status_code == 204
    assert client.get(f"/benefits/{benefit_id}").status_code == 404

    invalid_dates = {
        **create_payload,
        "valid_from": "2026-12-31T00:00:00Z",
        "valid_to": "2026-11-01T00:00:00Z",
    }
    assert client.post("/benefits", json=invalid_dates, headers=admin_headers).status_code == 422
