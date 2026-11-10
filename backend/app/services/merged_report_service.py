import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.dependencies import AuthContext, verify_customer_access
from app.models.config_models import ColumnMapping, LedClassificationRule
from app.models.hierarchy import Customer, Region, Zone
from app.models.report import (
    MergedReport,
    MergedReportVersion,
    ProcessingLog,
    ReportFile,
)
from app.models.user import User
from app.schemas.reports import (
    MergedReportGenerateRequest,
    MergedReportInspectOut,
    MergedReportOut,
    MergedReportPreviewOut,
    MergedReportVersionOut,
    ProcessingSummaryOut,
)
from app.services.audit_service import record_audit_log
from app.services.excel_reader_service import inspect_workbook
from app.services.excel_writer_service import write_merged_workbook
from app.services.hierarchy_service import validate_zone_hierarchy
from app.services.led_classifier_service import LedClassifier, RuleSpec
from app.services.reconciliation_engine import (
    MappingSpec,
    ReconciliationValidationError,
    reconcile_reports,
)
from app.services.report_file_service import _serialize_report_file
from app.services.storage_service import storage_service


def _find_saved_mapping(
    db: Session, *, customer_id: int, report_type: str, signature_hash: str
) -> ColumnMapping | None:
    cust_match = db.scalar(
        select(ColumnMapping).where(
            ColumnMapping.customer_id == customer_id,
            ColumnMapping.report_type == report_type,
            ColumnMapping.header_signature_hash == signature_hash,
        )
    )
    if cust_match is not None:
        return cust_match
    return db.scalar(
        select(ColumnMapping).where(
            ColumnMapping.customer_id.is_(None),
            ColumnMapping.report_type == report_type,
            ColumnMapping.header_signature_hash == signature_hash,
        )
    )


def _upsert_saved_mapping(
    db: Session,
    *,
    customer_id: int,
    report_type: str,
    signature_hash: str,
    sheet_name: str,
    header_row_index: int,
    mapping_config: dict[str, Any],
    user_id: int,
) -> None:
    existing = db.scalar(
        select(ColumnMapping).where(
            ColumnMapping.customer_id == customer_id,
            ColumnMapping.report_type == report_type,
            ColumnMapping.header_signature_hash == signature_hash,
        )
    )
    if existing is None:
        db.add(
            ColumnMapping(
                customer_id=customer_id,
                report_type=report_type,
                header_signature_hash=signature_hash,
                sheet_name=sheet_name,
                header_row_index=header_row_index,
                mapping_config=mapping_config,
                created_by=user_id,
            )
        )
    else:
        existing.sheet_name = sheet_name
        existing.header_row_index = header_row_index
        existing.mapping_config = mapping_config


def _get_active_source_pair(
    db: Session, *, customer_id: int, region_id: int, zone_id: int
) -> tuple[ReportFile | None, ReportFile | None]:
    pole_survey = db.scalar(
        select(ReportFile)
        .options(selectinload(ReportFile.versions))
        .where(
            ReportFile.customer_id == customer_id,
            ReportFile.region_id == region_id,
            ReportFile.zone_id == zone_id,
            ReportFile.report_type == "pole_survey",
            ReportFile.status == "active",
        )
    )
    lamp_inst = db.scalar(
        select(ReportFile)
        .options(selectinload(ReportFile.versions))
        .where(
            ReportFile.customer_id == customer_id,
            ReportFile.region_id == region_id,
            ReportFile.zone_id == zone_id,
            ReportFile.report_type == "lamp_installation",
            ReportFile.status == "active",
        )
    )
    return pole_survey, lamp_inst


