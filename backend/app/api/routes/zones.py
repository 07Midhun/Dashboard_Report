from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import AuthContext, get_client_ip, get_current_auth, require_admin
from app.database.session import get_db
from app.schemas.common import MessageResponse
from app.schemas.hierarchy import ZoneCreate, ZoneOut, ZoneUpdate
from app.services.hierarchy_service import (
    create_zone,
    delete_zone,
    list_zones,
    update_zone,
)


router = APIRouter(prefix="/zones", tags=["Zones"])


@router.get("", response_model=list[ZoneOut])
def get_zones(
    region_id: int | None = Query(default=None),
    customer_id: int | None = Query(default=None),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[ZoneOut]:
    return list_zones(db, auth, region_id=region_id, customer_id=customer_id)


@router.post("", response_model=ZoneOut, status_code=status.HTTP_201_CREATED)
def post_zone(
    payload: ZoneCreate,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ZoneOut:
    return create_zone(db, payload, auth.user.id, get_client_ip(request))


@router.put("/{zone_id}", response_model=ZoneOut)
def put_zone(
    zone_id: int,
    payload: ZoneUpdate,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ZoneOut:
    return update_zone(db, zone_id, payload, auth.user.id, get_client_ip(request))


@router.delete("/{zone_id}", response_model=MessageResponse)
def remove_zone(
    zone_id: int,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    delete_zone(db, zone_id, auth.user.id, get_client_ip(request))
    return MessageResponse(message="Zone deleted successfully.")

