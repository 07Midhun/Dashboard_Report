import re
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.dependencies import AuthContext, verify_customer_access
from app.models.hierarchy import Customer, Region, Ward, Zone
from app.models.report import MergedReport, ProcessingLog, ReportFile
from app.schemas.hierarchy import (
    CustomerCreate,
    CustomerOut,
    CustomerUpdate,
    HierarchyCustomerNode,
    HierarchyRegionNode,
    HierarchyWardNode,
    HierarchyZoneNode,
    RegionCreate,
    RegionOut,
    RegionUpdate,
    WardCreate,
    WardOut,
    WardUpdate,
    ZoneCreate,
    ZoneOut,
    ZoneUpdate,
)
from app.services.audit_service import record_audit_log


def _ward_sort_key(ward: Ward) -> tuple[tuple[int, int | str], ...]:
    label = (ward.ward_number or ward.ward_name or "").strip().upper()
    parts = re.split(r"(\d+)", label)
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in parts if p)


DEFAULT_REGION_CODE_MAP = {
    "BOMMANAHALLI": "BMH",
    "EAST": "EAST",
}


def derive_region_code(name: str) -> str:
    cleaned = (name or "").strip()
    upper = cleaned.upper()
    if upper in DEFAULT_REGION_CODE_MAP:
        return DEFAULT_REGION_CODE_MAP[upper]
    alphanumeric = re.sub(r"[^A-Za-z0-9]", "", upper)
    return alphanumeric[:10] if alphanumeric else "REG"


