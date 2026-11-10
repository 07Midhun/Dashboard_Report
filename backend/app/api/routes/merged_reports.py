from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import AuthContext, get_client_ip, get_current_auth, require_admin
from app.database.session import get_db
from app.schemas.reports import (
    MergedReportGenerateRequest,
    MergedReportInspectOut,
    MergedReportOut,
    MergedReportPreviewOut,
)
from app.services.merged_report_service import (
    download_merged_report,
    generate_merged_report,
    get_merged_report_detail,
    inspect_ward_sources,
    list_merged_reports,
    preview_merged_report,
    publish_merged_report,
)


router = APIRouter(prefix="/merged-reports", tags=["Merged Reports"])


@router.get("/inspect", response_model=MergedReportInspectOut)
def inspect_sources(
    customer_id: int = Query(...),
    region_id: int = Query(...),
    zone_id: int = Query(...),
    ward_id: int = Query(...),
    pole_sheet: str | None = Query(default=None),
    pole_header_row: int | None = Query(default=None),
    lamp_sheet: str | None = Query(default=None),
    lamp_header_row: int | None = Query(default=None),
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MergedReportInspectOut:
    return inspect_ward_sources(
        db,
        customer_id=customer_id,
        region_id=region_id,
        zone_id=zone_id,
        ward_id=ward_id,
        pole_sheet=pole_sheet,
        pole_header_row=pole_header_row,
        lamp_sheet=lamp_sheet,
        lamp_header_row=lamp_header_row,
    )


@router.post("/generate", response_model=MergedReportPreviewOut, status_code=status.HTTP_201_CREATED)
def generate_report(
    payload: MergedReportGenerateRequest,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MergedReportPreviewOut:
    return generate_merged_report(
        db,
        payload=payload,
        user_id=auth.user.id,
        ip_address=get_client_ip(request),
    )


@router.get("", response_model=list[MergedReportOut])
def get_merged_reports(
    customer_id: int | None = Query(default=None),
    region_id: int | None = Query(default=None),
    zone_id: int | None = Query(default=None),
    ward_id: int | None = Query(default=None),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[MergedReportOut]:
    return list_merged_reports(
        db,
        auth=auth,
        customer_id=customer_id,
        region_id=region_id,
        zone_id=zone_id,
        ward_id=ward_id,
    )


@router.get("/{merged_id}", response_model=MergedReportOut)
def get_merged_report(
    merged_id: int,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> MergedReportOut:
    return get_merged_report_detail(db, auth=auth, merged_id=merged_id)


@router.get("/{merged_id}/preview", response_model=MergedReportPreviewOut)
def get_merged_preview(
    merged_id: int,
    version: int | None = Query(default=None),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> MergedReportPreviewOut:
    return preview_merged_report(db, auth=auth, merged_id=merged_id, version=version)


@router.get("/{merged_id}/download")
def download_merged(
    merged_id: int,
    request: Request,
    version: int | None = Query(default=None),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    return download_merged_report(
        db,
        auth=auth,
        merged_id=merged_id,
        version=version,
        ip_address=get_client_ip(request),
    )


@router.post("/{merged_id}/publish", response_model=MergedReportOut)
def publish_merged(
    merged_id: int,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MergedReportOut:
    return publish_merged_report(
        db,
        merged_id=merged_id,
        user_id=auth.user.id,
        ip_address=get_client_ip(request),
    )

