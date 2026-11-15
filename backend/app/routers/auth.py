from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.database import get_session
from app.dependencies import get_now, require_actor
from app.domain.auth import AuthActor
from app.schemas import AuthSessionRead, AuthTokenResponse, UserLoginRequest, UserRegisterRequest
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

SessionDep = Annotated[Session, Depends(get_session)]
NowDep = Annotated[datetime, Depends(get_now)]
ActorDep = Annotated[AuthActor, Depends(require_actor)]


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserRegisterRequest,
    session: SessionDep,
    now: NowDep,
) -> AuthTokenResponse:
    """Register a new driver account and issue a signed bearer token."""
    return auth_service.register_user(payload=payload, session=session, now=now)


@router.post("/login", response_model=AuthTokenResponse)
def login(
    payload: UserLoginRequest,
    session: SessionDep,
    now: NowDep,
) -> AuthTokenResponse:
    """Authenticate an existing driver account and issue a signed bearer token."""
    return auth_service.login_user(payload=payload, session=session, now=now)


@router.get("/session", response_model=AuthSessionRead)
def get_session_info(actor: ActorDep) -> AuthSessionRead:
    """Return the authenticated driver or admin identity for the current bearer token."""
    return AuthSessionRead(
        username=actor.username,
        role=actor.role,
        user_id=actor.user_id,
    )
