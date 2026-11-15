from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.domain.auth import AuthActor
from app.services import admin as admin_service
from app.services import auth as auth_service


def get_now() -> datetime:
    """Provide current UTC timestamp (overridable in tests)."""
    return datetime.now(UTC)


def get_user_id(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> str:
    """Extract and validate non-empty X-User-Id header for write/voting endpoints."""
    if x_user_id is None or not x_user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="X-User-Id header is required",
        )
    return x_user_id.strip()


def require_admin(
    now: Annotated[datetime, Depends(get_now)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> str:
    """Require valid admin Bearer token on protected station/benefit endpoints."""
    return admin_service.verify_admin_bearer(authorization=authorization, now=now)


def require_actor(
    now: Annotated[datetime, Depends(get_now)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> AuthActor:
    """Require a valid user or admin Bearer token."""
    return auth_service.verify_actor_bearer(authorization=authorization, now=now)


def get_optional_actor(
    now: Annotated[datetime, Depends(get_now)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> AuthActor | None:
    """Return verified AuthActor when a valid Bearer token is present, otherwise None."""
    if authorization is None or not authorization.lower().startswith("bearer "):
        return None
    try:
        return auth_service.verify_actor_bearer(authorization=authorization, now=now)
    except HTTPException:
        return None
