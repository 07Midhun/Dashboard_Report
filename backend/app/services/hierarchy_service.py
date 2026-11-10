from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.dependencies import AuthContext, verify_customer_access
from app.models.hierarchy import Customer, Region, Zone
from app.models.report import MergedReport, ReportFile
from app.schemas.hierarchy import (
    CustomerCreate,
    CustomerOut,
    CustomerUpdate,
    HierarchyCustomerNode,
    HierarchyRegionNode,
    HierarchyZoneNode,
    RegionCreate,
    RegionOut,
    RegionUpdate,
    ZoneCreate,
    ZoneOut,
    ZoneUpdate,
)
from app.services.audit_service import record_audit_log


def list_customers(db: Session, auth: AuthContext) -> list[CustomerOut]:
    stmt = select(Customer).order_by(Customer.customer_name.asc())
    if auth.authorized_customer_ids is not None:
        if not auth.authorized_customer_ids:
            return []
        stmt = stmt.where(
            Customer.id.in_(auth.authorized_customer_ids),
            Customer.status == "active",
        )

    customers = db.scalars(stmt).all()
    results: list[CustomerOut] = []
    for cust in customers:
        regions_count = db.scalar(
            select(func.count(Region.id)).where(Region.customer_id == cust.id)
        ) or 0
        zones_count = db.scalar(
            select(func.count(Zone.id))
            .join(Region, Zone.region_id == Region.id)
            .where(Region.customer_id == cust.id)
        ) or 0
        reports_count = db.scalar(
            select(func.count(ReportFile.id)).where(
                ReportFile.customer_id == cust.id,
                ReportFile.status == "active",
            )
        ) or 0
        results.append(
            CustomerOut(
                id=cust.id,
                customer_name=cust.customer_name,
                status=cust.status,
                regions_count=regions_count,
                zones_count=zones_count,
                report_files_count=reports_count,
                created_at=cust.created_at,
                updated_at=cust.updated_at,
            )
        )
    return results


def create_customer(db: Session, payload: CustomerCreate, user_id: int, ip: str | None) -> CustomerOut:
    name = payload.customer_name.strip()
    existing = db.scalar(
        select(Customer).where(func.lower(Customer.customer_name) == name.lower())
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Customer '{name}' already exists.",
        )

    cust = Customer(customer_name=name, status=payload.status)
    db.add(cust)
    db.flush()
    record_audit_log(
        db,
        user_id=user_id,
        action="customer.create",
        entity_type="customer",
        entity_id=cust.id,
        details={"customer_name": cust.customer_name, "status": cust.status},
        ip_address=ip,
    )
    db.commit()
    db.refresh(cust)
    return CustomerOut(
        id=cust.id,
        customer_name=cust.customer_name,
        status=cust.status,
        created_at=cust.created_at,
        updated_at=cust.updated_at,
    )


def update_customer(
    db: Session, customer_id: int, payload: CustomerUpdate, user_id: int, ip: str | None
) -> CustomerOut:
    cust = db.get(Customer, customer_id)
    if cust is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    if payload.customer_name is not None:
        name = payload.customer_name.strip()
        dup = db.scalar(
            select(Customer).where(
                func.lower(Customer.customer_name) == name.lower(),
                Customer.id != customer_id,
            )
        )
        if dup is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Customer '{name}' already exists.",
            )
        cust.customer_name = name

    if payload.status is not None:
        cust.status = payload.status

    record_audit_log(
        db,
        user_id=user_id,
        action="customer.update",
        entity_type="customer",
        entity_id=cust.id,
        details={"customer_name": cust.customer_name, "status": cust.status},
        ip_address=ip,
    )
    db.commit()
    db.refresh(cust)

    regions_count = db.scalar(select(func.count(Region.id)).where(Region.customer_id == cust.id)) or 0
    zones_count = db.scalar(
        select(func.count(Zone.id))
        .join(Region, Zone.region_id == Region.id)
        .where(Region.customer_id == cust.id)
    ) or 0
    reports_count = db.scalar(
        select(func.count(ReportFile.id)).where(
            ReportFile.customer_id == cust.id, ReportFile.status == "active"
        )
    ) or 0
    return CustomerOut(
        id=cust.id,
        customer_name=cust.customer_name,
        status=cust.status,
        regions_count=regions_count,
        zones_count=zones_count,
        report_files_count=reports_count,
        created_at=cust.created_at,
        updated_at=cust.updated_at,
    )