def inspect_zone_sources(
    db: Session,
    *,
    customer_id: int,
    region_id: int,
    zone_id: int,
    pole_sheet: str | None = None,
    pole_header_row: int | None = None,
    lamp_sheet: str | None = None,
    lamp_header_row: int | None = None,
) -> MergedReportInspectOut:
    validate_zone_hierarchy(db, customer_id=customer_id, region_id=region_id, zone_id=zone_id)
    pole_file, lamp_file = _get_active_source_pair(
        db, customer_id=customer_id, region_id=region_id, zone_id=zone_id
    )

    missing_parts: list[str] = []
    if pole_file is None:
        missing_parts.append("Pole Survey Report")
    if lamp_file is None:
        missing_parts.append("Lamp Installation Report")

    warnings: list[str] = []
    blocking_error: str | None = None
    if missing_parts:
        blocking_error = (
            f"Cannot generate Merged Report: missing {' and '.join(missing_parts)} for the selected zone."
        )

    out = MergedReportInspectOut(
        customer_id=customer_id,
        region_id=region_id,
        zone_id=zone_id,
        pole_survey_ready=pole_file is not None,
        lamp_installation_ready=lamp_file is not None,
        pole_survey_file=_serialize_report_file(db, pole_file) if pole_file else None,
        lamp_installation_file=_serialize_report_file(db, lamp_file) if lamp_file else None,
        blocking_error=blocking_error,
    )

    if pole_file is not None:
        pole_abs = storage_service.get_absolute_path(pole_file.storage_path)
        p_insp, _ = inspect_workbook(
            pole_abs,
            sheet_name=pole_sheet or pole_file.sheet_name,
            header_row_index=pole_header_row or pole_file.header_row_index,
        )
        saved_p = _find_saved_mapping(
            db,
            customer_id=customer_id,
            report_type="pole_survey",
            signature_hash=p_insp.header_signature_hash,
        )
        out.pole_survey_sheets = p_insp.sheet_names
        out.pole_survey_active_sheet = p_insp.active_sheet
        out.pole_survey_header_row = p_insp.header_row_index
        out.pole_survey_headers = p_insp.headers
        out.pole_survey_suggested_mapping = p_insp.suggested_mapping
        out.pole_survey_saved_mapping = saved_p.mapping_config if saved_p else None
        out.pole_survey_needs_confirmation = (
            p_insp.needs_mapping_confirmation and saved_p is None
        )
        warnings.extend([f"[Pole Survey] {w}" for w in p_insp.warnings])

    if lamp_file is not None:
        lamp_abs = storage_service.get_absolute_path(lamp_file.storage_path)
        l_insp, _ = inspect_workbook(
            lamp_abs,
            sheet_name=lamp_sheet or lamp_file.sheet_name,
            header_row_index=lamp_header_row or lamp_file.header_row_index,
        )
        saved_l = _find_saved_mapping(
            db,
            customer_id=customer_id,
            report_type="lamp_installation",
            signature_hash=l_insp.header_signature_hash,
        )
        out.lamp_sheets = l_insp.sheet_names
        out.lamp_active_sheet = l_insp.active_sheet
        out.lamp_header_row = l_insp.header_row_index
        out.lamp_headers = l_insp.headers
        out.lamp_suggested_mapping = l_insp.suggested_mapping
        out.lamp_saved_mapping = saved_l.mapping_config if saved_l else None
        out.lamp_needs_confirmation = (
            l_insp.needs_mapping_confirmation and saved_l is None
        )
        warnings.extend([f"[Lamp Installation] {w}" for w in l_insp.warnings])

    out.warnings = warnings
    return out


