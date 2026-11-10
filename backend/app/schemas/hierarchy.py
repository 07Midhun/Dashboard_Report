from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


StatusLiteral = Literal["active", "inactive"]


class CustomerCreate(BaseModel):
    customer_name: str = Field(..., min_length=2, max_length=200)
    status: StatusLiteral = "active"


class CustomerUpdate(BaseModel):
    customer_name: str | None = Field(default=None, min_length=2, max_length=200)
    status: StatusLiteral | None = None


class CustomerOut(BaseModel):
    id: int
    customer_name: str
    status: str
    regions_count: int = 0
    zones_count: int = 0
    report_files_count: int = 0
    created_at: datetime
    updated_at: datetime


class RegionCreate(BaseModel):
    customer_id: int
    region_name: str = Field(..., min_length=2, max_length=200)
    status: StatusLiteral = "active"


class RegionUpdate(BaseModel):
    region_name: str | None = Field(default=None, min_length=2, max_length=200)
    status: StatusLiteral | None = None


class RegionOut(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    region_name: str
    status: str
    zones_count: int = 0
    report_files_count: int = 0
    created_at: datetime
    updated_at: datetime


class ZoneCreate(BaseModel):
    region_id: int
    zone_name: str = Field(..., min_length=2, max_length=200)
    status: StatusLiteral = "active"


class ZoneUpdate(BaseModel):
    zone_name: str | None = Field(default=None, min_length=2, max_length=200)
    status: StatusLiteral | None = None


class ZoneOut(BaseModel):
    id: int
    region_id: int
    region_name: str
    customer_id: int
    customer_name: str
    zone_name: str
    status: str
    has_pole_survey: bool = False
    has_lamp_installation: bool = False
    merged_status: str | None = None
    created_at: datetime
    updated_at: datetime


class HierarchyZoneNode(BaseModel):
    id: int
    region_id: int
    zone_name: str
    status: str
    has_pole_survey: bool = False
    has_lamp_installation: bool = False
    merged_status: str | None = None
    has_published_merged: bool = False


class HierarchyRegionNode(BaseModel):
    id: int
    customer_id: int
    region_name: str
    status: str
    zones_count: int
    zones: list[HierarchyZoneNode]


class HierarchyCustomerNode(BaseModel):
    id: int
    customer_name: str
    status: str
    regions_count: int
    zones_count: int
    regions: list[HierarchyRegionNode]