def _normalize_zone_code(code: str | None) -> str | None:
    if code is None:
        return None
    cleaned = code.strip().upper()
    return cleaned or None


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
        wards_count = db.scalar(
            select(func.count(Ward.id))
            .join(Zone, Ward.zone_id == Zone.id)
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
                wards_count=wards_count,
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
    wards_count = db.scalar(
        select(func.count(Ward.id))
        .join(Zone, Ward.zone_id == Zone.id)
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
        wards_count=wards_count,
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
        wards_count = db.scalar(
            select(func.count(Ward.id))
            .join(Zone, Ward.zone_id == Zone.id)
            .where(Zone.region_id == reg.id)
        ) or 0
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
                region_code=reg.region_code,
                status=reg.status,
                zones_count=zones_count,
                wards_count=wards_count,
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

    code = (payload.region_code or "").strip().upper()
    if not code:
        code = derive_region_code(name)

    dup_code = db.scalar(
        select(Region).where(
            Region.customer_id == payload.customer_id,
            func.upper(Region.region_code) == code.upper(),
        )
    )
    if dup_code is not None:
        if payload.region_code:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Region code '{code}' already exists under {cust.customer_name}.",
            )
        suffix = 1
        base_code = code[:8]
        while dup_code is not None and suffix < 100:
            candidate = f"{base_code}{suffix}"
            dup_code = db.scalar(
                select(Region).where(
                    Region.customer_id == payload.customer_id,
                    func.upper(Region.region_code) == candidate.upper(),
                )
            )
            if dup_code is None:
                code = candidate
                break
            suffix += 1

    reg = Region(
        customer_id=payload.customer_id,
        region_name=name,
        region_code=code,
        corporation="BBMP",
        division="",
        status=payload.status,
    )
    db.add(reg)
    db.flush()
    record_audit_log(
        db,
        user_id=user_id,
        action="region.create",
        entity_type="region",
        entity_id=reg.id,
        details={
            "customer_id": reg.customer_id,
            "region_name": reg.region_name,
            "region_code": reg.region_code,
        },
        ip_address=ip,
    )
    db.commit()
    db.refresh(reg)
    return RegionOut(
        id=reg.id,
        customer_id=reg.customer_id,
        customer_name=cust.customer_name,
        region_name=reg.region_name,
        region_code=reg.region_code,
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

    if payload.region_code is not None:
        code = payload.region_code.strip().upper()
        if not code:
            code = derive_region_code(reg.region_name)
        dup_code = db.scalar(
            select(Region).where(
                Region.customer_id == reg.customer_id,
                func.upper(Region.region_code) == code.upper(),
                Region.id != region_id,
            )
        )
        if dup_code is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Region code '{code}' already exists under this customer.",
            )
        reg.region_code = code

    if payload.status is not None:
        reg.status = payload.status

    record_audit_log(
        db,
        user_id=user_id,
        action="region.update",
        entity_type="region",
        entity_id=reg.id,
        details={
            "region_name": reg.region_name,
            "region_code": reg.region_code,
            "status": reg.status,
        },
        ip_address=ip,
    )
    db.commit()
    db.refresh(reg)
    zones_count = db.scalar(select(func.count(Zone.id)).where(Zone.region_id == reg.id)) or 0
    wards_count = db.scalar(
        select(func.count(Ward.id))
        .join(Zone, Ward.zone_id == Zone.id)
        .where(Zone.region_id == reg.id)
    ) or 0
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
        region_code=reg.region_code,
        status=reg.status,
        zones_count=zones_count,
        wards_count=wards_count,
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

    out: list[ZoneOut] = []
    for z in zones:
        ward_stmt = select(func.count(Ward.id)).where(Ward.zone_id == z.id)
        if auth.user.role != "admin":
            ward_stmt = ward_stmt.where(Ward.status == "active")
        wards_count = db.scalar(ward_stmt) or 0
        reports_count = db.scalar(
            select(func.count(ReportFile.id)).where(
                ReportFile.zone_id == z.id, ReportFile.status == "active"
            )
        ) or 0
        out.append(
            ZoneOut(
                id=z.id,
                region_id=z.region_id,
                region_name=z.region.region_name,
                customer_id=z.region.customer_id,
                customer_name=z.region.customer.customer_name,
                zone_name=z.zone_name,
                zone_code=z.zone_code,
                status=z.status,
                wards_count=wards_count,
                report_files_count=reports_count,
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

    zone_code = _normalize_zone_code(payload.zone_code)
    if zone_code is not None:
        dup_code = db.scalar(
            select(Zone).where(
                Zone.region_id == payload.region_id,
                func.lower(Zone.zone_code) == zone_code.lower(),
            )
        )
        if dup_code is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Zone code '{zone_code}' already exists in region {reg.region_name}.",
            )

    zone = Zone(
        region_id=payload.region_id,
        zone_name=name,
        zone_code=zone_code,
        status=payload.status,
    )
    db.add(zone)
    db.flush()
    record_audit_log(
        db,
        user_id=user_id,
        action="zone.create",
        entity_type="zone",
        entity_id=zone.id,
        details={
            "region_id": zone.region_id,
            "zone_name": zone.zone_name,
            "zone_code": zone.zone_code,
        },
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
        zone_code=zone.zone_code,
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

    if payload.zone_code is not None:
        zone_code = _normalize_zone_code(payload.zone_code)
        if zone_code is not None:
            dup_code = db.scalar(
                select(Zone).where(
                    Zone.region_id == zone.region_id,
                    func.lower(Zone.zone_code) == zone_code.lower(),
                    Zone.id != zone_id,
                )
            )
            if dup_code is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Zone code '{zone_code}' already exists in this region.",
                )
        zone.zone_code = zone_code

    if payload.status is not None:
        zone.status = payload.status

    record_audit_log(
        db,
        user_id=user_id,
        action="zone.update",
        entity_type="zone",
        entity_id=zone.id,
        details={
            "zone_name": zone.zone_name,
            "zone_code": zone.zone_code,
            "status": zone.status,
        },
        ip_address=ip,
    )
    db.commit()
    db.refresh(zone)

    wards_count = db.scalar(select(func.count(Ward.id)).where(Ward.zone_id == zone.id)) or 0
    reports_count = db.scalar(
        select(func.count(ReportFile.id)).where(
            ReportFile.zone_id == zone.id, ReportFile.status == "active"
        )
    ) or 0
    return ZoneOut(
        id=zone.id,
        region_id=zone.region_id,
        region_name=zone.region.region_name,
        customer_id=zone.region.customer_id,
        customer_name=zone.region.customer.customer_name,
        zone_name=zone.zone_name,
        zone_code=zone.zone_code,
        status=zone.status,
        wards_count=wards_count,
        report_files_count=reports_count,
        created_at=zone.created_at,
        updated_at=zone.updated_at,
    )


def delete_zone(db: Session, zone_id: int, user_id: int, ip: str | None) -> None:
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found.")

    has_wards = db.scalar(select(Ward.id).where(Ward.zone_id == zone_id))
    has_reports = db.scalar(select(ReportFile.id).where(ReportFile.zone_id == zone_id))
    has_merged = db.scalar(select(MergedReport.id).where(MergedReport.zone_id == zone_id))
    has_logs = db.scalar(select(ProcessingLog.id).where(ProcessingLog.zone_id == zone_id))
    if has_wards or has_reports or has_merged or has_logs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete zone containing wards or uploaded reports. Deactivate it instead.",
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


def list_wards(
    db: Session,
    auth: AuthContext,
    zone_id: int | None = None,
    region_id: int | None = None,
    customer_id: int | None = None,
) -> list[WardOut]:
    stmt = (
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

    if zone_id is not None:
        z = db.scalar(select(Zone).options(selectinload(Zone.region)).where(Zone.id == zone_id))
        if z is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found.")
        verify_customer_access(auth, z.region.customer_id)
        stmt = stmt.where(Ward.zone_id == zone_id)
    elif region_id is not None:
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

    is_admin = auth.user.role == "admin"
    if not is_admin:
        stmt = stmt.where(
            Ward.status == "active",
            Zone.status == "active",
            Region.status == "active",
            Customer.status == "active",
        )

    wards = sorted(db.scalars(stmt).all(), key=_ward_sort_key)
    if not wards:
        return []

    ward_ids = [w.id for w in wards]
    active_reports = db.execute(
        select(ReportFile.ward_id, ReportFile.report_type).where(
            ReportFile.ward_id.in_(ward_ids), ReportFile.status == "active"
        )
    ).all()
    report_map: dict[int, set[str]] = {}
    for wid, rtype in active_reports:
        report_map.setdefault(wid, set()).add(rtype)

    merged_rows = db.execute(
        select(MergedReport.ward_id, MergedReport.status, MergedReport.published_at).where(
            MergedReport.ward_id.in_(ward_ids)
        )
    ).all()
    merged_map = {wid: (mstatus, pub_at is not None) for wid, mstatus, pub_at in merged_rows}

    out: list[WardOut] = []
    for w in wards:
        rset = report_map.get(w.id, set())
        m_status, has_pub = merged_map.get(w.id, (None, False))
        visible_m_status = m_status if is_admin else ("published" if has_pub else None)
        out.append(
            WardOut(
                id=w.id,
                zone_id=w.zone_id,
                zone_name=w.zone.zone_name,
                zone_code=w.zone.zone_code,
                region_id=w.zone.region_id,
                region_name=w.zone.region.region_name,
                customer_id=w.zone.region.customer_id,
                customer_name=w.zone.region.customer.customer_name,
                ward_name=w.ward_name,
                ward_number=w.ward_number,
                ward_code=w.ward_code,
                status=w.status,
                has_pole_survey="pole_survey" in rset,
                has_lamp_installation="lamp_installation" in rset,
                merged_status=visible_m_status,
                has_published_merged=has_pub,
                created_at=w.created_at,
                updated_at=w.updated_at,
            )
        )
    return out


def create_ward(db: Session, payload: WardCreate, user_id: int, ip: str | None) -> WardOut:
    zone = db.scalar(
        select(Zone)
        .options(selectinload(Zone.region).selectinload(Region.customer))
        .where(Zone.id == payload.zone_id)
    )
    if zone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found.")

    ward_name = payload.ward_name.strip()
    ward_number = payload.ward_number.strip().upper()
    ward_code = (
        payload.ward_code.strip().upper()
        if payload.ward_code and payload.ward_code.strip()
        else ward_number
    )

    if not ward_name or not ward_number or not ward_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ward name, ward number, and ward code cannot be blank.",
        )

    dup_num = db.scalar(
        select(Ward).where(
            Ward.zone_id == payload.zone_id,
            func.lower(Ward.ward_number) == ward_number.lower(),
        )
    )
    if dup_num is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ward number '{ward_number}' already exists in zone {zone.zone_name}.",
        )

    dup_code = db.scalar(
        select(Ward).where(
            Ward.zone_id == payload.zone_id,
            func.lower(Ward.ward_code) == ward_code.lower(),
        )
    )
    if dup_code is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ward code '{ward_code}' already exists in zone {zone.zone_name}.",
        )

    ward = Ward(
        zone_id=payload.zone_id,
        ward_name=ward_name,
        ward_number=ward_number,
        ward_code=ward_code,
        status=payload.status,
    )
    db.add(ward)
    db.flush()
    record_audit_log(
        db,
        user_id=user_id,
        action="ward.create",
        entity_type="ward",
        entity_id=ward.id,
        details={
            "zone_id": ward.zone_id,
            "ward_number": ward.ward_number,
            "ward_name": ward.ward_name,
            "ward_code": ward.ward_code,
        },
        ip_address=ip,
    )
    db.commit()
    db.refresh(ward)
    return WardOut(
        id=ward.id,
        zone_id=ward.zone_id,
        zone_name=zone.zone_name,
        zone_code=zone.zone_code,
        region_id=zone.region_id,
        region_name=zone.region.region_name,
        customer_id=zone.region.customer_id,
        customer_name=zone.region.customer.customer_name,
        ward_name=ward.ward_name,
        ward_number=ward.ward_number,
        ward_code=ward.ward_code,
        status=ward.status,
        created_at=ward.created_at,
        updated_at=ward.updated_at,
    )