def _serialize_merged_report(
    db: Session,
    mr: MergedReport,
    *,
    is_admin: bool,
) -> MergedReportOut:
    cust = db.get(Customer, mr.customer_id)
    reg = db.get(Region, mr.region_id)
    zone = db.get(Zone, mr.zone_id)
    gen_user = db.get(User, mr.generated_by)

    active_pole, active_lamp = _get_active_source_pair(
        db, customer_id=mr.customer_id, region_id=mr.region_id, zone_id=mr.zone_id
    )
    active_pole_ver = active_pole.version if active_pole else None
    active_lamp_ver = active_lamp.version if active_lamp else None

    is_outdated = (
        mr.status == "outdated"
        or active_pole_ver != mr.source_pole_survey_version
        or active_lamp_ver != mr.source_lamp_installation_version
    )

    versions_out: list[MergedReportVersionOut] = []
    for v in sorted(mr.versions, key=lambda x: x.version, reverse=True):
        if not is_admin and v.status != "published":
            continue
        v_user = db.get(User, v.generated_by)
        versions_out.append(
            MergedReportVersionOut(
                id=v.id,
                version=v.version,
                file_size=v.file_size,
                source_pole_survey_version=v.source_pole_survey_version,
                source_lamp_installation_version=v.source_lamp_installation_version,
                status=v.status,
                generated_by=v.generated_by,
                generated_by_name=v_user.name if v_user else None,
                generated_at=v.generated_at,
                published_by=v.published_by,
                published_at=v.published_at,
            )
        )

    pub_versions = [v for v in mr.versions if v.status == "published"]
    latest_pub_ver = max(pub_versions, key=lambda x: x.version, default=None)

    if not is_admin and latest_pub_ver is not None:
        latest_log = db.scalar(
            select(ProcessingLog)
            .where(ProcessingLog.merged_report_version_id == latest_pub_ver.id)
            .order_by(ProcessingLog.created_at.desc())
            .limit(1)
        )
    else:
        latest_log = db.scalar(
            select(ProcessingLog)
            .where(ProcessingLog.merged_report_id == mr.id)
            .order_by(ProcessingLog.created_at.desc())
            .limit(1)
        )
    summary_out: ProcessingSummaryOut | None = None
    if latest_log is not None:
        summary_out = ProcessingSummaryOut(
            total_lamp_installation_records=latest_log.total_lamp_installation_records,
            total_survey_records=latest_log.total_survey_records,
            total_led_records=latest_log.total_led_records,
            unique_eligible_led_records=latest_log.unique_eligible_led_records,
            existing_records=latest_log.existing_records,
            added_records=latest_log.added_records,
            duplicate_records=latest_log.duplicate_records,
            invalid_records=latest_log.invalid_records,
            unknown_lamp_type_records=latest_log.unknown_lamp_type_records,
            final_merged_records=latest_log.final_merged_records,
            processing_status=latest_log.processing_status,
            warnings=latest_log.warnings_json or [],
            error_message=latest_log.error_message,
        )

    display_status = mr.status
    display_version = mr.current_version
    display_source_ps_ver = mr.source_pole_survey_version
    display_source_li_ver = mr.source_lamp_installation_version
    if not is_admin:
        display_status = "published"
        if latest_pub_ver is not None:
            display_version = latest_pub_ver.version
            display_source_ps_ver = latest_pub_ver.source_pole_survey_version
            display_source_li_ver = latest_pub_ver.source_lamp_installation_version

    return MergedReportOut(
        id=mr.id,
        customer_id=mr.customer_id,
        customer_name=cust.customer_name if cust else "",
        region_id=mr.region_id,
        region_name=reg.region_name if reg else "",
        zone_id=mr.zone_id,
        zone_name=zone.zone_name if zone else "",
        current_version=display_version,
        status=display_status,
        is_outdated=is_outdated if is_admin else False,
        source_pole_survey_version=display_source_ps_ver,
        source_lamp_installation_version=display_source_li_ver,
        active_pole_survey_version=active_pole_ver,
        active_lamp_installation_version=active_lamp_ver,
        generated_by=mr.generated_by,
        generated_by_name=gen_user.name if gen_user else None,
        generated_at=mr.generated_at,
        published_by=mr.published_by,
        published_at=mr.published_at,
        latest_summary=summary_out,
        versions=versions_out,
    )


