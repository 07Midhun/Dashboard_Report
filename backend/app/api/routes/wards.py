from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import AuthContext, get_client_ip, get_current_auth, require_admin
from app.database.session import get_db
from app.schemas.common import MessageResponse
from app.schemas.hierarchy import WardCreate, WardOut, WardUpdate
from app.services.hierarchy_service import (
    create_ward,
    delete_ward,
    list_wards,
    update_ward,
)


router = APIRouter(prefix="/wards", tags=["Wards"])


@router.get("", response_model=list[WardOut])
def get_wards(
    zone_id: int | None = Query(default=None),
    region_id: int | None = Query(default=None),
    customer_id: int | None = Query(default=None),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[WardOut]:
    return list_wards(
        db,
        auth,
        zone_id=zone_id,
        region_id=region_id,
        customer_id=customer_id,
    )


@router.post("", response_model=WardOut, status_code=status.HTTP_201_CREATED)
def post_ward(
    payload: WardCreate,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WardOut:
    return create_ward(db, payload, auth.user.id, get_client_ip(request))


@router.put("/{ward_id}", response_model=WardOut)
def put_ward(
    ward_id: int,
    payload: WardUpdate,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WardOut:
    return update_ward(db, ward_id, payload, auth.user.id, get_client_ip(request))


@router.delete("/{ward_id}", response_model=MessageResponse)
def remove_ward(
    ward_id: int,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    delete_ward(db, ward_id, auth.user.id, get_client_ip(request))
    return MessageResponse(message="Ward deleted successfully.")