def delete_customer(db: Session, customer_id: int, user_id: int, ip: str | None) -> None:
    cust = db.get(Customer, customer_id)
    if cust is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    has_regions = db.scalar(select(Region.id).where(Region.customer_id == customer_id))
    has_reports = db.scalar(select(ReportFile.id).where(ReportFile.customer_id == customer_id))
    if has_regions or has_reports:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete customer with existing regions or uploaded reports. Deactivate it instead.",
        )

    record_audit_log(
        db,
        user_id=user_id,
        action="customer.delete",
        entity_type="customer",
        entity_id=cust.id,
        details={"customer_name": cust.customer_name},
        ip_address=ip,
    )
    db.delete(cust)
    db.commit()


def list_regions(db: Session, auth: AuthContext, customer_id: int | None = None) -> list[RegionOut]:
    stmt = (
        select(Region)
        .options(selectinload(Region.customer))
        .order_by(Region.region_name.asc())
    )
    if customer_id is not None:
        verify_customer_access(auth, customer_id)
        stmt = stmt.where(Region.customer_id == customer_id)
    elif auth.authorized_customer_ids is not None:
        if not auth.authorized_customer_ids:
            return []
        stmt = stmt.where(Region.customer_id.in_(auth.authorized_customer_ids))

    if auth.user.role != "admin":
        stmt = stmt.where(Region.status == "active")

    regions = db.scalars(stmt).all()
    results: list[RegionOut] = []
    for reg in regions:
        zones_count = db.scalar(select(func.count(Zone.id)).where(Zone.region_id == reg.id)) or 0
        reports_count = db.scalar(
            select(func.count(ReportFile.id)).where(
                ReportFile.region_id == reg.id, ReportFile.status == "active"
            )
        ) or 0
        results.append(
            RegionOut(
                id=reg.id,
                customer_id=reg.customer_id,
                customer_name=reg.customer.customer_name,
                region_name=reg.region_name,
                status=reg.status,
                zones_count=zones_count,
                report_files_count=reports_count,
                created_at=reg.created_at,
                updated_at=reg.updated_at,
            )
        )
    return results


def create_region(db: Session, payload: RegionCreate, user_id: int, ip: str | None) -> RegionOut:
    cust = db.get(Customer, payload.customer_id)
    if cust is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    name = payload.region_name.strip()
    dup = db.scalar(
        select(Region).where(
            Region.customer_id == payload.customer_id,
            func.lower(Region.region_name) == name.lower(),
        )
    )
    if dup is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Region '{name}' already exists under {cust.customer_name}.",
        )

    reg = Region(customer_id=payload.customer_id, region_name=name, status=payload.status)
    db.add(reg)
    db.flush()
    record_audit_log(
        db,
        user_id=user_id,
        action="region.create",
        entity_type="region",
        entity_id=reg.id,
        details={"customer_id": reg.customer_id, "region_name": reg.region_name},
        ip_address=ip,
    )
    db.commit()
    db.refresh(reg)
    return RegionOut(
        id=reg.id,
        customer_id=reg.customer_id,
        customer_name=cust.customer_name,
        region_name=reg.region_name,
        status=reg.status,
        created_at=reg.created_at,
        updated_at=reg.updated_at,
    )


