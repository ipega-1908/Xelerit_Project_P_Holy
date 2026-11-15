from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_now, require_admin
from app.schemas import AdminLoginRequest, AdminLoginResponse, AdminSessionRead
from app.services import admin as admin_service

router = APIRouter(prefix="/admin", tags=["admin"])

NowDep = Annotated[datetime, Depends(get_now)]
AdminDep = Annotated[str, Depends(require_admin)]


@router.post("/login", response_model=AdminLoginResponse)
def login_admin(payload: AdminLoginRequest, now: NowDep) -> AdminLoginResponse:
    """Authenticate admin credentials and issue a signed bearer token."""
    return admin_service.login_admin(payload=payload, now=now)


@router.get("/session", response_model=AdminSessionRead)
def get_admin_session(admin_username: AdminDep) -> AdminSessionRead:
    """Verify current admin bearer token."""
    return AdminSessionRead(username=admin_username, is_admin=True)
