import os
import secrets
from datetime import datetime

from fastapi import HTTPException, status

from app.domain.auth import create_admin_token, verify_admin_credentials, verify_admin_token
from app.schemas import AdminLoginRequest, AdminLoginResponse

# Ephemeral per-process fallback secret so admins only need
# ADMIN_USERNAME and ADMIN_PASSWORD in .env.
_PROCESS_SIGNING_SECRET = secrets.token_hex(32)


def _get_configured_credentials() -> tuple[str, str]:
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin credentials are not configured (set ADMIN_USERNAME and ADMIN_PASSWORD)",
        )
    return username, password


def _get_signing_secret() -> str:
    return os.getenv("ADMIN_SESSION_SECRET", "").strip() or _PROCESS_SIGNING_SECRET


def login_admin(payload: AdminLoginRequest, now: datetime) -> AdminLoginResponse:
    """Validate admin credentials from env and return a signed bearer token."""
    expected_username, expected_password = _get_configured_credentials()
    if not verify_admin_credentials(
        payload.username.strip(),
        payload.password,
        expected_username,
        expected_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token, expires_at = create_admin_token(expected_username, _get_signing_secret(), now=now)
    return AdminLoginResponse(
        access_token=token,
        username=expected_username,
        expires_at=expires_at,
    )


def verify_admin_bearer(authorization: str | None, now: datetime) -> str:
    """Validate Authorization: Bearer <token> header and return the admin username."""
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:].strip()
    try:
        return verify_admin_token(token, _get_signing_secret(), now=now)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
