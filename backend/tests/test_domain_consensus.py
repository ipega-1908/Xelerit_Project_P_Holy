from datetime import UTC, datetime, timedelta

import pytest

from app.domain.consensus import (
    PriceStatus,
    ReportRecord,
    ReportSource,
    VoteRecord,
    VoteType,
    resolve_current_price,
    validate_correction,
    validate_price_range,
)


def test_validate_price_range_and_correction() -> None:
    validate_price_range(3.00)
    validate_price_range(15.00)

    with pytest.raises(ValueError):
        validate_price_range(2.99)
    with pytest.raises(ValueError):
        validate_price_range(15.01)

    validate_correction(previous_price=6.40, new_price=6.55)
    with pytest.raises(ValueError):
        validate_correction(previous_price=6.40, new_price=6.40)
    with pytest.raises(ValueError):
        validate_correction(previous_price=6.40, new_price=16.00)


def test_single_report_is_trusted_as_unconfirmed() -> None:
    now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    reports = [
        ReportRecord(
            report_id=1,
            price=6.39,
            user_id="user-1",
            reported_at=now - timedelta(hours=2),
        )
    ]

    res = resolve_current_price(reports=reports, votes=[], now=now)
    assert res.price == 6.39
    assert res.status == PriceStatus.UNCONFIRMED
    assert res.support == 1
    assert res.confirmations_count == 0
    assert res.age_hours == 2.0


def test_price_increase_wins_after_rejections() -> None:
    now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    # Old price 6.20 had support 2 (user-1 reported, user-2 confirmed).
    # Price increases to 6.55: user-3 and user-4 reject 6.20 and report/confirm 6.55.
    reports = [
        ReportRecord(1, 6.20, "user-1", now - timedelta(hours=10)),
        ReportRecord(2, 6.55, "user-3", now - timedelta(hours=1)),
    ]
    votes = [
        VoteRecord(1, "user-2", VoteType.CONFIRM, now - timedelta(hours=9)),
        VoteRecord(1, "user-3", VoteType.REJECT, now - timedelta(hours=1)),
        VoteRecord(1, "user-4", VoteType.REJECT, now - timedelta(minutes=45)),
        VoteRecord(2, "user-4", VoteType.CONFIRM, now - timedelta(minutes=45)),
    ]

    res = resolve_current_price(reports=reports, votes=votes, now=now)
    # 6.20 support = 2 - 2 = 0; 6.55 support = 2 -> 6.55 wins and is verified.
    assert res.price == 6.55
    assert res.status == PriceStatus.VERIFIED
    assert res.support == 2
    assert res.confirmations_count == 1


def test_tie_is_broken_by_newer_report() -> None:
    now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    reports = [
        ReportRecord(1, 6.20, "user-1", now - timedelta(hours=5)),
        ReportRecord(2, 6.50, "user-2", now - timedelta(hours=1)),
    ]
    # Both have support = 1 -> newer price (6.50) must win.
    res = resolve_current_price(reports=reports, votes=[], now=now)
    assert res.price == 6.50
    assert res.winning_report_id == 2


def test_same_user_double_voting_and_self_confirmation_ignored() -> None:
    now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    reports = [
        ReportRecord(1, 6.30, "user-1", now - timedelta(hours=3)),
        ReportRecord(2, 6.30, "user-1", now - timedelta(hours=2)),
    ]
    votes = [
        # Author tries to confirm own report -> must be ignored.
        VoteRecord(1, "user-1", VoteType.CONFIRM, now - timedelta(hours=2)),
        # user-2 confirms both reports at 6.30 -> counts only as 1 distinct user.
        VoteRecord(1, "user-2", VoteType.CONFIRM, now - timedelta(hours=1)),
        VoteRecord(2, "user-2", VoteType.CONFIRM, now - timedelta(minutes=30)),
    ]

    res = resolve_current_price(reports=reports, votes=votes, now=now)
    assert res.support == 2
    assert res.confirmations_count == 1
    assert res.status == PriceStatus.VERIFIED


