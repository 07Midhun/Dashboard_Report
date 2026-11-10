from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.dependencies import AuthContext, verify_customer_access
from app.models.hierarchy import Customer, Region, Ward, Zone
from app.models.report import MergedReport, ProcessingLog, ReportFile
from app.models.user import User
from app.schemas.reports import (
    AdminDashboardOut,
    CustomerDashboardOut,
    ProcessingActivityItem,
    RecentMergedItem,
    RecentUploadItem,
    RegionAvailabilityItem,
    ZoneAvailabilityItem,
)


def _validate_dashboard_filters(
    db: Session,
    *,
    auth: AuthContext | None = None,
    customer_id: int | None = None,
    region_id: int | None = None,
    zone_id: int | None = None,
) -> tuple[int | None, int | None, int | None]:
    if customer_id is not None and auth is not None:
        verify_customer_access(auth, customer_id)

    resolved_customer_id = customer_id
    resolved_region_id = region_id

    if region_id is not None:
        reg = db.get(Region, region_id)
        if reg is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found.")
        if auth is not None:
            verify_customer_access(auth, reg.customer_id)
        if customer_id is not None and reg.customer_id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected region does not belong to the selected customer.",
            )
        resolved_customer_id = resolved_customer_id or reg.customer_id

    if zone_id is not None:
        zone = db.scalar(select(Zone).options(selectinload(Zone.region)).where(Zone.id == zone_id))
        if zone is None or zone.region is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found.")
        if auth is not None:
            verify_customer_access(auth, zone.region.customer_id)
        if resolved_customer_id is not None and zone.region.customer_id != resolved_customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected zone does not belong to the selected customer.",
            )
        if resolved_region_id is not None and zone.region_id != resolved_region_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected zone does not belong to the selected region.",
            )
        resolved_customer_id = resolved_customer_id or zone.region.customer_id
        resolved_region_id = resolved_region_id or zone.region_id

    return resolved_customer_id, resolved_region_id, zone_id


def _load_scoped_hierarchy(
    db: Session,
    *,
    allowed_customer_ids: list[int] | None,
    customer_id: int | None,
    region_id: int | None,
    zone_id: int | None,
    active_only: bool,
) -> tuple[list[Customer], list[Region], list[Zone], list[Ward]]:
    c_stmt = select(Customer).order_by(Customer.customer_name.asc())
    r_stmt = select(Region).join(Customer, Region.customer_id == Customer.id).order_by(Region.region_name.asc())
    z_stmt = (
        select(Zone)
        .join(Region, Zone.region_id == Region.id)
        .join(Customer, Region.customer_id == Customer.id)
        .order_by(Zone.zone_name.asc())
    )
    w_stmt = (
        select(Ward)
        .join(Zone, Ward.zone_id == Zone.id)
        .join(Region, Zone.region_id == Region.id)
        .join(Customer, Region.customer_id == Customer.id)
        .options(
            selectinload(Ward.zone)
            .selectinload(Zone.region)
            .selectinload(Region.customer)
        )
    )

    if allowed_customer_ids is not None:
        if not allowed_customer_ids:
            return [], [], [], []
        c_stmt = c_stmt.where(Customer.id.in_(allowed_customer_ids))
        r_stmt = r_stmt.where(Region.customer_id.in_(allowed_customer_ids))
        z_stmt = z_stmt.where(Region.customer_id.in_(allowed_customer_ids))
        w_stmt = w_stmt.where(Region.customer_id.in_(allowed_customer_ids))

    if customer_id is not None:
        c_stmt = c_stmt.where(Customer.id == customer_id)
        r_stmt = r_stmt.where(Region.customer_id == customer_id)
        z_stmt = z_stmt.where(Region.customer_id == customer_id)
        w_stmt = w_stmt.where(Region.customer_id == customer_id)

    if region_id is not None:
        r_stmt = r_stmt.where(Region.id == region_id)
        z_stmt = z_stmt.where(Zone.region_id == region_id)
        w_stmt = w_stmt.where(Zone.region_id == region_id)

    if zone_id is not None:
        z_stmt = z_stmt.where(Zone.id == zone_id)
        w_stmt = w_stmt.where(Ward.zone_id == zone_id)

    if active_only:
        c_stmt = c_stmt.where(Customer.status == "active")
        r_stmt = r_stmt.where(Customer.status == "active", Region.status == "active")
        z_stmt = z_stmt.where(
            Customer.status == "active",
            Region.status == "active",
            Zone.status == "active",
        )
        w_stmt = w_stmt.where(
            Customer.status == "active",
            Region.status == "active",
            Zone.status == "active",
            Ward.status == "active",
        )

    customers = list(db.scalars(c_stmt).all())
    regions = list(db.scalars(r_stmt).all())
    zones = list(db.scalars(z_stmt).all())
    wards = list(db.scalars(w_stmt).all())
    return customers, regions, zones, wards


