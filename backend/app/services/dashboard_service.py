from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.dependencies import AuthContext
from app.models.hierarchy import Customer, Region, Zone
from app.models.report import MergedReport, ProcessingLog, ReportFile
from app.models.user import User
from app.schemas.reports import (
    AdminDashboardOut,
    CustomerDashboardOut,
    ProcessingActivityItem,
    RecentMergedItem,
    RecentUploadItem,
    RegionAvailabilityItem,
)


def _compute_region_availability(
    db: Session, customer_ids: list[int] | None, only_published_merged: bool
) -> list[RegionAvailabilityItem]:
    stmt = (
        select(Region)
        .options(selectinload(Region.customer), selectinload(Region.zones))
        .order_by(Region.region_name.asc())
    )
    if customer_ids is not None:
        if not customer_ids:
            return []
        stmt = stmt.where(Region.customer_id.in_(customer_ids), Region.status == "active")

    regions = db.scalars(stmt).all()
    items: list[RegionAvailabilityItem] = []

    for reg in regions:
        active_zones = [z for z in reg.zones if (customer_ids is None or z.status == "active")]
        pole_cnt = db.scalar(
            select(func.count(ReportFile.id)).where(
                ReportFile.region_id == reg.id,
                ReportFile.report_type == "pole_survey",
                ReportFile.status == "active",
            )
        ) or 0
        lamp_cnt = db.scalar(
            select(func.count(ReportFile.id)).where(
                ReportFile.region_id == reg.id,
                ReportFile.report_type == "lamp_installation",
                ReportFile.status == "active",
            )
        ) or 0
        pub_cnt = db.scalar(
            select(func.count(MergedReport.id)).where(
                MergedReport.region_id == reg.id,
                MergedReport.published_at.is_not(None),
            )
        ) or 0
        other_cnt = 0
        if not only_published_merged:
            other_cnt = db.scalar(
                select(func.count(MergedReport.id)).where(
                    MergedReport.region_id == reg.id,
                    MergedReport.status.in_(["draft", "outdated"]),
                )
            ) or 0

        items.append(
            RegionAvailabilityItem(
                customer_id=reg.customer_id,
                customer_name=reg.customer.customer_name,
                region_id=reg.id,
                region_name=reg.region_name,
                total_zones=len(active_zones),
                pole_survey_count=pole_cnt,
                lamp_installation_count=lamp_cnt,
                merged_published_count=pub_cnt,
                merged_draft_or_outdated_count=other_cnt,
            )
        )
    return items


