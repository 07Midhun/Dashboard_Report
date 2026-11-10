from pathlib import Path
from typing import Literal
from fastapi import HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.dependencies import AuthContext, verify_customer_access
from app.models.hierarchy import Customer, Region, Ward, Zone
from app.models.report import MergedReport, ReportFile, ReportFileVersion
from app.models.user import User
from app.schemas.reports import ExcelPreviewOut, ReportFileOut, ReportFileVersionOut
from app.services.audit_service import record_audit_log
from app.services.excel_reader_service import inspect_workbook, preview_workbook
from app.services.hierarchy_service import validate_ward_hierarchy
from app.services.storage_service import storage_service
from app.utilities.file_validators import validate_excel_upload


ReportTypeLiteral = Literal["pole_survey", "lamp_installation"]


def _serialize_report_file(db: Session, rf: ReportFile) -> ReportFileOut:
    cust = db.get(Customer, rf.customer_id)
    reg = db.get(Region, rf.region_id)
    zone = db.get(Zone, rf.zone_id)
    ward = db.get(Ward, rf.ward_id)
    uploader = db.get(User, rf.uploaded_by)

    versions_out: list[ReportFileVersionOut] = []
    for v in sorted(rf.versions, key=lambda x: x.version, reverse=True):
        v_user = db.get(User, v.uploaded_by)
        versions_out.append(
            ReportFileVersionOut(
                id=v.id,
                version=v.version,
                original_filename=v.original_filename,
                file_size=v.file_size,
                checksum_sha256=v.checksum_sha256,
                sheet_name=v.sheet_name,
                header_row_index=v.header_row_index,
                row_count=v.row_count,
                uploaded_by=v.uploaded_by,
                uploaded_by_name=v_user.name if v_user else None,
                uploaded_at=v.uploaded_at,
            )
        )

    return ReportFileOut(
        id=rf.id,
        customer_id=rf.customer_id,
        customer_name=cust.customer_name if cust else "",
        region_id=rf.region_id,
        region_name=reg.region_name if reg else "",
        zone_id=rf.zone_id,
        zone_name=zone.zone_name if zone else "",
        zone_code=zone.zone_code if zone else None,
        ward_id=rf.ward_id,
        ward_name=ward.ward_name if ward else "",
        ward_number=ward.ward_number if ward else "",
        ward_code=ward.ward_code if ward else "",
        report_type=rf.report_type,
        original_filename=rf.original_filename,
        file_size=rf.file_size,
        file_extension=rf.file_extension,
        sheet_name=rf.sheet_name,
        header_row_index=rf.header_row_index,
        row_count=rf.row_count,
        version=rf.version,
        status=rf.status,
        uploaded_by=rf.uploaded_by,
        uploaded_by_name=uploader.name if uploader else None,
        uploaded_at=rf.uploaded_at,
        updated_at=rf.updated_at,
        versions=versions_out,
    )