def update_region(
    db: Session, region_id: int, payload: RegionUpdate, user_id: int, ip: str | None
) -> RegionOut:
    reg = db.scalar(
        select(Region).options(selectinload(Region.customer)).where(Region.id == region_id)
    )
    if reg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found.")

    if payload.region_name is not None:
        name = payload.region_name.strip()
        dup = db.scalar(
            select(Region).where(
                Region.customer_id == reg.customer_id,
                func.lower(Region.region_name) == name.lower(),
                Region.id != region_id,
            )
        )
        if dup is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Region '{name}' already exists under this customer.",
            )
        reg.region_name = name

    if payload.status is not None:
        reg.status = payload.status

    record_audit_log(
        db,
        user_id=user_id,
        action="region.update",
        entity_type="region",
        entity_id=reg.id,
        details={"region_name": reg.region_name, "status": reg.status},
        ip_address=ip,
    )
    db.commit()
    db.refresh(reg)
    zones_count = db.scalar(select(func.count(Zone.id)).where(Zone.region_id == reg.id)) or 0
    reports_count = db.scalar(
        select(func.count(ReportFile.id)).where(
            ReportFile.region_id == reg.id, ReportFile.status == "active"
        )
    ) or 0
    return RegionOut(
        id=reg.id,
        customer_id=reg.customer_id,
        customer_name=reg.customer.customer_name,
        region_name=reg.region_name,
        status=reg.status,
        zones_count=zones_count,
        report_files_count=reports_count,
        created_at=reg.created_at,
        updated_at=reg.updated_at,
    )


def delete_region(db: Session, region_id: int, user_id: int, ip: str | None) -> None:
    reg = db.get(Region, region_id)
    if reg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found.")

    has_reports = db.scalar(select(ReportFile.id).where(ReportFile.region_id == region_id))
    has_merged = db.scalar(select(MergedReport.id).where(MergedReport.region_id == region_id))
    has_zones = db.scalar(select(Zone.id).where(Zone.region_id == region_id))
    if has_reports or has_merged or has_zones:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete region containing zones or uploaded reports. Deactivate it instead.",
        )

    record_audit_log(
        db,
        user_id=user_id,
        action="region.delete",
        entity_type="region",
        entity_id=reg.id,
        details={"region_name": reg.region_name},
        ip_address=ip,
    )
    db.delete(reg)
    db.commit()


def list_zones(
    db: Session, auth: AuthContext, region_id: int | None = None, customer_id: int | None = None
) -> list[ZoneOut]:
    stmt = (
        select(Zone)
        .join(Region, Zone.region_id == Region.id)
        .options(selectinload(Zone.region).selectinload(Region.customer))
        .order_by(Zone.zone_name.asc())
    )
    if region_id is not None:
        reg = db.get(Region, region_id)
        if reg is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found.")
        verify_customer_access(auth, reg.customer_id)
        stmt = stmt.where(Zone.region_id == region_id)
    elif customer_id is not None:
        verify_customer_access(auth, customer_id)
        stmt = stmt.where(Region.customer_id == customer_id)
    elif auth.authorized_customer_ids is not None:
        if not auth.authorized_customer_ids:
            return []
        stmt = stmt.where(Region.customer_id.in_(auth.authorized_customer_ids))

    if auth.user.role != "admin":
        stmt = stmt.where(Zone.status == "active", Region.status == "active")

    zones = db.scalars(stmt).all()
    if not zones:
        return []

    zone_ids = [z.id for z in zones]
    active_reports = db.execute(
        select(ReportFile.zone_id, ReportFile.report_type).where(
            ReportFile.zone_id.in_(zone_ids), ReportFile.status == "active"
        )
    ).all()
    report_map: dict[int, set[str]] = {}
    for zid, rtype in active_reports:
        report_map.setdefault(zid, set()).add(rtype)

    merged_rows = db.execute(
        select(MergedReport.zone_id, MergedReport.status).where(MergedReport.zone_id.in_(zone_ids))
    ).all()
    merged_map = {zid: mstatus for zid, mstatus in merged_rows}

    out: list[ZoneOut] = []
    for z in zones:
        rset = report_map.get(z.id, set())
        m_status = merged_map.get(z.id)
        if auth.user.role != "admin" and m_status != "published":
            m_status = None
        out.append(
            ZoneOut(
                id=z.id,
                region_id=z.region_id,
                region_name=z.region.region_name,
                customer_id=z.region.customer_id,
                customer_name=z.region.customer.customer_name,
                zone_name=z.zone_name,
                status=z.status,
                has_pole_survey="pole_survey" in rset,
                has_lamp_installation="lamp_installation" in rset,
                merged_status=m_status,
                created_at=z.created_at,
                updated_at=z.updated_at,
            )
        )
    return out


