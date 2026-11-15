import pytest
from fastapi.testclient import TestClient


def test_admin_login_503_when_credentials_missing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    response = client.post(
        "/admin/login",
        json={"username": "admin", "password": "secret"},
    )
    assert response.status_code == 503


def test_admin_login_session_and_protected_endpoints(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADMIN_USERNAME", "boss")
    monkeypatch.setenv("ADMIN_PASSWORD", "tajne-haslo")

    # Wrong password -> 401
    bad_login = client.post(
        "/admin/login",
        json={"username": "boss", "password": "wrong"},
    )
    assert bad_login.status_code == 401

    # Valid credentials -> bearer token
    good_login = client.post(
        "/admin/login",
        json={"username": "boss", "password": "tajne-haslo"},
    )
    assert good_login.status_code == 200
    token = good_login.json()["access_token"]
    assert good_login.json()["username"] == "boss"

    # Session check works with valid token and fails without it.
    assert client.get("/admin/session").status_code == 401
    session_resp = client.get(
        "/admin/session",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert session_resp.status_code == 200
    assert session_resp.json() == {"username": "boss", "is_admin": True}

    # Regular user CAN still create a new station without admin token.
    station_payload = {
        "name": "Nowa Stacja Kierowcy",
        "brand": "Orlen",
        "address": "ul. Kartuska 10",
        "district": "Siedlce",
        "latitude": 54.35,
        "longitude": 18.61,
    }
    created = client.post("/stations", json=station_payload)
    assert created.status_code == 201
    station_id = created.json()["id"]

    # Regular user CANNOT edit or delete stations or modify benefits.
    assert client.put(f"/stations/{station_id}", json=station_payload).status_code == 401
    assert client.delete(f"/stations/{station_id}").status_code == 401

    benefit_payload = {
        "brand": "Orlen",
        "app_name": "Orlen Vitay",
        "fuel_type": "PB95",
        "discount_per_liter": 0.20,
        "valid_from": "2026-11-01T00:00:00Z",
        "valid_to": "2026-12-31T23:59:59Z",
    }
    assert client.post("/benefits", json=benefit_payload).status_code == 401
    existing_benefit_id = client.get("/benefits").json()[0]["id"]
    assert client.put(f"/benefits/{existing_benefit_id}", json=benefit_payload).status_code == 401
    assert client.delete(f"/benefits/{existing_benefit_id}").status_code == 401

    # With admin bearer token, station delete succeeds.
    admin_headers = {"Authorization": f"Bearer {token}"}
    assert client.delete(f"/stations/{station_id}", headers=admin_headers).status_code == 204