def upload_report_file(
    db: Session,
    *,
    customer_id: int,
    region_id: int,
    zone_id: int,
    ward_id: int,
    report_type: ReportTypeLiteral,
    filename: str,
    content: bytes,
    replace_existing: bool,
    user_id: int,
    ip_address: str | None,
) -> ReportFileOut:
    validate_ward_hierarchy(
        db,
        customer_id=customer_id,
        region_id=region_id,
        zone_id=zone_id,
        ward_id=ward_id,
    )
    safe_name, ext, sha256_hex = validate_excel_upload(filename, content)

    existing = db.scalar(
        select(ReportFile)
        .options(selectinload(ReportFile.versions))
        .where(
            ReportFile.customer_id == customer_id,
            ReportFile.region_id == region_id,
            ReportFile.zone_id == zone_id,
            ReportFile.ward_id == ward_id,
            ReportFile.report_type == report_type,
            ReportFile.status == "active",
        )
    )

    if existing is not None and not replace_existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An active {report_type.replace('_', ' ')} file already exists for this ward. Confirm replacement to upload a new version.",
        )

    # Validate workbook structure inside an isolated temp workspace before persisting
    with storage_service.temp_workspace() as work_dir:
        temp_path = work_dir / f"validate{ext}"
        temp_path.write_bytes(content)
        inspection, _ = inspect_workbook(temp_path)

    next_version = (existing.version + 1) if existing is not None else 1
    rel_storage_path = storage_service.save_report_bytes(
        customer_id=customer_id,
        region_id=region_id,
        zone_id=zone_id,
        ward_id=ward_id,
        category=report_type,
        version=next_version,
        extension=ext,
        content=content,
    )

    if existing is None:
        rf = ReportFile(
            customer_id=customer_id,
            region_id=region_id,
            zone_id=zone_id,
            ward_id=ward_id,
            report_type=report_type,
            original_filename=safe_name,
            storage_path=rel_storage_path,
            file_size=len(content),
            file_extension=ext,
            checksum_sha256=sha256_hex,
            sheet_name=inspection.active_sheet,
            header_row_index=inspection.header_row_index,
            row_count=inspection.total_data_rows,
            version=1,
            status="active",
            uploaded_by=user_id,
        )
        db.add(rf)
        db.flush()
    else:
        rf = existing
        rf.original_filename = safe_name
        rf.storage_path = rel_storage_path
        rf.file_size = len(content)
        rf.file_extension = ext
        rf.checksum_sha256 = sha256_hex
        rf.sheet_name = inspection.active_sheet
        rf.header_row_index = inspection.header_row_index
        rf.row_count = inspection.total_data_rows
        rf.version = next_version
        rf.uploaded_by = user_id

    version_row = ReportFileVersion(
        report_file_id=rf.id,
        ward_id=ward_id,
        version=next_version,
        original_filename=safe_name,
        storage_path=rel_storage_path,
        file_size=len(content),
        file_extension=ext,
        checksum_sha256=sha256_hex,
        sheet_name=inspection.active_sheet,
        header_row_index=inspection.header_row_index,
        row_count=inspection.total_data_rows,
        uploaded_by=user_id,
    )
    db.add(version_row)

    # Mark any existing merged report for this specific ward as outdated when source changes
    merged = db.scalar(
        select(MergedReport).where(
            MergedReport.customer_id == customer_id,
            MergedReport.region_id == region_id,
            MergedReport.zone_id == zone_id,
            MergedReport.ward_id == ward_id,
        )
    )
    if merged is not None and merged.status in {"draft", "published"}:
        merged.status = "outdated"

    record_audit_log(
        db,
        user_id=user_id,
        action=f"{report_type}.upload",
        entity_type="report_file",
        entity_id=rf.id,
        details={
            "zone_id": zone_id,
            "ward_id": ward_id,
            "filename": safe_name,
            "version": next_version,
            "row_count": inspection.total_data_rows,
        },
        ip_address=ip_address,
    )
    db.commit()

    refreshed = db.scalar(
        select(ReportFile)
        .options(selectinload(ReportFile.versions))
        .where(ReportFile.id == rf.id)
    )
    return _serialize_report_file(db, refreshed)


def list_report_files(
    db: Session,
    *,
    auth: AuthContext,
    report_type: ReportTypeLiteral,
    customer_id: int | None = None,
    region_id: int | None = None,
    zone_id: int | None = None,
    ward_id: int | None = None,
    include_deleted: bool = False,
) -> list[ReportFileOut]:
    stmt = (
        select(ReportFile)
        .options(selectinload(ReportFile.versions))
        .where(ReportFile.report_type == report_type)
        .order_by(ReportFile.uploaded_at.desc())
    )
    if not include_deleted or auth.user.role != "admin":
        stmt = stmt.where(ReportFile.status == "active")

    if customer_id is not None:
        verify_customer_access(auth, customer_id)
        stmt = stmt.where(ReportFile.customer_id == customer_id)
    elif auth.authorized_customer_ids is not None:
        if not auth.authorized_customer_ids:
            return []
        stmt = stmt.where(ReportFile.customer_id.in_(auth.authorized_customer_ids))

    if region_id is not None:
        stmt = stmt.where(ReportFile.region_id == region_id)
    if zone_id is not None:
        stmt = stmt.where(ReportFile.zone_id == zone_id)
    if ward_id is not None:
        stmt = stmt.where(ReportFile.ward_id == ward_id)

    items = db.scalars(stmt).all()
    return [_serialize_report_file(db, item) for item in items]


def get_report_file_authorized(
    db: Session,
    *,
    auth: AuthContext,
    report_id: int,
    expected_type: ReportTypeLiteral,
) -> ReportFile:
    rf = db.scalar(
        select(ReportFile)
        .options(selectinload(ReportFile.versions))
        .where(ReportFile.id == report_id, ReportFile.report_type == expected_type)
    )
    if rf is None or (rf.status != "active" and auth.user.role != "admin"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requested report file was not found.",
        )
    verify_customer_access(auth, rf.customer_id)
    return rf


