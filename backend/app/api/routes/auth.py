from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.dependencies import AuthContext, bearer_scheme, get_client_ip, get_current_auth
from app.database.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.schemas.common import MessageResponse
from app.services.auth_service import authenticate_user, logout_token, serialize_user


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    return authenticate_user(db, payload, ip_address=get_client_ip(request))


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> MessageResponse:
    if credentials and credentials.credentials:
        logout_token(
            db,
            raw_token=credentials.credentials,
            user=auth.user,
            ip_address=get_client_ip(request),
        )
    return MessageResponse(message="Logged out successfully.")


@router.get("/me", response_model=UserOut)
def get_me(
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> UserOut:
    return serialize_user(db, auth.user)

