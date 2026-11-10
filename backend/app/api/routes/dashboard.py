from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import AuthContext, get_current_auth, require_admin
from app.database.session import get_db
from app.schemas.reports import AdminDashboardOut, CustomerDashboardOut
from app.services.dashboard_service import get_admin_dashboard, get_customer_dashboard


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/admin", response_model=AdminDashboardOut)
def admin_dashboard(
    customer_id: int | None = Query(default=None),
    region_id: int | None = Query(default=None),
    zone_id: int | None = Query(default=None),
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminDashboardOut:
    return get_admin_dashboard(
        db,
        customer_id=customer_id,
        region_id=region_id,
        zone_id=zone_id,
    )


@router.get("/customer", response_model=CustomerDashboardOut)
def customer_dashboard(
    customer_id: int | None = Query(default=None),
    region_id: int | None = Query(default=None),
    zone_id: int | None = Query(default=None),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> CustomerDashboardOut:
    return get_customer_dashboard(
        db,
        auth,
        customer_id=customer_id,
        region_id=region_id,
        zone_id=zone_id,
    )

