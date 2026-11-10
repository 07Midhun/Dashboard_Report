from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.security import create_access_token, decode_access_token, verify_password
from app.models.user import RevokedToken, User, UserCustomerPermission
from app.schemas.auth import CustomerAssignmentOut, LoginRequest, TokenResponse, UserOut
from app.services.audit_service import record_audit_log


def serialize_user(db: Session, user: User) -> UserOut:
    assignments: list[CustomerAssignmentOut] = []
    if user.role != "admin":
        rows = db.scalars(
            select(UserCustomerPermission)
            .options(selectinload(UserCustomerPermission.customer))
            .where(UserCustomerPermission.user_id == user.id)
        ).all()
        for row in rows:
            if row.customer is not None:
                assignments.append(
                    CustomerAssignmentOut(
                        customer_id=row.customer_id,
                        customer_name=row.customer.customer_name,
                        access_level=row.access_level,
                    )
                )

    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        username=user.username,
        role=user.role,
        status=user.status,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        assigned_customers=assignments,
    )


def authenticate_user(
    db: Session,
    payload: LoginRequest,
    ip_address: str | None = None,
) -> TokenResponse:
    ident = payload.identifier.strip().lower()
    user = db.scalar(
        select(User).where(
            or_(
                func.lower(User.email) == ident,
                func.lower(User.username) == ident,
            )
        )
    )

    if user is None or not verify_password(payload.password, user.password_hash):
        record_audit_log(
            db,
            user_id=user.id if user else None,
            action="auth.login_failed",
            entity_type="user",
            entity_id=user.id if user else None,
            details={"identifier": ident, "login_type": payload.login_type},
            ip_address=ip_address,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password.",
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Contact an administrator.",
        )

    if payload.login_type is not None and user.role != payload.login_type:
        expected_label = "Administrator" if payload.login_type == "admin" else "Customer"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This account does not have {expected_label} access. Please use the correct login tab.",
        )

    token, _, expires_at = create_access_token(
        subject=str(user.id),
        role=user.role,
        remember_me=payload.remember_me,
    )
    user.last_login_at = datetime.now(timezone.utc)
    record_audit_log(
        db,
        user_id=user.id,
        action="auth.login_success",
        entity_type="user",
        entity_id=user.id,
        details={"role": user.role, "remember_me": payload.remember_me},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)

    return TokenResponse(
        access_token=token,
        expires_at=expires_at,
        user=serialize_user(db, user),
    )


def logout_token(
    db: Session,
    *,
    raw_token: str,
    user: User,
    ip_address: str | None = None,
) -> None:
    payload = decode_access_token(raw_token)
    jti = payload["jti"]
    exp_ts = payload["exp"]
    expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc)

    existing = db.scalar(select(RevokedToken).where(RevokedToken.jti == jti))
    if existing is None:
        db.add(RevokedToken(jti=jti, expires_at=expires_at))

    # Opportunistic cleanup of expired revocation rows
    now = datetime.now(timezone.utc)
    db.query(RevokedToken).filter(RevokedToken.expires_at < now).delete(synchronize_session=False)

    record_audit_log(
        db,
        user_id=user.id,
        action="auth.logout",
        entity_type="user",
        entity_id=user.id,
        ip_address=ip_address,
    )
    db.commit()