def test_reports_and_votes_outside_window_are_ignored() -> None:
    now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    # Old report 4 days ago (outside 3-day window) had 3 supporters.
    # Fresh report 1 hour ago has 1 supporter.
    reports = [
        ReportRecord(1, 5.99, "user-1", now - timedelta(days=4)),
        ReportRecord(2, 6.45, "user-4", now - timedelta(hours=1)),
    ]
    votes = [
        VoteRecord(1, "user-2", VoteType.CONFIRM, now - timedelta(days=4)),
        VoteRecord(1, "user-3", VoteType.CONFIRM, now - timedelta(days=4)),
        # Even a stale vote referencing a fresh report outside the window is ignored.
        VoteRecord(2, "user-5", VoteType.CONFIRM, now - timedelta(days=4)),
    ]

    res = resolve_current_price(reports=reports, votes=votes, now=now)
    assert res.price == 6.45
    assert res.support == 1
    assert res.status == PriceStatus.UNCONFIRMED


def test_suspicious_vs_too_few_nearby_stations() -> None:
    now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    reports = [ReportRecord(1, 4.90, "user-1", now - timedelta(hours=1))]

    # Fewer than 3 nearby stations -> unconfirmed, NOT suspicious.
    few_stations = resolve_current_price(
        reports=reports,
        votes=[],
        now=now,
        nearby_prices=[6.40, 6.45],
    )
    assert few_stations.status == PriceStatus.UNCONFIRMED

    # At least 3 nearby stations with median 6.45 (> 1.00 PLN deviation) -> suspicious.
    enough_stations = resolve_current_price(
        reports=reports,
        votes=[],
        now=now,
        nearby_prices=[6.40, 6.45, 6.50],
    )
    assert enough_stations.status == PriceStatus.SUSPICIOUS

    # Once confirmed by another driver (support >= 2), suspicious becomes verified.
    confirmed = resolve_current_price(
        reports=reports,
        votes=[VoteRecord(1, "user-2", VoteType.CONFIRM, now - timedelta(minutes=10))],
        now=now,
        nearby_prices=[6.40, 6.45, 6.50],
    )
    assert confirmed.status == PriceStatus.VERIFIED


def test_expired_and_unknown_prices() -> None:
    now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)

    unknown = resolve_current_price(reports=[], votes=[], now=now)
    assert unknown.price is None
    assert unknown.status == PriceStatus.UNKNOWN
    assert unknown.needs_warning is True

    old_reports = [
        ReportRecord(1, 6.10, "user-1", now - timedelta(days=5)),
        ReportRecord(2, 6.25, "user-2", now - timedelta(days=4)),
    ]
    expired = resolve_current_price(reports=old_reports, votes=[], now=now)
    assert expired.price == 6.25
    assert expired.status == PriceStatus.EXPIRED
    assert expired.age_hours == 96.0
    assert expired.needs_warning is True


def test_photo_report_wins_as_verified_until_rejected() -> None:
    now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    reports = [
        ReportRecord(1, 6.20, "user-1", now - timedelta(hours=10)),
        ReportRecord(2, 6.20, "user-2", now - timedelta(hours=9)),
        ReportRecord(3, 6.20, "user-3", now - timedelta(hours=8)),
        ReportRecord(4, 6.65, "user-4", now - timedelta(hours=2), source=ReportSource.PHOTO),
    ]

    # Photo report beats older verified manual reports (support 3) and is verified immediately.
    result = resolve_current_price(reports=reports, votes=[], now=now)
    assert result.price == 6.65
    assert result.status == PriceStatus.VERIFIED
    assert result.needs_warning is False

    # A newer photo report supersedes the older photo report.
    reports_with_newer_photo = [
        *reports,
        ReportRecord(5, 6.72, "user-5", now - timedelta(minutes=20), source=ReportSource.PHOTO),
    ]
    newer_result = resolve_current_price(reports=reports_with_newer_photo, votes=[], now=now)
    assert newer_result.price == 6.72
    assert newer_result.status == PriceStatus.VERIFIED

    # If users later reject the photo report, its trust boost is revoked.
    rejected = resolve_current_price(
        reports=reports,
        votes=[VoteRecord(4, "user-5", VoteType.REJECT, now - timedelta(minutes=30))],
        now=now,
    )
    assert rejected.price == 6.20
    assert rejected.status == PriceStatus.VERIFIED
