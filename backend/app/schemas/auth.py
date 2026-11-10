from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=255, description="Username or email")
    password: str = Field(..., min_length=1, max_length=128)
    login_type: Literal["admin", "customer"] | None = Field(
        default=None,
        description="Optional login portal mode; if specified, verifies user role matches",
    )
    remember_me: bool = False


class CustomerAssignmentOut(BaseModel):
    customer_id: int
    customer_name: str
    access_level: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    username: str | None
    role: str
    status: str
    last_login_at: datetime | None
    created_at: datetime
    assigned_customers: list[CustomerAssignmentOut] = Field(default_factory=list)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut

