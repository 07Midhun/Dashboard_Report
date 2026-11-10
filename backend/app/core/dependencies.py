from dataclasses import dataclass
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.session import get_db
from app.models.user import RevokedToken, User, UserCustomerPermission


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: User
    jti: str
    authorized_customer_ids: list[int] | None  # None means unrestricted (admin)


def get_current_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthContext:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    jti = payload.get("jti")
    sub = payload.get("sub")
    if not jti or not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed authentication token.",
        )

    revoked = db.scalar(select(RevokedToken.id).where(RevokedToken.jti == jti))
    if revoked is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been logged out. Please log in again.",
        )

    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user subject in token.",
        ) from exc

    user = db.get(User, user_id)
    if user is None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or no longer exists.",
        )

    if user.role == "admin":
        authorized_ids = None
    else:
        rows = db.scalars(
            select(UserCustomerPermission.customer_id).where(
                UserCustomerPermission.user_id == user.id
            )
        ).all()
        authorized_ids = list(rows)

    return AuthContext(user=user, jti=jti, authorized_customer_ids=authorized_ids)


def get_current_user(auth: AuthContext = Depends(get_current_auth)) -> User:
    return auth.user


def require_admin(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
    if auth.user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator permissions are required for this operation.",
        )
    return auth


def verify_customer_access(auth: AuthContext, customer_id: int) -> None:
    if auth.user.role == "admin":
        return
    if auth.authorized_customer_ids is None or customer_id not in auth.authorized_customer_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access reports for this customer.",
        )


def get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None