def update_ward(
    db: Session, ward_id: int, payload: WardUpdate, user_id: int, ip: str | None
) -> WardOut:
    ward = db.scalar(
        select(Ward)
        .options(
            selectinload(Ward.zone)
            .selectinload(Zone.region)
            .selectinload(Region.customer)
        )
        .where(Ward.id == ward_id)
    )
    if ward is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found.")

    if payload.ward_name is not None:
        cleaned = payload.ward_name.strip()
        if not cleaned:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ward name cannot be blank.")
        ward.ward_name = cleaned

    if payload.ward_number is not None:
        ward_number = payload.ward_number.strip().upper()
        if not ward_number:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ward number cannot be blank.")
        dup_num = db.scalar(
            select(Ward).where(
                Ward.zone_id == ward.zone_id,
                func.lower(Ward.ward_number) == ward_number.lower(),
                Ward.id != ward_id,
            )
        )
        if dup_num is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ward number '{ward_number}' already exists in this zone.",
            )
        ward.ward_number = ward_number

    if payload.ward_code is not None:
        ward_code = payload.ward_code.strip().upper()
        if not ward_code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ward code cannot be blank.")
        dup_code = db.scalar(
            select(Ward).where(
                Ward.zone_id == ward.zone_id,
                func.lower(Ward.ward_code) == ward_code.lower(),
                Ward.id != ward_id,
            )
        )
        if dup_code is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ward code '{ward_code}' already exists in this zone.",
            )
        ward.ward_code = ward_code

    if payload.status is not None:
        ward.status = payload.status

    record_audit_log(
        db,
        user_id=user_id,
        action="ward.update",
        entity_type="ward",
        entity_id=ward.id,
        details={
            "ward_number": ward.ward_number,
            "ward_name": ward.ward_name,
            "ward_code": ward.ward_code,
            "status": ward.status,
        },
        ip_address=ip,
    )
    db.commit()
    db.refresh(ward)

    active_types = set(
        db.scalars(
            select(ReportFile.report_type).where(
                ReportFile.ward_id == ward.id, ReportFile.status == "active"
            )
        ).all()
    )
    mr_row = db.execute(
        select(MergedReport.status, MergedReport.published_at).where(MergedReport.ward_id == ward.id)
    ).first()
    m_status = mr_row[0] if mr_row else None
    has_pub = bool(mr_row and mr_row[1] is not None)
    return WardOut(
        id=ward.id,
        zone_id=ward.zone_id,
        zone_name=ward.zone.zone_name,
        zone_code=ward.zone.zone_code,
        region_id=ward.zone.region_id,
        region_name=ward.zone.region.region_name,
        customer_id=ward.zone.region.customer_id,
        customer_name=ward.zone.region.customer.customer_name,
        ward_name=ward.ward_name,
        ward_number=ward.ward_number,
        ward_code=ward.ward_code,
        status=ward.status,
        has_pole_survey="pole_survey" in active_types,
        has_lamp_installation="lamp_installation" in active_types,
        merged_status=m_status,
        has_published_merged=has_pub,
        created_at=ward.created_at,
        updated_at=ward.updated_at,
    )