def create_zone(db: Session, payload: ZoneCreate, user_id: int, ip: str | None) -> ZoneOut:
    reg = db.scalar(
        select(Region).options(selectinload(Region.customer)).where(Region.id == payload.region_id)
    )
    if reg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found.")

    name = payload.zone_name.strip()
    dup = db.scalar(
        select(Zone).where(
            Zone.region_id == payload.region_id,
            func.lower(Zone.zone_name) == name.lower(),
        )
    )
    if dup is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Zone '{name}' already exists in region {reg.region_name}.",
        )

    zone = Zone(region_id=payload.region_id, zone_name=name, status=payload.status)
    db.add(zone)
    db.flush()
    record_audit_log(
        db,
        user_id=user_id,
        action="zone.create",
        entity_type="zone",
        entity_id=zone.id,
        details={"region_id": zone.region_id, "zone_name": zone.zone_name},
        ip_address=ip,
    )
    db.commit()
    db.refresh(zone)
    return ZoneOut(
        id=zone.id,
        region_id=zone.region_id,
        region_name=reg.region_name,
        customer_id=reg.customer_id,
        customer_name=reg.customer.customer_name,
        zone_name=zone.zone_name,
        status=zone.status,
        created_at=zone.created_at,
        updated_at=zone.updated_at,
    )


def update_zone(
    db: Session, zone_id: int, payload: ZoneUpdate, user_id: int, ip: str | None
) -> ZoneOut:
    zone = db.scalar(
        select(Zone)
        .options(selectinload(Zone.region).selectinload(Region.customer))
        .where(Zone.id == zone_id)
    )
    if zone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found.")

    if payload.zone_name is not None:
        name = payload.zone_name.strip()
        dup = db.scalar(
            select(Zone).where(
                Zone.region_id == zone.region_id,
                func.lower(Zone.zone_name) == name.lower(),
                Zone.id != zone_id,
            )
        )
        if dup is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Zone '{name}' already exists in this region.",
            )
        zone.zone_name = name

    if payload.status is not None:
        zone.status = payload.status

    record_audit_log(
        db,
        user_id=user_id,
        action="zone.update",
        entity_type="zone",
        entity_id=zone.id,
        details={"zone_name": zone.zone_name, "status": zone.status},
        ip_address=ip,
    )
    db.commit()
    db.refresh(zone)

    active_types = set(
        db.scalars(
            select(ReportFile.report_type).where(
                ReportFile.zone_id == zone.id, ReportFile.status == "active"
            )
        ).all()
    )
    m_status = db.scalar(select(MergedReport.status).where(MergedReport.zone_id == zone.id))
    return ZoneOut(
        id=zone.id,
        region_id=zone.region_id,
        region_name=zone.region.region_name,
        customer_id=zone.region.customer_id,
        customer_name=zone.region.customer.customer_name,
        zone_name=zone.zone_name,
        status=zone.status,
        has_pole_survey="pole_survey" in active_types,
        has_lamp_installation="lamp_installation" in active_types,
        merged_status=m_status,
        created_at=zone.created_at,
        updated_at=zone.updated_at,
    )