def _build_availability_breakdowns(
    db: Session,
    *,
    regions: list[Region],
    zones: list[Zone],
    wards: list[Ward],
    pole_ward_ids: set[int],
    lamp_ward_ids: set[int],
    published_merged_ward_ids: set[int],
    draft_or_outdated_ward_ids: set[int],
    error_ward_ids: set[int],
    only_published_merged: bool,
) -> tuple[list[RegionAvailabilityItem], list[ZoneAvailabilityItem]]:
    customer_cache: dict[int, Customer] = {}
    region_cache: dict[int, Region] = {r.id: r for r in regions}

    def _cust_name(cid: int) -> str:
        if cid not in customer_cache:
            c = db.get(Customer, cid)
            if c is not None:
                customer_cache[cid] = c
        c = customer_cache.get(cid)
        return c.customer_name if c else ""

    zones_by_region: dict[int, list[Zone]] = {}
    for z in zones:
        zones_by_region.setdefault(z.region_id, []).append(z)

    wards_by_region: dict[int, list[Ward]] = {}
    wards_by_zone: dict[int, list[Ward]] = {}
    for w in wards:
        wards_by_zone.setdefault(w.zone_id, []).append(w)
        if w.zone is not None:
            wards_by_region.setdefault(w.zone.region_id, []).append(w)

    region_items: list[RegionAvailabilityItem] = []
    for reg in regions:
        reg_wards = wards_by_region.get(reg.id, [])
        reg_ward_ids = {w.id for w in reg_wards}
        active_reg_wards = [w for w in reg_wards if w.status == "active"]
        region_items.append(
            RegionAvailabilityItem(
                customer_id=reg.customer_id,
                customer_name=_cust_name(reg.customer_id),
                region_id=reg.id,
                region_name=reg.region_name,
                total_zones=len(zones_by_region.get(reg.id, [])),
                total_wards=len(reg_wards),
                pole_survey_count=len(reg_ward_ids & pole_ward_ids),
                lamp_installation_count=len(reg_ward_ids & lamp_ward_ids),
                merged_published_count=len(reg_ward_ids & published_merged_ward_ids),
                merged_draft_or_outdated_count=0
                if only_published_merged
                else len(reg_ward_ids & draft_or_outdated_ward_ids),
                awaiting_uploads_count=sum(
                    1
                    for w in active_reg_wards
                    if w.id not in pole_ward_ids or w.id not in lamp_ward_ids
                ),
                error_wards_count=0 if only_published_merged else len(reg_ward_ids & error_ward_ids),
            )
        )

    zone_items: list[ZoneAvailabilityItem] = []
    for z in zones:
        reg = region_cache.get(z.region_id) or db.get(Region, z.region_id)
        z_wards = wards_by_zone.get(z.id, [])
        z_ward_ids = {w.id for w in z_wards}
        active_z_wards = [w for w in z_wards if w.status == "active"]
        cust_id = reg.customer_id if reg else 0
        zone_items.append(
            ZoneAvailabilityItem(
                customer_id=cust_id,
                customer_name=_cust_name(cust_id),
                region_id=z.region_id,
                region_name=reg.region_name if reg else "",
                zone_id=z.id,
                zone_name=z.zone_name,
                zone_code=z.zone_code,
                total_wards=len(z_wards),
                pole_survey_count=len(z_ward_ids & pole_ward_ids),
                lamp_installation_count=len(z_ward_ids & lamp_ward_ids),
                merged_published_count=len(z_ward_ids & published_merged_ward_ids),
                merged_draft_or_outdated_count=0
                if only_published_merged
                else len(z_ward_ids & draft_or_outdated_ward_ids),
                awaiting_uploads_count=sum(
                    1
                    for w in active_z_wards
                    if w.id not in pole_ward_ids or w.id not in lamp_ward_ids
                ),
                error_wards_count=0 if only_published_merged else len(z_ward_ids & error_ward_ids),
            )
        )

    return region_items, zone_items