def generate_merged_report(
    db: Session,
    *,
    payload: MergedReportGenerateRequest,
    user_id: int,
    ip_address: str | None,
) -> MergedReportPreviewOut:
    validate_zone_hierarchy(
        db,
        customer_id=payload.customer_id,
        region_id=payload.region_id,
        zone_id=payload.zone_id,
    )
    pole_file, lamp_file = _get_active_source_pair(
        db,
        customer_id=payload.customer_id,
        region_id=payload.region_id,
        zone_id=payload.zone_id,
    )
    if pole_file is None or lamp_file is None:
        missing = []
        if pole_file is None:
            missing.append("Pole Survey Report")
        if lamp_file is None:
            missing.append("Lamp Installation Report")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot generate Merged Report: missing {' and '.join(missing)} for this zone.",
        )

    pole_abs = storage_service.get_absolute_path(pole_file.storage_path)
    lamp_abs = storage_service.get_absolute_path(lamp_file.storage_path)

    p_insp, p_rows = inspect_workbook(
        pole_abs,
        sheet_name=payload.pole_survey_mapping.sheet_name or pole_file.sheet_name,
        header_row_index=payload.pole_survey_mapping.header_row_index or pole_file.header_row_index,
    )
    l_insp, l_rows = inspect_workbook(
        lamp_abs,
        sheet_name=payload.lamp_installation_mapping.sheet_name or lamp_file.sheet_name,
        header_row_index=payload.lamp_installation_mapping.header_row_index or lamp_file.header_row_index,
    )

    active_rules = db.scalars(
        select(LedClassificationRule).where(LedClassificationRule.is_active.is_(True))
    ).all()
    classifier = LedClassifier(
        [
            RuleSpec(r.pattern, r.match_type, r.classification)
            for r in active_rules
        ]
        if active_rules
        else None
    )

    survey_map_spec = MappingSpec(
        pole_number_col=payload.pole_survey_mapping.pole_number_col,
        arm_count_col=payload.pole_survey_mapping.arm_count_col,
        lamp_type_col=payload.pole_survey_mapping.lamp_type_col,
        extra_mappings=payload.pole_survey_mapping.extra_mappings,
    )
    lamp_map_spec = MappingSpec(
        pole_number_col=payload.lamp_installation_mapping.pole_number_col,
        arm_count_col=payload.lamp_installation_mapping.arm_count_col,
        lamp_type_col=payload.lamp_installation_mapping.lamp_type_col,
    )

    existing_mr = db.scalar(
        select(MergedReport)
        .options(selectinload(MergedReport.versions))
        .where(
            MergedReport.customer_id == payload.customer_id,
            MergedReport.region_id == payload.region_id,
            MergedReport.zone_id == payload.zone_id,
        )
    )

    try:
        result = reconcile_reports(
            lamp_headers=l_insp.headers,
            lamp_rows=l_rows,
            lamp_mapping=lamp_map_spec,
            survey_headers=p_insp.headers,
            survey_rows=p_rows,
            survey_mapping=survey_map_spec,
            classifier=classifier,
        )
    except ReconciliationValidationError as exc:
        # Persist failed processing log for visibility & auditability
        db.add(
            ProcessingLog(
                merged_report_id=existing_mr.id if existing_mr else None,
                customer_id=payload.customer_id,
                region_id=payload.region_id,
                zone_id=payload.zone_id,
                total_lamp_installation_records=len(l_rows),
                total_survey_records=len(p_rows),
                processing_status="failed",
                error_message=str(exc),
            )
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    next_version = (existing_mr.current_version + 1) if existing_mr is not None else 1

    all_warnings = [*p_insp.warnings, *l_insp.warnings, *result.warnings]

    with storage_service.temp_workspace() as work_dir:
        temp_out = work_dir / f"merged_v{next_version}.xlsx"
        writer_warnings = write_merged_workbook(
            master_path=lamp_abs,
            output_path=temp_out,
            sheet_name=l_insp.active_sheet,
            header_row_index=l_insp.header_row_index,
            header_col_map=l_insp.header_col_map,
            last_data_row_index=l_insp.last_data_row_index,
            has_footer_rows=l_insp.has_footer_rows,
            newly_added_records=result.newly_added_records,
        )
        all_warnings.extend(writer_warnings)

        rel_xlsx_path, out_file_size = storage_service.copy_temp_file_to_storage(
            src_path=temp_out,
            customer_id=payload.customer_id,
            region_id=payload.region_id,
            zone_id=payload.zone_id,
            category="merged_reports",
            version=next_version,
            extension=".xlsx",
        )

    # Save clean JSON preview snapshot for fast 6-tab inspection
    serializable_added = [
        {k: v for k, v in rec.items() if k != "_raw_mapped_values"}
        for rec in result.newly_added_records
    ]
    preview_payload = {
        "lamp_columns": l_insp.headers,
        "summary": {**result.summary, "warnings": all_warnings},
        "existing_lamp_records": result.existing_lamp_records,
        "newly_added_records": serializable_added,
        "skipped_existing_records": result.skipped_existing_records,
        "duplicate_records": result.duplicate_records,
        "invalid_records": result.invalid_records,
        "unknown_lamp_types": result.unknown_lamp_types,
    }
    rel_preview_path = storage_service.save_json_bytes(
        customer_id=payload.customer_id,
        region_id=payload.region_id,
        zone_id=payload.zone_id,
        category="merged_previews",
        version=next_version,
        content=json.dumps(preview_payload, ensure_ascii=False).encode("utf-8"),
    )

    if payload.save_mapping:
        _upsert_saved_mapping(
            db,
            customer_id=payload.customer_id,
            report_type="pole_survey",
            signature_hash=p_insp.header_signature_hash,
            sheet_name=p_insp.active_sheet,
            header_row_index=p_insp.header_row_index,
            mapping_config=payload.pole_survey_mapping.model_dump(),
            user_id=user_id,
        )
        _upsert_saved_mapping(
            db,
            customer_id=payload.customer_id,
            report_type="lamp_installation",
            signature_hash=l_insp.header_signature_hash,
            sheet_name=l_insp.active_sheet,
            header_row_index=l_insp.header_row_index,
            mapping_config=payload.lamp_installation_mapping.model_dump(),
            user_id=user_id,
        )

    if existing_mr is None:
        mr = MergedReport(
            customer_id=payload.customer_id,
            region_id=payload.region_id,
            zone_id=payload.zone_id,
            current_version=1,
            status="draft",
            generated_file_path=rel_xlsx_path,
            source_pole_survey_file_id=pole_file.id,
            source_pole_survey_version=pole_file.version,
            source_lamp_installation_file_id=lamp_file.id,
            source_lamp_installation_version=lamp_file.version,
            generated_by=user_id,
        )
        db.add(mr)
        db.flush()
    else:
        mr = existing_mr
        mr.current_version = next_version
        mr.status = "draft"
        mr.generated_file_path = rel_xlsx_path
        mr.source_pole_survey_file_id = pole_file.id
        mr.source_pole_survey_version = pole_file.version
        mr.source_lamp_installation_file_id = lamp_file.id
        mr.source_lamp_installation_version = lamp_file.version
        mr.generated_by = user_id

    mrv = MergedReportVersion(
        merged_report_id=mr.id,
        version=next_version,
        generated_file_path=rel_xlsx_path,
        file_size=out_file_size,
        source_pole_survey_version=pole_file.version,
        source_lamp_installation_version=lamp_file.version,
        status="draft",
        preview_snapshot_path=rel_preview_path,
        generated_by=user_id,
    )
    db.add(mrv)
    db.flush()

    proc_status = "warning" if all_warnings else "success"
    db.add(
        ProcessingLog(
            merged_report_id=mr.id,
            merged_report_version_id=mrv.id,
            customer_id=payload.customer_id,
            region_id=payload.region_id,
            zone_id=payload.zone_id,
            total_lamp_installation_records=result.summary["total_lamp_installation_records"],
            total_survey_records=result.summary["total_survey_records"],
            total_led_records=result.summary["total_led_records"],
            unique_eligible_led_records=result.summary["unique_eligible_led_records"],
            existing_records=result.summary["existing_records"],
            added_records=result.summary["added_records"],
            duplicate_records=result.summary["duplicate_records"],
            invalid_records=result.summary["invalid_records"],
            unknown_lamp_type_records=result.summary["unknown_lamp_type_records"],
            final_merged_records=result.summary["final_merged_records"],
            warnings_json=all_warnings,
            processing_status=proc_status,
        )
    )

    record_audit_log(
        db,
        user_id=user_id,
        action="merged_report.generate",
        entity_type="merged_report",
        entity_id=mr.id,
        details={
            "zone_id": payload.zone_id,
            "version": next_version,
            "added_records": result.summary["added_records"],
            "existing_records": result.summary["existing_records"],
        },
        ip_address=ip_address,
    )
    db.commit()

    refreshed = db.scalar(
        select(MergedReport)
        .options(selectinload(MergedReport.versions))
        .where(MergedReport.id == mr.id)
    )
    mr_out = _serialize_merged_report(db, refreshed, is_admin=True)
    summary_out = ProcessingSummaryOut(
        **{k: v for k, v in result.summary.items() if k != "non_led_records"},
        non_led_records=result.summary["non_led_records"],
        processing_status=proc_status,
        warnings=all_warnings,
    )

    return MergedReportPreviewOut(
        merged_report=mr_out,
        summary=summary_out,
        lamp_columns=l_insp.headers,
        existing_lamp_records=result.existing_lamp_records,
        newly_added_records=serializable_added,
        skipped_existing_records=result.skipped_existing_records,
        duplicate_records=result.duplicate_records,
        invalid_records=result.invalid_records,
        unknown_lamp_types=result.unknown_lamp_types,
    )


def list_merged_reports(
    db: Session,
    *,
    auth: AuthContext,
    customer_id: int | None = None,
    region_id: int | None = None,
    zone_id: int | None = None,
) -> list[MergedReportOut]:
    is_admin = auth.user.role == "admin"
    stmt = (
        select(MergedReport)
        .options(selectinload(MergedReport.versions))
        .order_by(MergedReport.generated_at.desc())
    )
    if customer_id is not None:
        verify_customer_access(auth, customer_id)
        stmt = stmt.where(MergedReport.customer_id == customer_id)
    elif auth.authorized_customer_ids is not None:
        if not auth.authorized_customer_ids:
            return []
        stmt = stmt.where(MergedReport.customer_id.in_(auth.authorized_customer_ids))

    if region_id is not None:
        stmt = stmt.where(MergedReport.region_id == region_id)
    if zone_id is not None:
        stmt = stmt.where(MergedReport.zone_id == zone_id)

    if not is_admin:
        # Customers see only reports that have a published version
        stmt = stmt.where(MergedReport.published_at.is_not(None))

    rows = db.scalars(stmt).all()
    return [_serialize_merged_report(db, r, is_admin=is_admin) for r in rows]


def _get_merged_report_authorized(
    db: Session, *, auth: AuthContext, merged_id: int
) -> MergedReport:
    mr = db.scalar(
        select(MergedReport)
        .options(selectinload(MergedReport.versions))
        .where(MergedReport.id == merged_id)
    )
    if mr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merged Report not found.")
    verify_customer_access(auth, mr.customer_id)
    if auth.user.role != "admin" and mr.published_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This Merged Report has not been published yet.",
        )
    return mr


