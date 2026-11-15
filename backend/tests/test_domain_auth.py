from datetime import UTC, datetime, timedelta

import pytest

from app.domain.auth import (
    AuthActor,
    create_admin_token,
    create_session_token,
    hash_password,
    verify_admin_credentials,
    verify_admin_token,
    verify_password,
    verify_session_token,
)


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


def test_password_hashing_and_verification() -> None:
    hashed = hash_password("demo", salt=b"0123456789abcdef")
    assert hashed.startswith("pbkdf2_sha256$")
    assert "demo" not in hashed
    assert verify_password("demo", hashed) is True
    assert verify_password("wrong", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password("demo", "malformed-hash") is False


def test_user_session_token_cannot_pass_admin_verification() -> None:
    now = datetime(2026, 11, 15, 22, 0, tzinfo=UTC)
    token, _ = create_session_token(
        AuthActor(username="demo", role="user", user_id=7),
        secret="signing-secret",
        now=now,
    )
    actor = verify_session_token(token, "signing-secret", now + timedelta(minutes=10))
    assert actor == AuthActor(username="demo", role="user", user_id=7)

    with pytest.raises(ValueError, match="Admin role required"):
        verify_admin_token(token, "signing-secret", now)