def get_admin_dashboard(
    db: Session,
    *,
    customer_id: int | None = None,
    region_id: int | None = None,
    zone_id: int | None = None,
) -> AdminDashboardOut:
    resolved_cust_id, resolved_reg_id, resolved_zone_id = _validate_dashboard_filters(
        db,
        auth=None,
        customer_id=customer_id,
        region_id=region_id,
        zone_id=zone_id,
    )

    customers, regions, zones, wards = _load_scoped_hierarchy(
        db,
        allowed_customer_ids=None,
        customer_id=resolved_cust_id,
        region_id=resolved_reg_id,
        zone_id=resolved_zone_id,
        active_only=False,
    )
    ward_ids = [w.id for w in wards]

    pole_ward_ids: set[int] = set()
    lamp_ward_ids: set[int] = set()
    completed_merged_ward_ids: set[int] = set()
    published_merged_ward_ids: set[int] = set()
    draft_or_outdated_ward_ids: set[int] = set()
    error_ward_ids: set[int] = set()
    total_merged_count = 0

    if ward_ids:
        rf_rows = db.execute(
            select(ReportFile.ward_id, ReportFile.report_type).where(
                ReportFile.ward_id.in_(ward_ids),
                ReportFile.status == "active",
            )
        ).all()
        for wid, rtype in rf_rows:
            if rtype == "pole_survey":
                pole_ward_ids.add(wid)
            elif rtype == "lamp_installation":
                lamp_ward_ids.add(wid)

        mr_rows = db.execute(
            select(
                MergedReport.ward_id,
                MergedReport.status,
                MergedReport.published_at,
                MergedReport.generated_file_path,
            ).where(MergedReport.ward_id.in_(ward_ids))
        ).all()
        total_merged_count = len(mr_rows)
        for wid, mstatus, pub_at, gen_path in mr_rows:
            if gen_path and mstatus in {"draft", "published", "outdated"}:
                completed_merged_ward_ids.add(wid)
            if pub_at is not None:
                published_merged_ward_ids.add(wid)
            elif mstatus in {"draft", "outdated"}:
                draft_or_outdated_ward_ids.add(wid)

        # Latest processing log status per ward determines whether a ward currently has errors
        log_rows = db.execute(
            select(ProcessingLog.ward_id, ProcessingLog.processing_status)
            .where(ProcessingLog.ward_id.in_(ward_ids))
            .order_by(ProcessingLog.created_at.desc(), ProcessingLog.id.desc())
        ).all()
        seen_wards: set[int] = set()
        for wid, pstatus in log_rows:
            if wid not in seen_wards:
                seen_wards.add(wid)
                if pstatus == "failed":
                    error_ward_ids.add(wid)

    active_wards = [w for w in wards if w.status == "active"]
    wards_awaiting_uploads = sum(
        1
        for w in active_wards
        if w.id not in pole_ward_ids or w.id not in lamp_ward_ids
    )

    # Filter recent lists cleanly by active scope filters
    rf_stmt = select(ReportFile).where(ReportFile.status == "active")
    mr_stmt = select(MergedReport)
    log_stmt = select(ProcessingLog)
    if resolved_cust_id is not None:
        rf_stmt = rf_stmt.where(ReportFile.customer_id == resolved_cust_id)
        mr_stmt = mr_stmt.where(MergedReport.customer_id == resolved_cust_id)
        log_stmt = log_stmt.where(ProcessingLog.customer_id == resolved_cust_id)
    if resolved_reg_id is not None:
        rf_stmt = rf_stmt.where(ReportFile.region_id == resolved_reg_id)
        mr_stmt = mr_stmt.where(MergedReport.region_id == resolved_reg_id)
        log_stmt = log_stmt.where(ProcessingLog.region_id == resolved_reg_id)
    if resolved_zone_id is not None:
        rf_stmt = rf_stmt.where(ReportFile.zone_id == resolved_zone_id)
        mr_stmt = mr_stmt.where(MergedReport.zone_id == resolved_zone_id)
        log_stmt = log_stmt.where(ProcessingLog.zone_id == resolved_zone_id)

    recent_rf = db.scalars(rf_stmt.order_by(ReportFile.uploaded_at.desc()).limit(8)).all()
    recent_uploads: list[RecentUploadItem] = []
    for rf in recent_rf:
        c = db.get(Customer, rf.customer_id)
        r = db.get(Region, rf.region_id)
        z = db.get(Zone, rf.zone_id)
        w = db.get(Ward, rf.ward_id)
        u = db.get(User, rf.uploaded_by)
        recent_uploads.append(
            RecentUploadItem(
                id=rf.id,
                report_type=rf.report_type,
                original_filename=rf.original_filename,
                version=rf.version,
                customer_name=c.customer_name if c else "",
                region_name=r.region_name if r else "",
                zone_name=z.zone_name if z else "",
                ward_id=rf.ward_id,
                ward_number=w.ward_number if w else "",
                ward_name=w.ward_name if w else "",
                uploaded_by_name=u.name if u else None,
                uploaded_at=rf.uploaded_at,
            )
        )

    recent_mr = db.scalars(mr_stmt.order_by(MergedReport.generated_at.desc()).limit(8)).all()
    recent_merged_reports: list[RecentMergedItem] = []
    for mr in recent_mr:
        c = db.get(Customer, mr.customer_id)
        r = db.get(Region, mr.region_id)
        z = db.get(Zone, mr.zone_id)
        w = db.get(Ward, mr.ward_id)
        latest_log = db.scalar(
            select(ProcessingLog)
            .where(ProcessingLog.merged_report_id == mr.id)
            .order_by(ProcessingLog.created_at.desc())
            .limit(1)
        )
        recent_merged_reports.append(
            RecentMergedItem(
                id=mr.id,
                customer_name=c.customer_name if c else "",
                region_name=r.region_name if r else "",
                zone_name=z.zone_name if z else "",
                ward_id=mr.ward_id,
                ward_number=w.ward_number if w else "",
                ward_name=w.ward_name if w else "",
                current_version=mr.current_version,
                status=mr.status,
                added_records=latest_log.added_records if latest_log else 0,
                final_merged_records=latest_log.final_merged_records if latest_log else 0,
                generated_at=mr.generated_at,
            )
        )

    def _serialize_logs(logs: list[ProcessingLog]) -> list[ProcessingActivityItem]:
        out: list[ProcessingActivityItem] = []
        for log in logs:
            c = db.get(Customer, log.customer_id)
            r = db.get(Region, log.region_id)
            z = db.get(Zone, log.zone_id)
            w = db.get(Ward, log.ward_id)
            out.append(
                ProcessingActivityItem(
                    id=log.id,
                    customer_name=c.customer_name if c else "",
                    region_name=r.region_name if r else "",
                    zone_name=z.zone_name if z else "",
                    ward_id=log.ward_id,
                    ward_number=w.ward_number if w else "",
                    ward_name=w.ward_name if w else "",
                    processing_status=log.processing_status,
                    added_records=log.added_records,
                    duplicate_records=log.duplicate_records,
                    invalid_records=log.invalid_records,
                    unknown_lamp_type_records=log.unknown_lamp_type_records,
                    error_message=log.error_message,
                    created_at=log.created_at,
                )
            )
        return out

    latest_logs = db.scalars(log_stmt.order_by(ProcessingLog.created_at.desc()).limit(8)).all()
    failed_logs = db.scalars(
        log_stmt.where(ProcessingLog.processing_status == "failed")
        .order_by(ProcessingLog.created_at.desc())
        .limit(8)
    ).all()

    region_avail, zone_avail = _build_availability_breakdowns(
        db,
        regions=regions,
        zones=zones,
        wards=wards,
        pole_ward_ids=pole_ward_ids,
        lamp_ward_ids=lamp_ward_ids,
        published_merged_ward_ids=published_merged_ward_ids,
        draft_or_outdated_ward_ids=draft_or_outdated_ward_ids,
        error_ward_ids=error_ward_ids,
        only_published_merged=False,
    )

    return AdminDashboardOut(
        total_customers=len(customers),
        total_regions=len(regions),
        total_zones=len(zones),
        total_wards=len(wards),
        wards_with_pole_survey=len(pole_ward_ids),
        wards_with_lamp_installation=len(lamp_ward_ids),
        wards_with_completed_merged=len(completed_merged_ward_ids),
        wards_with_published_merged=len(published_merged_ward_ids),
        wards_awaiting_uploads=wards_awaiting_uploads,
        wards_with_processing_errors=len(error_ward_ids),
        total_pole_survey_reports=len(pole_ward_ids),
        total_lamp_installation_reports=len(lamp_ward_ids),
        total_merged_reports=total_merged_count,
        recent_uploads=recent_uploads,
        recent_merged_reports=recent_merged_reports,
        latest_processing_activity=_serialize_logs(latest_logs),
        failed_processing_records=_serialize_logs(failed_logs),
        report_availability_by_region=region_avail,
        zone_availability=zone_avail,
    )


