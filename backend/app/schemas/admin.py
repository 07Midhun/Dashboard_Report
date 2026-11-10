from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    email: str = Field(..., min_length=3, max_length=255)
    username: str | None = Field(default=None, min_length=2, max_length=100)
    password: str = Field(..., min_length=8, max_length=72)
    role: Literal["admin", "customer"] = "customer"
    status: Literal["active", "inactive"] = "active"
    customer_ids: list[int] = Field(default_factory=list)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    username: str | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, min_length=8, max_length=72)
    role: Literal["admin", "customer"] | None = None
    status: Literal["active", "inactive"] | None = None
    customer_ids: list[int] | None = None


class ExternalLinkOut(BaseModel):
    id: int
    link_key: str
    link_name: str
    url: str | None
    is_enabled: bool
    updated_at: datetime


class ExternalLinkItemUpdate(BaseModel):
    link_key: Literal["om_dashboard", "energy_saving_report"]
    link_name: str | None = Field(default=None, min_length=2, max_length=120)
    url: str | None = Field(default=None, max_length=1000)
    is_enabled: bool | None = None


class ExternalLinksBulkUpdate(BaseModel):
    links: list[ExternalLinkItemUpdate]


class LedRuleCreate(BaseModel):
    pattern: str = Field(..., min_length=1, max_length=150)
    match_type: Literal["exact", "prefix", "contains", "word", "regex"] = "contains"
    classification: Literal["led", "non_led"] = "led"
    is_active: bool = True


class LedRuleUpdate(BaseModel):
    pattern: str | None = Field(default=None, min_length=1, max_length=150)
    match_type: Literal["exact", "prefix", "contains", "word", "regex"] | None = None
    classification: Literal["led", "non_led"] | None = None
    is_active: bool | None = None


class LedRuleOut(BaseModel):
    id: int
    pattern: str
    match_type: str
    classification: str
    is_active: bool
    created_at: datetime


class AuditLogOut(BaseModel):
    id: int
    user_id: int | None
    user_name: str | None
    user_email: str | None
    action: str
    entity_type: str
    entity_id: str | None
    details: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime

