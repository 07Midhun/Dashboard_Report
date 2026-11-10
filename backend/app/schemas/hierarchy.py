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
    wards_count: int = 0
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
    wards_count: int = 0
    report_files_count: int = 0
    created_at: datetime
    updated_at: datetime


class ZoneCreate(BaseModel):
    region_id: int
    zone_name: str = Field(..., min_length=2, max_length=200)
    zone_code: str | None = Field(default=None, max_length=32)
    status: StatusLiteral = "active"


class ZoneUpdate(BaseModel):
    zone_name: str | None = Field(default=None, min_length=2, max_length=200)
    zone_code: str | None = Field(default=None, max_length=32)
    status: StatusLiteral | None = None


class ZoneOut(BaseModel):
    id: int
    region_id: int
    region_name: str
    customer_id: int
    customer_name: str
    zone_name: str
    zone_code: str | None = None
    status: str
    wards_count: int = 0
    report_files_count: int = 0
    created_at: datetime
    updated_at: datetime


class WardCreate(BaseModel):
    zone_id: int
    ward_name: str = Field(..., min_length=1, max_length=200)
    ward_number: str = Field(..., min_length=1, max_length=64)
    ward_code: str | None = Field(default=None, max_length=64)
    status: StatusLiteral = "active"


class WardUpdate(BaseModel):
    ward_name: str | None = Field(default=None, min_length=1, max_length=200)
    ward_number: str | None = Field(default=None, min_length=1, max_length=64)
    ward_code: str | None = Field(default=None, min_length=1, max_length=64)
    status: StatusLiteral | None = None


class WardOut(BaseModel):
    id: int
    zone_id: int
    zone_name: str
    zone_code: str | None = None
    region_id: int
    region_name: str
    customer_id: int
    customer_name: str
    ward_name: str
    ward_number: str
    ward_code: str
    status: str
    has_pole_survey: bool = False
    has_lamp_installation: bool = False
    merged_status: str | None = None
    has_published_merged: bool = False
    created_at: datetime
    updated_at: datetime


class HierarchyWardNode(BaseModel):
    id: int
    zone_id: int
    ward_name: str
    ward_number: str
    ward_code: str
    status: str
    has_pole_survey: bool = False
    has_lamp_installation: bool = False
    merged_status: str | None = None
    has_published_merged: bool = False


class HierarchyZoneNode(BaseModel):
    id: int
    region_id: int
    zone_name: str
    zone_code: str | None = None
    status: str
    wards_count: int = 0
    wards_with_pole_survey: int = 0
    wards_with_lamp_installation: int = 0
    wards_with_merged: int = 0
    wards: list[HierarchyWardNode] = Field(default_factory=list)


class HierarchyRegionNode(BaseModel):
    id: int
    customer_id: int
    region_name: str
    status: str
    zones_count: int
    wards_count: int = 0
    zones: list[HierarchyZoneNode]


class HierarchyCustomerNode(BaseModel):
    id: int
    customer_name: str
    status: str
    regions_count: int
    zones_count: int
    wards_count: int = 0
    regions: list[HierarchyRegionNode]