def get_customer_dashboard(
    db: Session,
    auth: AuthContext,
    *,
    customer_id: int | None = None,
    region_id: int | None = None,
    zone_id: int | None = None,
) -> CustomerDashboardOut:
    resolved_cust_id, resolved_reg_id, resolved_zone_id = _validate_dashboard_filters(
        db,
        auth=auth,
        customer_id=customer_id,
        region_id=region_id,
        zone_id=zone_id,
    )

    cust_ids = auth.authorized_customer_ids
    if cust_ids is not None and not cust_ids:
        return CustomerDashboardOut(
            customer_names=[],
            total_regions=0,
            total_zones=0,
            total_wards=0,
            wards_with_pole_survey=0,
            wards_with_lamp_installation=0,
            wards_with_completed_merged=0,
            wards_awaiting_uploads=0,
            available_pole_survey_count=0,
            available_lamp_installation_count=0,
            available_merged_count=0,
            last_updated_at=None,
            recent_available_reports=[],
            region_availability=[],
            zone_availability=[],
        )

    customers, regions, zones, wards = _load_scoped_hierarchy(
        db,
        allowed_customer_ids=cust_ids,
        customer_id=resolved_cust_id,
        region_id=resolved_reg_id,
        zone_id=resolved_zone_id,
        active_only=True,
    )
    customer_names = [c.customer_name for c in customers]
    if not customers:
        return CustomerDashboardOut(
            customer_names=[],
            total_regions=0,
            total_zones=0,
            total_wards=0,
            wards_with_pole_survey=0,
            wards_with_lamp_installation=0,
            wards_with_completed_merged=0,
            wards_awaiting_uploads=0,
            available_pole_survey_count=0,
            available_lamp_installation_count=0,
            available_merged_count=0,
            last_updated_at=None,
            recent_available_reports=[],
            region_availability=[],
            zone_availability=[],
        )

    ward_ids = [w.id for w in wards]
    pole_ward_ids: set[int] = set()
    lamp_ward_ids: set[int] = set()
    published_merged_ward_ids: set[int] = set()

    if ward_ids:
        rf_rows = db.execute(
            select(ReportFile.ward_id, ReportFile.report_type).where(
                ReportFile.ward_id.in_(ward_ids),
                ReportFile.status == "active",
            )
        ).all()
        for wid, rtype in rf_rows:
            if rtype == "pole_survey":
                pole_ward_ids.add(wid)
            elif rtype == "lamp_installation":
                lamp_ward_ids.add(wid)

        pub_rows = db.scalars(
            select(MergedReport.ward_id).where(
                MergedReport.ward_id.in_(ward_ids),
                MergedReport.published_at.is_not(None),
            )
        ).all()
        published_merged_ward_ids.update(pub_rows)

    wards_awaiting_uploads = sum(
        1 for w in wards if w.id not in pole_ward_ids or w.id not in lamp_ward_ids
    )

    last_updated_at = None
    recent_items: list[dict] = []
    if ward_ids:
        last_rf_dt = db.scalar(
            select(func.max(ReportFile.uploaded_at)).where(
                ReportFile.ward_id.in_(ward_ids), ReportFile.status == "active"
            )
        )
        last_mr_dt = db.scalar(
            select(func.max(MergedReport.published_at)).where(
                MergedReport.ward_id.in_(ward_ids), MergedReport.published_at.is_not(None)
            )
        )
        dates = [d for d in (last_rf_dt, last_mr_dt) if d is not None]
        last_updated_at = max(dates) if dates else None

        pub_merged = db.scalars(
            select(MergedReport)
            .where(
                MergedReport.ward_id.in_(ward_ids),
                MergedReport.published_at.is_not(None),
            )
            .order_by(MergedReport.published_at.desc())
            .limit(5)
        ).all()
        for mr in pub_merged:
            r = db.get(Region, mr.region_id)
            z = db.get(Zone, mr.zone_id)
            w = db.get(Ward, mr.ward_id)
            recent_items.append(
                {
                    "id": mr.id,
                    "category": "merged_report",
                    "title": f"Merged Report - {z.zone_name if z else ''} ({w.ward_number if w else ''})",
                    "region_name": r.region_name if r else "",
                    "zone_name": z.zone_name if z else "",
                    "ward_id": mr.ward_id,
                    "ward_number": w.ward_number if w else "",
                    "ward_name": w.ward_name if w else "",
                    "updated_at": mr.published_at,
                    "version": mr.current_version,
                }
            )

        recent_src = db.scalars(
            select(ReportFile)
            .where(
                ReportFile.ward_id.in_(ward_ids),
                ReportFile.status == "active",
            )
            .order_by(ReportFile.uploaded_at.desc())
            .limit(6)
        ).all()
        for rf in recent_src:
            r = db.get(Region, rf.region_id)
            z = db.get(Zone, rf.zone_id)
            w = db.get(Ward, rf.ward_id)
            recent_items.append(
                {
                    "id": rf.id,
                    "category": rf.report_type,
                    "title": rf.original_filename,
                    "region_name": r.region_name if r else "",
                    "zone_name": z.zone_name if z else "",
                    "ward_id": rf.ward_id,
                    "ward_number": w.ward_number if w else "",
                    "ward_name": w.ward_name if w else "",
                    "updated_at": rf.uploaded_at,
                    "version": rf.version,
                }
            )

        recent_items.sort(key=lambda x: x["updated_at"], reverse=True)

    region_avail, zone_avail = _build_availability_breakdowns(
        db,
        regions=regions,
        zones=zones,
        wards=wards,
        pole_ward_ids=pole_ward_ids,
        lamp_ward_ids=lamp_ward_ids,
        published_merged_ward_ids=published_merged_ward_ids,
        draft_or_outdated_ward_ids=set(),
        error_ward_ids=set(),
        only_published_merged=True,
    )

    return CustomerDashboardOut(
        customer_names=customer_names,
        total_regions=len(regions),
        total_zones=len(zones),
        total_wards=len(wards),
        wards_with_pole_survey=len(pole_ward_ids),
        wards_with_lamp_installation=len(lamp_ward_ids),
        wards_with_completed_merged=len(published_merged_ward_ids),
        wards_awaiting_uploads=wards_awaiting_uploads,
        available_pole_survey_count=len(pole_ward_ids),
        available_lamp_installation_count=len(lamp_ward_ids),
        available_merged_count=len(published_merged_ward_ids),
        last_updated_at=last_updated_at,
        recent_available_reports=recent_items[:8],
        region_availability=region_avail,
        zone_availability=zone_avail,
    )
