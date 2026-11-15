from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import PriceReport, PriceVote


def test_create_and_list_price_reports(client: TestClient) -> None:
    station = client.get("/stations").json()[0]
    station_id = station["id"]

    # Missing X-User-Id header must be rejected.
    missing_header = client.post(
        f"/stations/{station_id}/price-reports",
        json={"fuel_type": "PB95", "price": 6.45},
    )
    assert missing_header.status_code == 422

    # Price out of [3.00, 15.00] returns 422.
    invalid_price = client.post(
        f"/stations/{station_id}/price-reports",
        json={"fuel_type": "PB95", "price": 2.50},
        headers={"X-User-Id": "driver-a"},
    )
    assert invalid_price.status_code == 422

    created = client.post(
        f"/stations/{station_id}/price-reports",
        json={"fuel_type": "PB95", "price": 6.33},
        headers={"X-User-Id": "driver-a"},
    )
    assert created.status_code == 201
    assert created.json()["price"] == 6.33
    assert created.json()["reported_at"] == "2026-11-15T12:00:00Z"

    history = client.get(f"/stations/{station_id}/price-reports", params={"fuel_type": "PB95"})
    assert history.status_code == 200
    assert len(history.json()) >= 2
    assert history.json()[0]["id"] == created.json()["id"]


def test_confirmations_and_double_vote_returns_409(client: TestClient) -> None:
    station_id = client.get("/stations").json()[0]["id"]
    report_resp = client.post(
        f"/stations/{station_id}/price-reports",
        json={"fuel_type": "ON", "price": 6.51},
        headers={"X-User-Id": "author-1"},
    )
    assert report_resp.status_code == 201
    report_id = report_resp.json()["id"]

    # Author cannot confirm own report.
    self_confirm = client.post(
        f"/price-reports/{report_id}/confirmations",
        headers={"X-User-Id": "author-1"},
    )
    assert self_confirm.status_code == 409

    # Different user confirms -> 201.
    first_confirm = client.post(
        f"/price-reports/{report_id}/confirmations",
        headers={"X-User-Id": "driver-b"},
    )
    assert first_confirm.status_code == 201

    # Same user voting again -> 409 Conflict.
    second_confirm = client.post(
        f"/price-reports/{report_id}/confirmations",
        headers={"X-User-Id": "driver-b"},
    )
    assert second_confirm.status_code == 409


def test_correction_validation_and_atomicity(client: TestClient, session: Session) -> None:
    station_id = client.get("/stations").json()[0]["id"]
    report_resp = client.post(
        f"/stations/{station_id}/price-reports",
        json={"fuel_type": "PB95", "price": 6.40},
        headers={"X-User-Id": "author-1"},
    )
    report_id = report_resp.json()["id"]

    # Identical price correction must return 422.
    same_price = client.post(
        f"/price-reports/{report_id}/corrections",
        json={"price": 6.40},
        headers={"X-User-Id": "driver-c"},
    )
    assert same_price.status_code == 422

    # Valid correction creates reject vote + new report in one transaction.
    correction = client.post(
        f"/price-reports/{report_id}/corrections",
        json={"price": 6.55},
        headers={"X-User-Id": "driver-c"},
    )
    assert correction.status_code == 201
    body = correction.json()
    assert body["rejected_report_id"] == report_id
    assert body["vote"]["vote_type"] == "reject"
    assert body["new_report"]["price"] == 6.55
    assert body["new_report"]["confirmations_count"] == 0

    # Same user cannot correct or vote on the same report twice.
    duplicate = client.post(
        f"/price-reports/{report_id}/corrections",
        json={"price": 6.60},
        headers={"X-User-Id": "driver-c"},
    )
    assert duplicate.status_code == 409

    # Verify atomicity: if voting fails due to conflict, neither vote nor report persists.
    reports_before = len(session.exec(select(PriceReport)).all())
    votes_before = len(session.exec(select(PriceVote)).all())

    # Simulate already-voted user trying to inject via confirmation then correction.
    assert (
        client.post(
            f"/price-reports/{report_id}/confirmations",
            headers={"X-User-Id": "driver-d"},
        ).status_code
        == 201
    )
    failed_correction = client.post(
        f"/price-reports/{report_id}/corrections",
        json={"price": 6.65},
        headers={"X-User-Id": "driver-d"},
    )
    assert failed_correction.status_code == 409

    assert len(session.exec(select(PriceReport)).all()) == reports_before
    assert len(session.exec(select(PriceVote)).all()) == votes_before + 1


def test_photo_sourced_report_updates_station_price_to_verified_and_can_be_corrected(
    client: TestClient,
) -> None:
    stations = client.get("/stations").json()
    station_id = stations[0]["id"]

    created = client.post(
        f"/stations/{station_id}/price-reports",
        json={"fuel_type": "PB95", "price": 6.89, "source": "photo"},
        headers={"X-User-Id": "photo-driver"},
    )
    assert created.status_code == 201
    report_body = created.json()
    assert report_body["source"] == "photo"

    station_after = client.get(f"/stations/{station_id}").json()
    assert station_after["prices"]["PB95"]["price"] == 6.89
    assert station_after["prices"]["PB95"]["status"] == "verified"

    # Rejecting with correction revokes photo trust and lets the corrected/existing consensus win.
    correction = client.post(
        f"/price-reports/{report_body['id']}/corrections",
        json={"price": 6.45},
        headers={"X-User-Id": "reviewer-1"},
    )
    assert correction.status_code == 201

    station_reverted = client.get(f"/stations/{station_id}").json()
    assert station_reverted["prices"]["PB95"]["price"] != 6.89
