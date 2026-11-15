from datetime import UTC, datetime, timedelta

import pytest

from app.domain.auth import create_admin_token, verify_admin_credentials, verify_admin_token


def test_verify_admin_credentials() -> None:
    assert verify_admin_credentials("admin", "s3cr3t", "admin", "s3cr3t") is True
    assert verify_admin_credentials("admin", "wrong", "admin", "s3cr3t") is False
    assert verify_admin_credentials("other", "s3cr3t", "admin", "s3cr3t") is False
    assert verify_admin_credentials("", "", "", "") is False


def test_create_and_verify_admin_token_lifecycle() -> None:
    now = datetime(2026, 11, 15, 22, 0, tzinfo=UTC)
    token, expires_at = create_admin_token("admin", "signing-secret", now=now, ttl_hours=2)

    assert expires_at == now + timedelta(hours=2)
    assert verify_admin_token(token, "signing-secret", now + timedelta(hours=1)) == "admin"

    with pytest.raises(ValueError):
        verify_admin_token(token, "wrong-secret", now)

    with pytest.raises(ValueError):
        verify_admin_token(f"{token}tamper", "signing-secret", now)

    with pytest.raises(ValueError):
        verify_admin_token(token, "signing-secret", now + timedelta(hours=2))
