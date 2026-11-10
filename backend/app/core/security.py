from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.core.config import settings


def hash_password(plain_password: str) -> str:
    if not plain_password or len(plain_password.encode("utf-8")) > 72:
        raise ValueError("Password must be non-empty and at most 72 bytes.")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    if not plain_password or not password_hash:
        return False
    try:
        pw_bytes = plain_password.encode("utf-8")
        if len(pw_bytes) > 72:
            return False
        return bcrypt.checkpw(pw_bytes, password_hash.encode("utf-8"))
    except Exception:
        return False


def create_access_token(
    subject: str,
    role: str,
    remember_me: bool = False,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, str, datetime]:
    now = datetime.now(timezone.utc)
    minutes = (
        settings.jwt_remember_me_expire_minutes
        if remember_me
        else settings.jwt_access_token_expire_minutes
    )
    expires_at = now + timedelta(minutes=minutes)
    jti = str(uuid4())
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "role", "exp", "jti"]},
        )
        return payload
    except InvalidTokenError as exc:
        raise ValueError("Invalid or expired authentication token.") from exc

