import io
import shutil
import zipfile
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
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
from app.services.storage_service import storage_service


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


@router.post("/storage-sync-file")
async def sync_storage_file(
    relative_path: str = Form(...),
    file: UploadFile = File(...),
    _: AuthContext = Depends(require_admin),
):
    clean_rel = relative_path.replace("\\", "/").lstrip("/")
    target_path = storage_service._resolve_relative(clean_rel)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    target_path.write_bytes(content)
    return {"status": "ok", "path": clean_rel, "bytes_written": len(content)}


@router.post("/storage-sync-zip")
async def sync_storage_zip(
    zip_file: UploadFile = File(...),
    _: AuthContext = Depends(require_admin),
):
    content = await zip_file.read()
    extracted_count = 0
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            clean_name = member.filename.replace("\\", "/").lstrip("/")
            try:
                dest_path = storage_service._resolve_relative(clean_name)
            except Exception:
                continue
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(dest_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted_count += 1
    return {"status": "ok", "files_extracted": extracted_count}


@router.post("/storage-remap-hierarchy")
def remap_storage_hierarchy(
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
):
    storage_root = storage_service.root

    # Map by zone code (BMH, CVRN, HEB, PN, SN, SNTR, SVJR)
    code_to_render_dest = {}
    render_zones = db.query(Zone).all()
    for z in render_zones:
        if z.zone_code:
            code_to_render_dest[z.zone_code.strip().upper()] = (z.customer_id, z.region_id, z.id)

    # Source zones from local storage
    local_source_zones = {
        "BMH": (1, 1, 1),
        "CVRN": (1, 2, 2),
        "HEB": (1, 2, 3),
        "PN": (1, 2, 4),
        "SN": (1, 2, 5),
        "SNTR": (1, 2, 6),
        "SVJR": (1, 2, 7),
    }

    copied_wards = 0
    for code, (src_c, src_r, src_z) in local_source_zones.items():
        if code in code_to_render_dest:
            dst_c, dst_r, dst_z = code_to_render_dest[code]
            src_dir = storage_root / "customers" / str(src_c) / "regions" / str(src_r) / "zones" / str(src_z) / "wards"
            dst_dir = storage_root / "customers" / str(dst_c) / "regions" / str(dst_r) / "zones" / str(dst_z) / "wards"
            if src_dir.exists():
                dst_dir.mkdir(parents=True, exist_ok=True)
                for ward_item in src_dir.iterdir():
                    target_ward = dst_dir / ward_item.name
                    if ward_item.is_dir():
                        shutil.copytree(ward_item, target_ward, dirs_exist_ok=True)
                        copied_wards += 1

    return {"status": "ok", "wards_mapped": copied_wards}


@router.get("/storage-diagnostics")
def get_storage_diagnostics(
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
):
    storage_root = storage_service.root
    active_files = db.query(ReportFile).filter(ReportFile.status == "active").all()
    results = []
    for rf in active_files[:25]:
        abs_p = storage_root / rf.storage_path
        results.append({
            "id": rf.id,
            "report_type": rf.report_type,
            "ward_id": rf.ward_id,
            "filename": rf.original_filename,
            "storage_path": rf.storage_path,
            "exists": abs_p.exists(),
        })

    # Sample top level directories and files
    top_entries = []
    if storage_root.exists():
        for item in sorted(storage_root.rglob("*"))[:40]:
            if item.is_file():
                top_entries.append(str(item.relative_to(storage_root)).replace("\\", "/"))

    from app.models.report import MergedReport
    merged_reports = db.query(MergedReport).all()
    mr_results = []
    for mr in merged_reports[:15]:
        gen_exists = (storage_root / mr.generated_file_path).exists() if mr.generated_file_path else False
        mr_results.append({
            "id": mr.id,
            "ward_id": mr.ward_id,
            "status": mr.status,
            "version": mr.current_version,
            "generated_file_path": mr.generated_file_path,
            "exists": gen_exists,
        })

    return {
        "storage_root": str(storage_root),
        "exists": storage_root.exists(),
        "total_active_rf": len(active_files),
        "sample_files": results,
        "total_merged_reports": len(merged_reports),
        "sample_merged_reports": mr_results,
        "sample_disk_entries": top_entries,
    }


@router.post("/storage-sync-reconcile")
def reconcile_storage_files(
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
):
    """
    Reconciles physical files on disk with ReportFile and MergedReport records in the database.
    If a database record expects a specific random-UUID filename in its ward directory,
    this endpoint locates the corresponding uploaded report in that ward directory and copies
    it to the exact path the database expects.
    """
    storage_root = storage_service.root
    reconciled_files = 0
    reconciled_reports = 0

    # 1. Reconcile ReportFiles and ReportFileVersions
    active_files = db.query(ReportFile).filter(ReportFile.status == "active").all()
    for rf in active_files:
        target_path = storage_root / rf.storage_path
        if not target_path.exists():
            folder = target_path.parent
            if folder.exists():
                candidates = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in {".xlsx", ".xls"}]
                if candidates:
                    # Choose best matching candidate (e.g. by modification time or size)
                    best = sorted(candidates, key=lambda x: x.stat().st_mtime, reverse=True)[0]
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(best, target_path)
                    reconciled_files += 1

        for v in rf.versions:
            v_target = storage_root / v.storage_path
            if not v_target.exists():
                v_folder = v_target.parent
                if v_folder.exists():
                    v_candidates = [f for f in v_folder.iterdir() if f.is_file() and f.suffix.lower() in {".xlsx", ".xls"}]
                    if v_candidates:
                        best = sorted(v_candidates, key=lambda x: x.stat().st_mtime, reverse=True)[0]
                        v_target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(best, v_target)

    # 2. Reconcile MergedReport and MergedReportVersion
    from app.models.report import MergedReport, MergedReportVersion
    merged_reports = db.query(MergedReport).all()
    for mr in merged_reports:
        if mr.generated_file_path:
            mr_path = storage_root / mr.generated_file_path
            if not mr_path.exists():
                folder = mr_path.parent
                if folder.exists():
                    candidates = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() == ".xlsx"]
                    if candidates:
                        best = sorted(candidates, key=lambda x: x.stat().st_mtime, reverse=True)[0]
                        mr_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(best, mr_path)
                        reconciled_reports += 1

        for mv in mr.versions:
            if mv.generated_file_path:
                mv_path = storage_root / mv.generated_file_path
                if not mv_path.exists():
                    folder = mv_path.parent
                    if folder.exists():
                        candidates = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() == ".xlsx"]
                        if candidates:
                            best = sorted(candidates, key=lambda x: x.stat().st_mtime, reverse=True)[0]
                            mv_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(best, mv_path)

            if mv.preview_snapshot_path:
                prev_path = storage_root / mv.preview_snapshot_path
                if not prev_path.exists():
                    folder = prev_path.parent
                    if folder.exists():
                        candidates = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() == ".json"]
                        if candidates:
                            best = sorted(candidates, key=lambda x: x.stat().st_mtime, reverse=True)[0]
                            prev_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(best, prev_path)

    return {
        "status": "ok",
        "reconciled_report_files": reconciled_files,
        "reconciled_merged_reports": reconciled_reports,
    }