def get_report_file_detail(
    db: Session,
    *,
    auth: AuthContext,
    report_id: int,
    expected_type: ReportTypeLiteral,
) -> ReportFileOut:
    rf = get_report_file_authorized(
        db, auth=auth, report_id=report_id, expected_type=expected_type
    )
    return _serialize_report_file(db, rf)


def preview_report_file(
    db: Session,
    *,
    auth: AuthContext,
    report_id: int,
    expected_type: ReportTypeLiteral,
    version: int | None = None,
    sheet_name: str | None = None,
    header_row_index: int | None = None,
    search: str | None = None,
    filter_column: str | None = None,
    filter_value: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> ExcelPreviewOut:
    rf = get_report_file_authorized(
        db, auth=auth, report_id=report_id, expected_type=expected_type
    )
    target_storage_path = rf.storage_path
    target_filename = rf.original_filename
    target_version = rf.version
    default_sheet = rf.sheet_name
    default_header_row = rf.header_row_index

    if version is not None and version != rf.version:
        if auth.user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Historical file versions are restricted to administrators.",
            )
        ver = next((v for v in rf.versions if v.version == version), None)
        if ver is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requested version not found.")
        target_storage_path = ver.storage_path
        target_filename = ver.original_filename
        target_version = ver.version
        default_sheet = ver.sheet_name
        default_header_row = ver.header_row_index

    abs_path = storage_service.get_absolute_path(target_storage_path)
    preview_data = preview_workbook(
        abs_path,
        sheet_name=sheet_name or default_sheet,
        header_row_index=header_row_index or default_header_row,
        search=search,
        filter_column=filter_column,
        filter_value=filter_value,
        page=page,
        page_size=page_size,
    )

    return ExcelPreviewOut(
        report_id=rf.id,
        original_filename=target_filename,
        version=target_version,
        **preview_data,
    )


def download_report_file(
    db: Session,
    *,
    auth: AuthContext,
    report_id: int,
    expected_type: ReportTypeLiteral,
    version: int | None = None,
    ip_address: str | None = None,
) -> FileResponse:
    rf = get_report_file_authorized(
        db, auth=auth, report_id=report_id, expected_type=expected_type
    )
    target_storage_path = rf.storage_path
    target_filename = rf.original_filename
    target_version = rf.version

    if version is not None and version != rf.version:
        if auth.user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Historical file versions are restricted to administrators.",
            )
        ver = next((v for v in rf.versions if v.version == version), None)
        if ver is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requested version not found.")
        target_storage_path = ver.storage_path
        target_filename = ver.original_filename
        target_version = ver.version

    abs_path = storage_service.get_absolute_path(target_storage_path)
    record_audit_log(
        db,
        user_id=auth.user.id,
        action=f"{expected_type}.download",
        entity_type="report_file",
        entity_id=rf.id,
        details={"version": target_version, "filename": target_filename},
        ip_address=ip_address,
    )
    db.commit()

    media_type = (
        "application/vnd.ms-excel"
        if target_filename.lower().endswith(".xls")
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return FileResponse(
        path=str(abs_path),
        filename=target_filename,
        media_type=media_type,
    )


def delete_report_file(
    db: Session,
    *,
    report_id: int,
    expected_type: ReportTypeLiteral,
    user_id: int,
    ip_address: str | None,
) -> None:
    rf = db.get(ReportFile, report_id)
    if rf is None or rf.report_type != expected_type or rf.status == "deleted":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active report file not found.",
        )

    rf.status = "deleted"
    merged = db.scalar(
        select(MergedReport).where(
            MergedReport.customer_id == rf.customer_id,
            MergedReport.region_id == rf.region_id,
            MergedReport.zone_id == rf.zone_id,
            MergedReport.ward_id == rf.ward_id,
        )
    )
    if merged is not None and merged.status in {"draft", "published"}:
        merged.status = "outdated"

    record_audit_log(
        db,
        user_id=user_id,
        action=f"{expected_type}.delete",
        entity_type="report_file",
        entity_id=rf.id,
        details={
            "zone_id": rf.zone_id,
            "ward_id": rf.ward_id,
            "filename": rf.original_filename,
            "version": rf.version,
        },
        ip_address=ip_address,
    )
    db.commit()