def get_admin_dashboard(db: Session) -> AdminDashboardOut:
    total_customers = db.scalar(select(func.count(Customer.id))) or 0
    total_regions = db.scalar(select(func.count(Region.id))) or 0
    total_zones = db.scalar(select(func.count(Zone.id))) or 0
    total_pole = db.scalar(
        select(func.count(ReportFile.id)).where(
            ReportFile.report_type == "pole_survey", ReportFile.status == "active"
        )
    ) or 0
    total_lamp = db.scalar(
        select(func.count(ReportFile.id)).where(
            ReportFile.report_type == "lamp_installation", ReportFile.status == "active"
        )
    ) or 0
    total_merged = db.scalar(select(func.count(MergedReport.id))) or 0

    recent_rf = db.scalars(
        select(ReportFile)
        .where(ReportFile.status == "active")
        .order_by(ReportFile.uploaded_at.desc())
        .limit(8)
    ).all()
    recent_uploads: list[RecentUploadItem] = []
    for rf in recent_rf:
        c = db.get(Customer, rf.customer_id)
        r = db.get(Region, rf.region_id)
        z = db.get(Zone, rf.zone_id)
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
                uploaded_by_name=u.name if u else None,
                uploaded_at=rf.uploaded_at,
            )
        )

    recent_mr = db.scalars(
        select(MergedReport).order_by(MergedReport.generated_at.desc()).limit(8)
    ).all()
    recent_merged_reports: list[RecentMergedItem] = []
    for mr in recent_mr:
        c = db.get(Customer, mr.customer_id)
        r = db.get(Region, mr.region_id)
        z = db.get(Zone, mr.zone_id)
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
            out.append(
                ProcessingActivityItem(
                    id=log.id,
                    customer_name=c.customer_name if c else "",
                    region_name=r.region_name if r else "",
                    zone_name=z.zone_name if z else "",
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

    latest_logs = db.scalars(
        select(ProcessingLog).order_by(ProcessingLog.created_at.desc()).limit(8)
    ).all()
    failed_logs = db.scalars(
        select(ProcessingLog)
        .where(ProcessingLog.processing_status == "failed")
        .order_by(ProcessingLog.created_at.desc())
        .limit(8)
    ).all()

    return AdminDashboardOut(
        total_customers=total_customers,
        total_regions=total_regions,
        total_zones=total_zones,
        total_pole_survey_reports=total_pole,
        total_lamp_installation_reports=total_lamp,
        total_merged_reports=total_merged,
        recent_uploads=recent_uploads,
        recent_merged_reports=recent_merged_reports,
        latest_processing_activity=_serialize_logs(latest_logs),
        failed_processing_records=_serialize_logs(failed_logs),
        report_availability_by_region=_compute_region_availability(
            db, customer_ids=None, only_published_merged=False
        ),
    )


def get_customer_dashboard(db: Session, auth: AuthContext) -> CustomerDashboardOut:
    cust_ids = auth.authorized_customer_ids or []
    if not cust_ids:
        return CustomerDashboardOut(
            customer_names=[],
            total_regions=0,
            total_zones=0,
            available_pole_survey_count=0,
            available_lamp_installation_count=0,
            available_merged_count=0,
            last_updated_at=None,
            recent_available_reports=[],
            region_availability=[],
        )

    customers = db.scalars(
        select(Customer).where(Customer.id.in_(cust_ids), Customer.status == "active")
    ).all()
    active_cust_ids = [c.id for c in customers]
    customer_names = [c.customer_name for c in customers]

    if not active_cust_ids:
        return CustomerDashboardOut(
            customer_names=[],
            total_regions=0,
            total_zones=0,
            available_pole_survey_count=0,
            available_lamp_installation_count=0,
            available_merged_count=0,
            last_updated_at=None,
            recent_available_reports=[],
            region_availability=[],
        )

    total_regions = db.scalar(
        select(func.count(Region.id)).where(
            Region.customer_id.in_(active_cust_ids), Region.status == "active"
        )
    ) or 0
    total_zones = db.scalar(
        select(func.count(Zone.id))
        .join(Region, Zone.region_id == Region.id)
        .where(
            Region.customer_id.in_(active_cust_ids),
            Region.status == "active",
            Zone.status == "active",
        )
    ) or 0

    pole_count = db.scalar(
        select(func.count(ReportFile.id)).where(
            ReportFile.customer_id.in_(active_cust_ids),
            ReportFile.report_type == "pole_survey",
            ReportFile.status == "active",
        )
    ) or 0
    lamp_count = db.scalar(
        select(func.count(ReportFile.id)).where(
            ReportFile.customer_id.in_(active_cust_ids),
            ReportFile.report_type == "lamp_installation",
            ReportFile.status == "active",
        )
    ) or 0
    merged_count = db.scalar(
        select(func.count(MergedReport.id)).where(
            MergedReport.customer_id.in_(active_cust_ids),
            MergedReport.published_at.is_not(None),
        )
    ) or 0

    last_rf_dt = db.scalar(
        select(func.max(ReportFile.uploaded_at)).where(
            ReportFile.customer_id.in_(active_cust_ids), ReportFile.status == "active"
        )
    )
    last_mr_dt = db.scalar(
        select(func.max(MergedReport.published_at)).where(
            MergedReport.customer_id.in_(active_cust_ids), MergedReport.published_at.is_not(None)
        )
    )
    dates = [d for d in (last_rf_dt, last_mr_dt) if d is not None]
    last_updated_at = max(dates) if dates else None

    recent_items: list[dict] = []
    pub_merged = db.scalars(
        select(MergedReport)
        .where(
            MergedReport.customer_id.in_(active_cust_ids),
            MergedReport.published_at.is_not(None),
        )
        .order_by(MergedReport.published_at.desc())
        .limit(5)
    ).all()
    for mr in pub_merged:
        r = db.get(Region, mr.region_id)
        z = db.get(Zone, mr.zone_id)
        recent_items.append(
            {
                "id": mr.id,
                "category": "merged_report",
                "title": f"Merged Report - {z.zone_name if z else ''}",
                "region_name": r.region_name if r else "",
                "zone_name": z.zone_name if z else "",
                "updated_at": mr.published_at,
                "version": mr.current_version,
            }
        )

    recent_src = db.scalars(
        select(ReportFile)
        .where(
            ReportFile.customer_id.in_(active_cust_ids),
            ReportFile.status == "active",
        )
        .order_by(ReportFile.uploaded_at.desc())
        .limit(6)
    ).all()
    for rf in recent_src:
        r = db.get(Region, rf.region_id)
        z = db.get(Zone, rf.zone_id)
        recent_items.append(
            {
                "id": rf.id,
                "category": rf.report_type,
                "title": rf.original_filename,
                "region_name": r.region_name if r else "",
                "zone_name": z.zone_name if z else "",
                "updated_at": rf.uploaded_at,
                "version": rf.version,
            }
        )

    recent_items.sort(key=lambda x: x["updated_at"], reverse=True)

    return CustomerDashboardOut(
        customer_names=customer_names,
        total_regions=total_regions,
        total_zones=total_zones,
        available_pole_survey_count=pole_count,
        available_lamp_installation_count=lamp_count,
        available_merged_count=merged_count,
        last_updated_at=last_updated_at,
        recent_available_reports=recent_items[:8],
        region_availability=_compute_region_availability(
            db, customer_ids=active_cust_ids, only_published_merged=True
        ),
    )

