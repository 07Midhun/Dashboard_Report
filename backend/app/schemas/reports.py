from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class ReportFileVersionOut(BaseModel):
    id: int
    version: int
    original_filename: str
    file_size: int
    checksum_sha256: str
    sheet_name: str | None
    header_row_index: int | None
    row_count: int
    uploaded_by: int
    uploaded_by_name: str | None = None
    uploaded_at: datetime


class ReportFileOut(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    region_id: int
    region_name: str
    zone_id: int
    zone_name: str
    zone_code: str | None = None
    ward_id: int
    ward_name: str
    ward_number: str
    ward_code: str
    report_type: str
    original_filename: str
    file_size: int
    file_extension: str
    sheet_name: str | None
    header_row_index: int | None
    row_count: int
    version: int
    status: str
    uploaded_by: int
    uploaded_by_name: str | None = None
    uploaded_at: datetime
    updated_at: datetime
    versions: list[ReportFileVersionOut] = Field(default_factory=list)


class ExcelPreviewOut(BaseModel):
    report_id: int
    original_filename: str
    version: int
    sheets: list[str]
    active_sheet: str
    header_row_index: int
    columns: list[str]
    header_signature_hash: str
    suggested_mapping: dict[str, str | None]
    needs_mapping_confirmation: bool
    warnings: list[str]
    total_rows: int
    page: int
    page_size: int
    rows: list[dict[str, Any]]


class MappingInput(BaseModel):
    sheet_name: str | None = None
    header_row_index: int | None = None
    pole_number_col: str
    arm_count_col: str | None = None
    lamp_type_col: str | None = None
    extra_mappings: dict[str, str] = Field(default_factory=dict)


class MergedReportInspectOut(BaseModel):
    customer_id: int
    region_id: int
    zone_id: int
    ward_id: int
    pole_survey_ready: bool
    lamp_installation_ready: bool
    pole_survey_file: ReportFileOut | None = None
    lamp_installation_file: ReportFileOut | None = None
    pole_survey_sheets: list[str] = Field(default_factory=list)
    pole_survey_active_sheet: str | None = None
    pole_survey_header_row: int | None = None
    pole_survey_headers: list[str] = Field(default_factory=list)
    pole_survey_suggested_mapping: dict[str, str | None] = Field(default_factory=dict)
    pole_survey_saved_mapping: dict[str, Any] | None = None
    pole_survey_needs_confirmation: bool = True
    lamp_sheets: list[str] = Field(default_factory=list)
    lamp_active_sheet: str | None = None
    lamp_header_row: int | None = None
    lamp_headers: list[str] = Field(default_factory=list)
    lamp_suggested_mapping: dict[str, str | None] = Field(default_factory=dict)
    lamp_saved_mapping: dict[str, Any] | None = None
    lamp_needs_confirmation: bool = True
    warnings: list[str] = Field(default_factory=list)
    blocking_error: str | None = None


class MergedReportGenerateRequest(BaseModel):
    customer_id: int
    region_id: int
    zone_id: int
    ward_id: int
    pole_survey_mapping: MappingInput
    lamp_installation_mapping: MappingInput
    save_mapping: bool = True


class MergedReportVersionOut(BaseModel):
    id: int
    version: int
    file_size: int
    source_pole_survey_version: int
    source_lamp_installation_version: int
    status: str
    generated_by: int
    generated_by_name: str | None = None
    generated_at: datetime
    published_by: int | None = None
    published_at: datetime | None = None


class ProcessingSummaryOut(BaseModel):
    total_lamp_installation_records: int
    total_survey_records: int
    total_led_records: int
    unique_eligible_led_records: int
    existing_records: int
    added_records: int
    duplicate_records: int
    invalid_records: int
    unknown_lamp_type_records: int
    empty_records: int = 0
    non_led_records: int = 0
    final_merged_records: int
    processing_status: str
    warnings: list[str] = Field(default_factory=list)
    error_message: str | None = None


class MergedReportOut(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    region_id: int
    region_name: str
    zone_id: int
    zone_name: str
    zone_code: str | None = None
    ward_id: int
    ward_name: str
    ward_number: str
    ward_code: str
    current_version: int
    status: str
    is_outdated: bool = False
    source_pole_survey_version: int | None
    source_lamp_installation_version: int | None
    active_pole_survey_version: int | None = None
    active_lamp_installation_version: int | None = None
    generated_by: int
    generated_by_name: str | None = None
    generated_at: datetime
    published_by: int | None
    published_at: datetime | None
    latest_summary: ProcessingSummaryOut | None = None
    versions: list[MergedReportVersionOut] = Field(default_factory=list)


class MergedReportPreviewOut(BaseModel):
    merged_report: MergedReportOut
    summary: ProcessingSummaryOut
    lamp_columns: list[str]
    existing_lamp_records: list[dict[str, Any]]
    newly_added_records: list[dict[str, Any]]
    skipped_existing_records: list[dict[str, Any]]
    duplicate_records: list[dict[str, Any]]
    invalid_records: list[dict[str, Any]]
    unknown_lamp_types: list[dict[str, Any]]
    empty_records: list[dict[str, Any]] = Field(default_factory=list)


class RecentUploadItem(BaseModel):
    id: int
    report_type: str
    original_filename: str
    version: int
    customer_name: str
    region_name: str
    zone_name: str
    ward_id: int
    ward_number: str
    ward_name: str
    uploaded_by_name: str | None
    uploaded_at: datetime


class RecentMergedItem(BaseModel):
    id: int
    customer_name: str
    region_name: str
    zone_name: str
    ward_id: int
    ward_number: str
    ward_name: str
    current_version: int
    status: str
    added_records: int
    final_merged_records: int
    generated_at: datetime


class ProcessingActivityItem(BaseModel):
    id: int
    customer_name: str
    region_name: str
    zone_name: str
    ward_id: int
    ward_number: str
    ward_name: str
    processing_status: str
    added_records: int
    duplicate_records: int
    invalid_records: int
    unknown_lamp_type_records: int
    error_message: str | None
    created_at: datetime


class RegionAvailabilityItem(BaseModel):
    customer_id: int
    customer_name: str
    region_id: int
    region_name: str
    total_zones: int
    total_wards: int = 0
    pole_survey_count: int
    lamp_installation_count: int
    merged_published_count: int
    merged_draft_or_outdated_count: int
    awaiting_uploads_count: int = 0
    error_wards_count: int = 0


class ZoneAvailabilityItem(BaseModel):
    customer_id: int
    customer_name: str
    region_id: int
    region_name: str
    zone_id: int
    zone_name: str
    zone_code: str | None = None
    total_wards: int = 0
    pole_survey_count: int = 0
    lamp_installation_count: int = 0
    merged_published_count: int = 0
    merged_draft_or_outdated_count: int = 0
    awaiting_uploads_count: int = 0
    error_wards_count: int = 0


class RegionMergedLampsItem(BaseModel):
    region_id: int
    region_name: str
    merged_lamps_count: int = 0
    published_wards_count: int = 0


class AdminDashboardOut(BaseModel):
    total_customers: int
    total_regions: int
    total_zones: int
    total_wards: int
    wards_with_pole_survey: int
    wards_with_lamp_installation: int
    wards_with_completed_merged: int
    wards_with_published_merged: int
    wards_awaiting_uploads: int
    wards_with_processing_errors: int
    total_pole_survey_reports: int
    total_lamp_installation_reports: int
    total_merged_reports: int
    merged_lamps_by_region: list[RegionMergedLampsItem] = Field(default_factory=list)
    recent_uploads: list[RecentUploadItem]
    recent_merged_reports: list[RecentMergedItem]
    latest_processing_activity: list[ProcessingActivityItem]
    failed_processing_records: list[ProcessingActivityItem]
    report_availability_by_region: list[RegionAvailabilityItem]
    zone_availability: list[ZoneAvailabilityItem] = Field(default_factory=list)


class CustomerDashboardOut(BaseModel):
    customer_names: list[str]
    total_regions: int
    total_zones: int
    total_wards: int
    wards_with_pole_survey: int
    wards_with_lamp_installation: int
    wards_with_completed_merged: int
    wards_awaiting_uploads: int
    available_pole_survey_count: int
    available_lamp_installation_count: int
    available_merged_count: int
    last_updated_at: datetime | None
    recent_available_reports: list[dict[str, Any]]
    region_availability: list[RegionAvailabilityItem]
    zone_availability: list[ZoneAvailabilityItem] = Field(default_factory=list)