def delete_ward(db: Session, ward_id: int, user_id: int, ip: str | None) -> None:
    ward = db.get(Ward, ward_id)
    if ward is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ward not found.")

    has_reports = db.scalar(select(ReportFile.id).where(ReportFile.ward_id == ward_id))
    has_merged = db.scalar(select(MergedReport.id).where(MergedReport.ward_id == ward_id))
    has_logs = db.scalar(select(ProcessingLog.id).where(ProcessingLog.ward_id == ward_id))
    if has_reports or has_merged or has_logs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete ward containing uploaded reports, merged reports, or processing history. Deactivate it instead.",
        )

    record_audit_log(
        db,
        user_id=user_id,
        action="ward.delete",
        entity_type="ward",
        entity_id=ward.id,
        details={"ward_number": ward.ward_number, "ward_name": ward.ward_name},
        ip_address=ip,
    )
    db.delete(ward)
    db.commit()


def get_hierarchy_tree(db: Session, auth: AuthContext) -> list[HierarchyCustomerNode]:
    stmt = (
        select(Customer)
        .options(
            selectinload(Customer.regions)
            .selectinload(Region.zones)
            .selectinload(Zone.wards)
        )
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
        select(ReportFile.ward_id, ReportFile.report_type).where(ReportFile.status == "active")
    ).all()
    report_map: dict[int, set[str]] = {}
    for wid, rtype in active_reports:
        report_map.setdefault(wid, set()).add(rtype)

    merged_rows = db.execute(
        select(
            MergedReport.ward_id,
            MergedReport.status,
            MergedReport.published_at,
        )
    ).all()
    merged_map = {wid: (mstatus, pub_at is not None) for wid, mstatus, pub_at in merged_rows}

    is_admin = auth.user.role == "admin"
    tree: list[HierarchyCustomerNode] = []

    for cust in customers:
        region_nodes: list[HierarchyRegionNode] = []
        total_zones = 0
        total_wards = 0
        sorted_regions = sorted(cust.regions, key=lambda r: r.region_name.lower())
        for reg in sorted_regions:
            if not is_admin and reg.status != "active":
                continue
            zone_nodes: list[HierarchyZoneNode] = []
            region_wards_count = 0
            for z in sorted(reg.zones, key=lambda zn: zn.zone_name.lower()):
                if not is_admin and z.status != "active":
                    continue
                ward_nodes: list[HierarchyWardNode] = []
                pole_wards = 0
                lamp_wards = 0
                merged_wards = 0
                for w in sorted(z.wards, key=_ward_sort_key):
                    if not is_admin and w.status != "active":
                        continue
                    rset = report_map.get(w.id, set())
                    m_status, has_pub = merged_map.get(w.id, (None, False))
                    visible_m_status = m_status if is_admin else ("published" if has_pub else None)
                    has_ps = "pole_survey" in rset
                    has_li = "lamp_installation" in rset
                    if has_ps:
                        pole_wards += 1
                    if has_li:
                        lamp_wards += 1
                    if visible_m_status in {"draft", "published", "outdated"}:
                        merged_wards += 1
                    ward_nodes.append(
                        HierarchyWardNode(
                            id=w.id,
                            zone_id=w.zone_id,
                            ward_name=w.ward_name,
                            ward_number=w.ward_number,
                            ward_code=w.ward_code,
                            status=w.status,
                            has_pole_survey=has_ps,
                            has_lamp_installation=has_li,
                            merged_status=visible_m_status,
                            has_published_merged=has_pub,
                        )
                    )
                region_wards_count += len(ward_nodes)
                zone_nodes.append(
                    HierarchyZoneNode(
                        id=z.id,
                        region_id=z.region_id,
                        zone_name=z.zone_name,
                        zone_code=z.zone_code,
                        status=z.status,
                        wards_count=len(ward_nodes),
                        wards_with_pole_survey=pole_wards,
                        wards_with_lamp_installation=lamp_wards,
                        wards_with_merged=merged_wards,
                        wards=ward_nodes,
                    )
                )
            total_zones += len(zone_nodes)
            total_wards += region_wards_count
            region_nodes.append(
                HierarchyRegionNode(
                    id=reg.id,
                    customer_id=reg.customer_id,
                    region_name=reg.region_name,
                    region_code=reg.region_code,
                    status=reg.status,
                    zones_count=len(zone_nodes),
                    wards_count=region_wards_count,
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
                wards_count=total_wards,
                regions=region_nodes,
            )
        )

    return tree


def validate_ward_hierarchy(
    db: Session, *, customer_id: int, region_id: int, zone_id: int, ward_id: int
) -> tuple[Customer, Region, Zone, Ward]:
    ward = db.scalar(
        select(Ward)
        .options(
            selectinload(Ward.zone)
            .selectinload(Zone.region)
            .selectinload(Region.customer)
        )
        .where(Ward.id == ward_id)
    )
    if ward is None or ward.zone is None or ward.zone.region is None or ward.zone.region.customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Selected ward does not exist.",
        )
    if (
        ward.zone_id != zone_id
        or ward.zone.region_id != region_id
        or ward.zone.region.customer_id != customer_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ward does not belong to the selected customer, region, and zone.",
        )
    return ward.zone.region.customer, ward.zone.region, ward.zone, ward
