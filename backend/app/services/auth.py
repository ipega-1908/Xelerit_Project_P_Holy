from datetime import datetime

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.domain.auth import (
    AuthActor,
    create_session_token,
    hash_password,
    verify_password,
    verify_session_token,
)
from app.models import User
from app.schemas import AuthTokenResponse, UserLoginRequest, UserRegisterRequest
from app.services.admin import get_signing_secret


def register_user(
    payload: UserRegisterRequest,
    session: Session,
    now: datetime,
) -> AuthTokenResponse:
    """Register a new driver account with PBKDF2 password hash and issue a session token."""
    normalized_username = payload.username.strip()
    existing = session.exec(select(User).where(User.username == normalized_username)).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Użytkownik o takiej nazwie już istnieje",
        )

    user = User(
        username=normalized_username,
        password_hash=hash_password(payload.password),
        created_at=now,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None

    actor = AuthActor(username=user.username, role="user", user_id=user.id)
    token, expires_at = create_session_token(actor, secret=get_signing_secret(), now=now)
    return AuthTokenResponse(
        access_token=token,
        username=user.username,
        role="user",
        user_id=user.id,
        expires_at=expires_at,
    )


def login_user(
    payload: UserLoginRequest,
    session: Session,
    now: datetime,
) -> AuthTokenResponse:
    """Authenticate a driver account and issue a signed bearer token."""
    normalized_username = payload.username.strip()
    user = session.exec(select(User).where(User.username == normalized_username)).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowa nazwa użytkownika lub hasło",
            headers={"WWW-Authenticate": "Bearer"},
        )

    assert user.id is not None
    actor = AuthActor(username=user.username, role="user", user_id=user.id)
    token, expires_at = create_session_token(actor, secret=get_signing_secret(), now=now)
    return AuthTokenResponse(
        access_token=token,
        username=user.username,
        role="user",
        user_id=user.id,
        expires_at=expires_at,
    )


def verify_actor_bearer(authorization: str | None, now: datetime) -> AuthActor:
    """Validate Authorization: Bearer <token> header for either a user or admin session."""
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:].strip()
    try:
        return verify_session_token(token=token, secret=get_signing_secret(), now=now)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
