export type UserRole = "admin" | "customer";
export type EntityStatus = "active" | "inactive";
export type ReportType = "pole_survey" | "lamp_installation";

export interface CustomerAssignment {
  customer_id: number;
  customer_name: string;
  access_level: string;
}

export interface User {
  id: number;
  name: string;
  email: string;
  username: string | null;
  role: UserRole;
  status: EntityStatus;
  last_login_at: string | null;
  created_at: string;
  assigned_customers: CustomerAssignment[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: User;
}

export interface Customer {
  id: number;
  customer_name: string;
  status: EntityStatus;
  regions_count: number;
  zones_count: number;
  wards_count: number;
  report_files_count: number;
  created_at: string;
  updated_at: string;
}

export interface Region {
  id: number;
  customer_id: number;
  customer_name: string;
  region_name: string;
  status: EntityStatus;
  zones_count: number;
  wards_count: number;
  report_files_count: number;
  created_at: string;
  updated_at: string;
}

export interface Zone {
  id: number;
  region_id: number;
  region_name: string;
  customer_id: number;
  customer_name: string;
  zone_name: string;
  zone_code: string | null;
  status: EntityStatus;
  wards_count: number;
  report_files_count: number;
  created_at: string;
  updated_at: string;
}

export interface Ward {
  id: number;
  zone_id: number;
  zone_name: string;
  zone_code: string | null;
  region_id: number;
  region_name: string;
  customer_id: number;
  customer_name: string;
  ward_name: string;
  ward_number: string;
  ward_code: string;
  status: EntityStatus;
  has_pole_survey: boolean;
  has_lamp_installation: boolean;
  merged_status: string | null;
  has_published_merged: boolean;
  created_at: string;
  updated_at: string;
}

export interface HierarchyWardNode {
  id: number;
  zone_id: number;
  ward_name: string;
  ward_number: string;
  ward_code: string;
  status: EntityStatus;
  has_pole_survey: boolean;
  has_lamp_installation: boolean;
  merged_status: string | null;
  has_published_merged: boolean;
}

export interface HierarchyZoneNode {
  id: number;
  region_id: number;
  zone_name: string;
  zone_code: string | null;
  status: EntityStatus;
  wards_count: number;
  wards_with_pole_survey: number;
  wards_with_lamp_installation: number;
  wards_with_merged: number;
  wards: HierarchyWardNode[];
}

export interface HierarchyRegionNode {
  id: number;
  customer_id: number;
  region_name: string;
  status: EntityStatus;
  zones_count: number;
  wards_count: number;
  zones: HierarchyZoneNode[];
}

export interface HierarchyCustomerNode {
  id: number;
  customer_name: string;
  status: EntityStatus;
  regions_count: number;
  zones_count: number;
  wards_count: number;
  regions: HierarchyRegionNode[];
}

export interface ReportFileVersion {
  id: number;
  version: number;
  original_filename: string;
  file_size: number;
  checksum_sha256: string;
  sheet_name: string | null;
  header_row_index: number | null;
  row_count: number;
  uploaded_by: number;
  uploaded_by_name: string | null;
  uploaded_at: string;
}

export interface ReportFile {
  id: number;
  customer_id: number;
  customer_name: string;
  region_id: number;
  region_name: string;
  zone_id: number;
  zone_name: string;
  zone_code: string | null;
  ward_id: number;
  ward_name: string;
  ward_number: string;
  ward_code: string;
  report_type: ReportType;
  original_filename: string;
  file_size: number;
  file_extension: string;
  sheet_name: string | null;
  header_row_index: number | null;
  row_count: number;
  version: number;
  status: string;
  uploaded_by: number;
  uploaded_by_name: string | null;
  uploaded_at: string;
  updated_at: string;
  versions: ReportFileVersion[];
}

export interface ExcelPreview {
  report_id: number;
  original_filename: string;
  version: number;
  sheets: string[];
  active_sheet: string;
  header_row_index: number;
  columns: string[];
  header_signature_hash: string;
  suggested_mapping: Record<string, string | null>;
  needs_mapping_confirmation: boolean;
  warnings: string[];
  total_rows: number;
  page: number;
  page_size: number;
  rows: Record<string, any>[];
}

export interface MappingInput {
  sheet_name?: string | null;
  header_row_index?: number | null;
  pole_number_col: string;
  arm_count_col?: string | null;
  lamp_type_col?: string | null;
  extra_mappings?: Record<string, string>;
}

export interface MergedReportInspect {
  customer_id: number;
  region_id: number;
  zone_id: number;
  ward_id: number;
  pole_survey_ready: boolean;
  lamp_installation_ready: boolean;
  pole_survey_file: ReportFile | null;
  lamp_installation_file: ReportFile | null;
  pole_survey_sheets: string[];
  pole_survey_active_sheet: string | null;
  pole_survey_header_row: number | null;
  pole_survey_headers: string[];
  pole_survey_suggested_mapping: Record<string, string | null>;
  pole_survey_saved_mapping: Record<string, any> | null;
  pole_survey_needs_confirmation: boolean;
  lamp_sheets: string[];
  lamp_active_sheet: string | null;
  lamp_header_row: number | null;
  lamp_headers: string[];
  lamp_suggested_mapping: Record<string, string | null>;
  lamp_saved_mapping: Record<string, any> | null;
  lamp_needs_confirmation: boolean;
  warnings: string[];
  blocking_error: string | null;
}

export interface ProcessingSummary {
  total_lamp_installation_records: number;
  total_survey_records: number;
  total_led_records: number;
  unique_eligible_led_records: number;
  existing_records: number;
  added_records: number;
  duplicate_records: number;
  invalid_records: number;
  unknown_lamp_type_records: number;
  non_led_records: number;
  final_merged_records: number;
  processing_status: string;
  warnings: string[];
  error_message: string | null;
}

export interface MergedReportVersion {
  id: number;
  version: number;
  file_size: number;
  source_pole_survey_version: number;
  source_lamp_installation_version: number;
  status: string;
  generated_by: number;
  generated_by_name: string | null;
  generated_at: string;
  published_by: number | null;
  published_at: string | null;
}

export interface MergedReport {
  id: number;
  customer_id: number;
  customer_name: string;
  region_id: number;
  region_name: string;
  zone_id: number;
  zone_name: string;
  zone_code: string | null;
  ward_id: number;
  ward_name: string;
  ward_number: string;
  ward_code: string;
  current_version: number;
  status: string;
  is_outdated: boolean;
  source_pole_survey_version: number | null;
  source_lamp_installation_version: number | null;
  active_pole_survey_version: number | null;
  active_lamp_installation_version: number | null;
  generated_by: number;
  generated_by_name: string | null;
  generated_at: string;
  published_by: number | null;
  published_at: string | null;
  latest_summary: ProcessingSummary | null;
  versions: MergedReportVersion[];
}

export interface MergedReportPreview {
  merged_report: MergedReport;
  summary: ProcessingSummary;
  lamp_columns: string[];
  existing_lamp_records: Record<string, any>[];
  newly_added_records: Record<string, any>[];
  skipped_existing_records: Record<string, any>[];
  duplicate_records: Record<string, any>[];
  invalid_records: Record<string, any>[];
  unknown_lamp_types: Record<string, any>[];
}

export interface RegionAvailabilityItem {
  customer_id: number;
  customer_name: string;
  region_id: number;
  region_name: string;
  total_zones: number;
  total_wards: number;
  pole_survey_count: number;
  lamp_installation_count: number;
  merged_published_count: number;
  merged_draft_or_outdated_count: number;
  awaiting_uploads_count: number;
  error_wards_count: number;
}

export interface ZoneAvailabilityItem {
  customer_id: number;
  customer_name: string;
  region_id: number;
  region_name: string;
  zone_id: number;
  zone_name: string;
  zone_code: string | null;
  total_wards: number;
  pole_survey_count: number;
  lamp_installation_count: number;
  merged_published_count: number;
  merged_draft_or_outdated_count: number;
  awaiting_uploads_count: number;
  error_wards_count: number;
}

export interface AdminDashboardData {
  total_customers: number;
  total_regions: number;
  total_zones: number;
  total_wards: number;
  wards_with_pole_survey: number;
  wards_with_lamp_installation: number;
  wards_with_completed_merged: number;
  wards_with_published_merged: number;
  wards_awaiting_uploads: number;
  wards_with_processing_errors: number;
  total_pole_survey_reports: number;
  total_lamp_installation_reports: number;
  total_merged_reports: number;
  recent_uploads: {
    id: number;
    report_type: string;
    original_filename: string;
    version: number;
    customer_name: string;
    region_name: string;
    zone_name: string;
    ward_id: number;
    ward_number: string;
    ward_name: string;
    uploaded_by_name: string | null;
    uploaded_at: string;
  }[];
  recent_merged_reports: {
    id: number;
    customer_name: string;
    region_name: string;
    zone_name: string;
    ward_id: number;
    ward_number: string;
    ward_name: string;
    current_version: number;
    status: string;
    added_records: number;
    final_merged_records: number;
    generated_at: string;
  }[];
  latest_processing_activity: {
    id: number;
    customer_name: string;
    region_name: string;
    zone_name: string;
    ward_id: number;
    ward_number: string;
    ward_name: string;
    processing_status: string;
    added_records: number;
    duplicate_records: number;
    invalid_records: number;
    unknown_lamp_type_records: number;
    error_message: string | null;
    created_at: string;
  }[];
  failed_processing_records: {
    id: number;
    customer_name: string;
    region_name: string;
    zone_name: string;
    ward_id: number;
    ward_number: string;
    ward_name: string;
    processing_status: string;
    error_message: string | null;
    created_at: string;
  }[];
  report_availability_by_region: RegionAvailabilityItem[];
  zone_availability: ZoneAvailabilityItem[];
}

export interface CustomerDashboardData {
  customer_names: string[];
  total_regions: number;
  total_zones: number;
  total_wards: number;
  wards_with_pole_survey: number;
  wards_with_lamp_installation: number;
  wards_with_completed_merged: number;
  wards_awaiting_uploads: number;
  available_pole_survey_count: number;
  available_lamp_installation_count: number;
  available_merged_count: number;
  last_updated_at: string | null;
  recent_available_reports: {
    id: number;
    category: string;
    title: string;
    region_name: string;
    zone_name: string;
    ward_id: number;
    ward_number: string;
    ward_name: string;
    updated_at: string;
    version: number;
  }[];
  region_availability: RegionAvailabilityItem[];
  zone_availability: ZoneAvailabilityItem[];
}

export interface ExternalLink {
  id: number;
  link_key: "om_dashboard" | "energy_saving_report";
  link_name: string;
  url: string | null;
  is_enabled: boolean;
  updated_at: string;
}

export interface LedRule {
  id: number;
  pattern: string;
  match_type: "exact" | "prefix" | "contains" | "word" | "regex";
  classification: "led" | "non_led";
  is_active: boolean;
  created_at: string;
}

export interface AuditLogEntry {
  id: number;
  user_id: number | null;
  user_name: string | null;
  user_email: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  details: Record<string, any> | null;
  ip_address: string | null;
  created_at: string;
}

export interface UploadHistoryItem {
  id: number;
  report_file_id: number;
  report_type: ReportType;
  customer_id: number;
  customer_name: string;
  region_id: number;
  region_name: string;
  zone_id: number;
  zone_name: string;
  zone_code: string | null;
  ward_id: number;
  ward_number: string;
  ward_name: string;
  ward_code: string;
  version: number;
  is_current: boolean;
  file_status: string;
  original_filename: string;
  file_size: number;
  row_count: number;
  uploaded_by_name: string | null;
  uploaded_at: string;
}
