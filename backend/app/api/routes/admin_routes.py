from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import AuthContext, get_client_ip, require_admin
from app.database.session import get_db
from app.models.hierarchy import Customer, Region, Ward, Zone
from app.models.report import ReportFileVersion, ReportFile
from app.models.user import User
from app.schemas.admin import (
    AuditLogOut,
    LedRuleCreate,
    LedRuleOut,
    LedRuleUpdate,
    UserCreate,
    UserUpdate,
)
from app.schemas.auth import UserOut
from app.schemas.common import MessageResponse
from app.services.admin_service import (
    create_led_rule,
    create_user,
    delete_led_rule,
    list_audit_logs,
    list_led_rules,
    list_users,
    update_led_rule,
    update_user,
)


router = APIRouter(tags=["Administration"])


@router.get("/users", response_model=list[UserOut])
def get_users(
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[UserOut]:
    return list_users(db)


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def post_user(
    payload: UserCreate,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    return create_user(db, payload, auth.user.id, get_client_ip(request))


@router.put("/users/{user_id}", response_model=UserOut)
def put_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    return update_user(db, user_id, payload, auth.user.id, get_client_ip(request))


@router.get("/led-rules", response_model=list[LedRuleOut])
def get_led_rules(
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[LedRuleOut]:
    return list_led_rules(db)


@router.post("/led-rules", response_model=LedRuleOut, status_code=status.HTTP_201_CREATED)
def post_led_rule(
    payload: LedRuleCreate,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> LedRuleOut:
    return create_led_rule(db, payload, auth.user.id, get_client_ip(request))


@router.put("/led-rules/{rule_id}", response_model=LedRuleOut)
def put_led_rule(
    rule_id: int,
    payload: LedRuleUpdate,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> LedRuleOut:
    return update_led_rule(db, rule_id, payload, auth.user.id, get_client_ip(request))


@router.delete("/led-rules/{rule_id}", response_model=MessageResponse)
def remove_led_rule(
    rule_id: int,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    delete_led_rule(db, rule_id, auth.user.id, get_client_ip(request))
    return MessageResponse(message="LED classification rule deleted.")


@router.get("/audit-logs", response_model=list[AuditLogOut])
def get_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AuditLogOut]:
    return list_audit_logs(db, limit=limit)


@router.get("/upload-history")
def get_upload_history(
    report_type: str | None = Query(default=None),
    ward_id: int | None = Query(default=None),
    zone_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = (
        select(ReportFileVersion, ReportFile)
        .join(ReportFile, ReportFileVersion.report_file_id == ReportFile.id)
        .order_by(ReportFileVersion.uploaded_at.desc())
        .limit(limit)
    )
    if report_type in {"pole_survey", "lamp_installation"}:
        stmt = stmt.where(ReportFile.report_type == report_type)
    if zone_id is not None:
        stmt = stmt.where(ReportFile.zone_id == zone_id)
    if ward_id is not None:
        stmt = stmt.where(ReportFile.ward_id == ward_id)

    rows = db.execute(stmt).all()
    out: list[dict] = []
    for ver, rf in rows:
        c = db.get(Customer, rf.customer_id)
        r = db.get(Region, rf.region_id)
        z = db.get(Zone, rf.zone_id)
        w = db.get(Ward, rf.ward_id)
        u = db.get(User, ver.uploaded_by)
        out.append(
            {
                "id": ver.id,
                "report_file_id": rf.id,
                "report_type": rf.report_type,
                "customer_id": rf.customer_id,
                "customer_name": c.customer_name if c else "",
                "region_id": rf.region_id,
                "region_name": r.region_name if r else "",
                "zone_id": rf.zone_id,
                "zone_name": z.zone_name if z else "",
                "zone_code": z.zone_code if z else None,
                "ward_id": rf.ward_id,
                "ward_number": w.ward_number if w else "",
                "ward_name": w.ward_name if w else "",
                "ward_code": w.ward_code if w else "",
                "version": ver.version,
                "is_current": ver.version == rf.version and rf.status == "active",
                "file_status": rf.status,
                "original_filename": ver.original_filename,
                "file_size": ver.file_size,
                "row_count": ver.row_count,
                "uploaded_by_name": u.name if u else None,
                "uploaded_at": ver.uploaded_at,
            }
        )
    return out

