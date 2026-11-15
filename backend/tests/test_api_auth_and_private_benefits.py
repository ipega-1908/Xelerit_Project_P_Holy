import pytest
from fastapi.testclient import TestClient


def _benefit_payload(
    *,
    brand: str = "Orlen",
    app_name: str = "Mój prywatny kod Orlen",
    discount: float = 0.60,
    fuel_type: str | None = "PB95",
) -> dict[str, object]:
    return {
        "brand": brand,
        "app_name": app_name,
        "fuel_type": fuel_type,
        "discount_per_liter": discount,
        "max_liters": 50.0,
        "active_weekdays": None,
        "start_hour": None,
        "end_hour": None,
        "valid_from": "2026-10-01T00:00:00Z",
        "valid_to": "2027-06-01T00:00:00Z",
        "description": "Prywatny rabat flotowy użytkownika",
    }


def test_demo_user_login_and_registration(client: TestClient) -> None:
    # Seeded demo/demo account works immediately.
    login_resp = client.post("/auth/login", json={"username": "demo", "password": "demo"})
    assert login_resp.status_code == 200
    demo_data = login_resp.json()
    assert demo_data["username"] == "demo"
    assert demo_data["role"] == "user"
    assert isinstance(demo_data["user_id"], int)

    session_resp = client.get(
        "/auth/session",
        headers={"Authorization": f"Bearer {demo_data['access_token']}"},
    )
    assert session_resp.status_code == 200
    assert session_resp.json() == {
        "username": "demo",
        "role": "user",
        "user_id": demo_data["user_id"],
    }

    # Wrong password returns 401.
    assert (
        client.post("/auth/login", json={"username": "demo", "password": "bad"}).status_code == 401
    )

    # Duplicate registration returns 409.
    dup_resp = client.post("/auth/register", json={"username": "demo", "password": "demo"})
    assert dup_resp.status_code == 409

    # New registration succeeds and validates minimum length.
    assert (
        client.post("/auth/register", json={"username": "ab", "password": "123"}).status_code == 422
    )
    reg_resp = client.post("/auth/register", json={"username": "ania_gdansk", "password": "pass"})
    assert reg_resp.status_code == 201
    assert reg_resp.json()["username"] == "ania_gdansk"
    assert reg_resp.json()["role"] == "user"


def test_user_private_benefits_crud_isolation_and_deals(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")

    user_a = client.post("/auth/login", json={"username": "demo", "password": "demo"}).json()
    user_b = client.post(
        "/auth/register", json={"username": "kierowca2", "password": "tajne"}
    ).json()

    headers_a = {"Authorization": f"Bearer {user_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {user_b['access_token']}"}

    # Anonymous sees only global seeded benefits.
    anon_benefits = client.get("/benefits").json()
    assert all(b["owner_id"] is None and b["is_own"] is False for b in anon_benefits)
    global_benefit_id = anon_benefits[0]["id"]

    # User A creates a private benefit.
    created = client.post(
        "/benefits",
        json=_benefit_payload(discount=0.80, app_name="Karta Demo Flota"),
        headers=headers_a,
    )
    assert created.status_code == 201
    created_data = created.json()
    private_id = created_data["id"]
    assert created_data["owner_id"] == user_a["user_id"]
    assert created_data["is_own"] is True

    # User A sees it in /benefits, /stations and /deals (discount applied!).
    benefits_a = client.get("/benefits", headers=headers_a).json()
    assert any(b["id"] == private_id and b["is_own"] is True for b in benefits_a)

    stations_a = client.get("/stations", headers=headers_a).json()
    orlen_a = next(s for s in stations_a if s["brand"] == "Orlen")
    assert any(b["id"] == private_id for b in orlen_a["active_benefits"])

    deals_a = client.get(
        "/deals",
        params={
            "lat": 54.352,
            "lon": 18.6466,
            "fuel": "PB95",
            "liters": 40,
            "consumption": 7.5,
            "apps": ["Karta Demo Flota"],
        },
        headers=headers_a,
    ).json()
    applied_names_a = {
        d["applied_benefit"]["app_name"] for d in deals_a["deals"] if d["applied_benefit"]
    }
    assert "Karta Demo Flota" in applied_names_a

    # User B and anonymous do NOT see User A's private benefit anywhere.
    assert all(b["id"] != private_id for b in client.get("/benefits").json())
    assert all(b["id"] != private_id for b in client.get("/benefits", headers=headers_b).json())
    deals_b = client.get(
        "/deals",
        params={
            "lat": 54.352,
            "lon": 18.6466,
            "fuel": "PB95",
            "liters": 40,
            "consumption": 7.5,
            "apps": ["Karta Demo Flota"],
        },
        headers=headers_b,
    ).json()
    applied_names_b = {
        d["applied_benefit"]["app_name"] for d in deals_b["deals"] if d["applied_benefit"]
    }
    assert "Karta Demo Flota" not in applied_names_b

    # User B cannot read/edit/delete User A's benefit or global benefits -> 403.
    assert client.get(f"/benefits/{private_id}", headers=headers_b).status_code == 403
    assert (
        client.put(
            f"/benefits/{private_id}",
            json=_benefit_payload(discount=0.90),
            headers=headers_b,
        ).status_code
        == 403
    )
    assert client.delete(f"/benefits/{private_id}", headers=headers_b).status_code == 403
    assert (
        client.put(
            f"/benefits/{global_benefit_id}",
            json=_benefit_payload(),
            headers=headers_a,
        ).status_code
        == 403
    )
    assert client.delete(f"/benefits/{global_benefit_id}", headers=headers_a).status_code == 403

    # Regular user token CANNOT bypass admin protection on /stations/{id}.
    station_id = stations_a[0]["id"]
    assert client.delete(f"/stations/{station_id}", headers=headers_a).status_code == 403

    # User A can edit and delete their own private benefit.
    updated = client.put(
        f"/benefits/{private_id}",
        json=_benefit_payload(discount=0.95, app_name="Karta Demo VIP"),
        headers=headers_a,
    )
    assert updated.status_code == 200
    assert updated.json()["discount_per_liter"] == 0.95
    assert updated.json()["app_name"] == "Karta Demo VIP"

    assert client.delete(f"/benefits/{private_id}", headers=headers_a).status_code == 204
    assert all(b["id"] != private_id for b in client.get("/benefits", headers=headers_a).json())