def get_merged_report_detail(
    db: Session, *, auth: AuthContext, merged_id: int
) -> MergedReportOut:
    mr = _get_merged_report_authorized(db, auth=auth, merged_id=merged_id)
    return _serialize_merged_report(db, mr, is_admin=auth.user.role == "admin")


def preview_merged_report(
    db: Session,
    *,
    auth: AuthContext,
    merged_id: int,
    version: int | None = None,
) -> MergedReportPreviewOut:
    mr = _get_merged_report_authorized(db, auth=auth, merged_id=merged_id)
    is_admin = auth.user.role == "admin"

    if version is not None:
        ver = next((v for v in mr.versions if v.version == version), None)
    elif is_admin:
        ver = next((v for v in mr.versions if v.version == mr.current_version), None)
    else:
        # Customer sees latest published version
        pub_versions = [v for v in mr.versions if v.status == "published"]
        ver = max(pub_versions, key=lambda x: x.version, default=None)

    if ver is None or (not is_admin and ver.status != "published"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merged Report version preview is unavailable.",
        )

    if not ver.preview_snapshot_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preview snapshot not found for this Merged Report version.",
        )

    snap_abs = storage_service.get_absolute_path(ver.preview_snapshot_path)
    data = json.loads(snap_abs.read_text(encoding="utf-8"))
    raw_sum = data.get("summary", {})
    summary_out = ProcessingSummaryOut(
        total_lamp_installation_records=raw_sum.get("total_lamp_installation_records", 0),
        total_survey_records=raw_sum.get("total_survey_records", 0),
        total_led_records=raw_sum.get("total_led_records", 0),
        unique_eligible_led_records=raw_sum.get("unique_eligible_led_records", 0),
        existing_records=raw_sum.get("existing_records", 0),
        added_records=raw_sum.get("added_records", 0),
        duplicate_records=raw_sum.get("duplicate_records", 0),
        invalid_records=raw_sum.get("invalid_records", 0),
        unknown_lamp_type_records=raw_sum.get("unknown_lamp_type_records", 0),
        non_led_records=raw_sum.get("non_led_records", 0),
        final_merged_records=raw_sum.get("final_merged_records", 0),
        processing_status="warning" if raw_sum.get("warnings") else "success",
        warnings=raw_sum.get("warnings", []),
    )

    return MergedReportPreviewOut(
        merged_report=_serialize_merged_report(db, mr, is_admin=is_admin),
        summary=summary_out,
        lamp_columns=data.get("lamp_columns", []),
        existing_lamp_records=data.get("existing_lamp_records", []),
        newly_added_records=data.get("newly_added_records", []),
        skipped_existing_records=data.get("skipped_existing_records", []),
        duplicate_records=data.get("duplicate_records", []),
        invalid_records=data.get("invalid_records", []),
        unknown_lamp_types=data.get("unknown_lamp_types", []),
    )


