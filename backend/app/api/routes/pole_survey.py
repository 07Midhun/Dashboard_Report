from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import AuthContext, get_client_ip, get_current_auth, require_admin
from app.database.session import get_db
from app.schemas.common import MessageResponse
from app.schemas.reports import ExcelPreviewOut, ReportFileOut
from app.services.report_file_service import (
    delete_report_file,
    download_report_file,
    get_report_file_detail,
    list_report_files,
    preview_report_file,
    upload_report_file,
)


router = APIRouter(prefix="/pole-survey", tags=["Pole Survey Reports"])


@router.post("/upload", response_model=ReportFileOut, status_code=status.HTTP_201_CREATED)
async def upload_pole_survey(
    request: Request,
    customer_id: int = Form(...),
    region_id: int = Form(...),
    zone_id: int = Form(...),
    ward_id: int = Form(...),
    replace_existing: bool = Form(default=False),
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ReportFileOut:
    content = await file.read()
    return upload_report_file(
        db,
        customer_id=customer_id,
        region_id=region_id,
        zone_id=zone_id,
        ward_id=ward_id,
        report_type="pole_survey",
        filename=file.filename or "pole_survey.xlsx",
        content=content,
        replace_existing=replace_existing,
        user_id=auth.user.id,
        ip_address=get_client_ip(request),
    )


@router.get("", response_model=list[ReportFileOut])
def list_pole_surveys(
    customer_id: int | None = Query(default=None),
    region_id: int | None = Query(default=None),
    zone_id: int | None = Query(default=None),
    ward_id: int | None = Query(default=None),
    include_deleted: bool = Query(default=False),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[ReportFileOut]:
    return list_report_files(
        db,
        auth=auth,
        report_type="pole_survey",
        customer_id=customer_id,
        region_id=region_id,
        zone_id=zone_id,
        ward_id=ward_id,
        include_deleted=include_deleted,
    )


@router.get("/{report_id}", response_model=ReportFileOut)
def get_pole_survey(
    report_id: int,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> ReportFileOut:
    return get_report_file_detail(db, auth=auth, report_id=report_id, expected_type="pole_survey")


@router.get("/{report_id}/preview", response_model=ExcelPreviewOut)
def preview_pole_survey(
    report_id: int,
    version: int | None = Query(default=None),
    sheet_name: str | None = Query(default=None),
    header_row_index: int | None = Query(default=None),
    search: str | None = Query(default=None),
    filter_column: str | None = Query(default=None),
    filter_value: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=250),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> ExcelPreviewOut:
    return preview_report_file(
        db,
        auth=auth,
        report_id=report_id,
        expected_type="pole_survey",
        version=version,
        sheet_name=sheet_name,
        header_row_index=header_row_index,
        search=search,
        filter_column=filter_column,
        filter_value=filter_value,
        page=page,
        page_size=page_size,
    )


@router.get("/{report_id}/download")
def download_pole_survey(
    report_id: int,
    request: Request,
    version: int | None = Query(default=None),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    return download_report_file(
        db,
        auth=auth,
        report_id=report_id,
        expected_type="pole_survey",
        version=version,
        ip_address=get_client_ip(request),
    )


@router.delete("/{report_id}", response_model=MessageResponse)
def remove_pole_survey(
    report_id: int,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    delete_report_file(
        db,
        report_id=report_id,
        expected_type="pole_survey",
        user_id=auth.user.id,
        ip_address=get_client_ip(request),
    )
    return MessageResponse(message="Pole Survey Report deleted successfully.")