def delete_zone(db: Session, zone_id: int, user_id: int, ip: str | None) -> None:
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found.")

    has_reports = db.scalar(select(ReportFile.id).where(ReportFile.zone_id == zone_id))
    has_merged = db.scalar(select(MergedReport.id).where(MergedReport.zone_id == zone_id))
    if has_reports or has_merged:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete zone containing uploaded or merged reports. Deactivate it instead.",
        )

    record_audit_log(
        db,
        user_id=user_id,
        action="zone.delete",
        entity_type="zone",
        entity_id=zone.id,
        details={"zone_name": zone.zone_name},
        ip_address=ip,
    )
    db.delete(zone)
    db.commit()


def get_hierarchy_tree(db: Session, auth: AuthContext) -> list[HierarchyCustomerNode]:
    stmt = (
        select(Customer)
        .options(selectinload(Customer.regions).selectinload(Region.zones))
        .order_by(Customer.customer_name.asc())
    )
    if auth.authorized_customer_ids is not None:
        if not auth.authorized_customer_ids:
            return []
        stmt = stmt.where(
            Customer.id.in_(auth.authorized_customer_ids),
            Customer.status == "active",
        )

    customers = db.scalars(stmt).all()

    active_reports = db.execute(
        select(ReportFile.zone_id, ReportFile.report_type).where(ReportFile.status == "active")
    ).all()
    report_map: dict[int, set[str]] = {}
    for zid, rtype in active_reports:
        report_map.setdefault(zid, set()).add(rtype)

    merged_rows = db.execute(
        select(
            MergedReport.zone_id,
            MergedReport.status,
            MergedReport.published_at,
        )
    ).all()
    merged_map = {zid: (mstatus, pub_at is not None) for zid, mstatus, pub_at in merged_rows}

    is_admin = auth.user.role == "admin"
    tree: list[HierarchyCustomerNode] = []

    for cust in customers:
        region_nodes: list[HierarchyRegionNode] = []
        total_zones = 0
        sorted_regions = sorted(cust.regions, key=lambda r: r.region_name.lower())
        for reg in sorted_regions:
            if not is_admin and reg.status != "active":
                continue
            zone_nodes: list[HierarchyZoneNode] = []
            for z in sorted(reg.zones, key=lambda zn: zn.zone_name.lower()):
                if not is_admin and z.status != "active":
                    continue
                rset = report_map.get(z.id, set())
                m_status, has_pub = merged_map.get(z.id, (None, False))
                visible_m_status = m_status if is_admin else ("published" if has_pub else None)
                zone_nodes.append(
                    HierarchyZoneNode(
                        id=z.id,
                        region_id=z.region_id,
                        zone_name=z.zone_name,
                        status=z.status,
                        has_pole_survey="pole_survey" in rset,
                        has_lamp_installation="lamp_installation" in rset,
                        merged_status=visible_m_status,
                        has_published_merged=has_pub,
                    )
                )
            total_zones += len(zone_nodes)
            region_nodes.append(
                HierarchyRegionNode(
                    id=reg.id,
                    customer_id=reg.customer_id,
                    region_name=reg.region_name,
                    status=reg.status,
                    zones_count=len(zone_nodes),
                    zones=zone_nodes,
                )
            )
        tree.append(
            HierarchyCustomerNode(
                id=cust.id,
                customer_name=cust.customer_name,
                status=cust.status,
                regions_count=len(region_nodes),
                zones_count=total_zones,
                regions=region_nodes,
            )
        )

    return tree


def validate_zone_hierarchy(
    db: Session, *, customer_id: int, region_id: int, zone_id: int
) -> tuple[Customer, Region, Zone]:
    zone = db.scalar(
        select(Zone)
        .options(selectinload(Zone.region).selectinload(Region.customer))
        .where(Zone.id == zone_id)
    )
    if zone is None or zone.region is None or zone.region.customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Selected zone does not exist.")
    if zone.region_id != region_id or zone.region.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zone does not belong to the selected customer and region.",
        )
    return zone.region.customer, zone.region, zone