def publish_merged_report(
    db: Session,
    *,
    merged_id: int,
    user_id: int,
    ip_address: str | None,
) -> MergedReportOut:
    mr = db.scalar(
        select(MergedReport)
        .options(selectinload(MergedReport.versions))
        .where(MergedReport.id == merged_id)
    )
    if mr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merged Report not found.")
    if mr.status == "failed" or not mr.generated_file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot publish a failed or incomplete Merged Report.",
        )

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    # Mark older published versions as superseded
    for v in mr.versions:
        if v.version == mr.current_version:
            v.status = "published"
            v.published_by = user_id
            v.published_at = now
        elif v.status == "published":
            v.status = "superseded"

    mr.status = "published"
    mr.published_by = user_id
    mr.published_at = now

    record_audit_log(
        db,
        user_id=user_id,
        action="merged_report.publish",
        entity_type="merged_report",
        entity_id=mr.id,
        details={"version": mr.current_version, "zone_id": mr.zone_id},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(mr)
    return _serialize_merged_report(db, mr, is_admin=True)


def download_merged_report(
    db: Session,
    *,
    auth: AuthContext,
    merged_id: int,
    version: int | None = None,
    ip_address: str | None = None,
) -> FileResponse:
    mr = _get_merged_report_authorized(db, auth=auth, merged_id=merged_id)
    is_admin = auth.user.role == "admin"

    if version is not None:
        ver = next((v for v in mr.versions if v.version == version), None)
    elif is_admin:
        ver = next((v for v in mr.versions if v.version == mr.current_version), None)
    else:
        pub_versions = [v for v in mr.versions if v.status == "published"]
        ver = max(pub_versions, key=lambda x: x.version, default=None)

    if ver is None or not ver.generated_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated Merged Report file not found.",
        )
    if not is_admin and ver.status != "published":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only published Merged Reports can be downloaded by customers.",
        )

    abs_path = storage_service.get_absolute_path(ver.generated_file_path)
    zone = db.get(Zone, mr.zone_id)
    safe_zone = (zone.zone_name if zone else f"zone_{mr.zone_id}").replace(" ", "_")
    download_name = f"Merged_Report_{safe_zone}_v{ver.version}.xlsx"

    record_audit_log(
        db,
        user_id=auth.user.id,
        action="merged_report.download",
        entity_type="merged_report",
        entity_id=mr.id,
        details={"version": ver.version, "filename": download_name},
        ip_address=ip_address,
    )
    db.commit()

    return FileResponse(
        path=str(abs_path),
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
