from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import AuthContext, get_client_ip, get_current_auth, require_admin
from app.database.session import get_db
from app.schemas.common import MessageResponse
from app.schemas.hierarchy import RegionCreate, RegionOut, RegionUpdate
from app.services.hierarchy_service import (
    create_region,
    delete_region,
    list_regions,
    update_region,
)


router = APIRouter(prefix="/regions", tags=["Regions"])


@router.get("", response_model=list[RegionOut])
def get_regions(
    customer_id: int | None = Query(default=None),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[RegionOut]:
    return list_regions(db, auth, customer_id=customer_id)


@router.post("", response_model=RegionOut, status_code=status.HTTP_201_CREATED)
def post_region(
    payload: RegionCreate,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RegionOut:
    return create_region(db, payload, auth.user.id, get_client_ip(request))


@router.put("/{region_id}", response_model=RegionOut)
def put_region(
    region_id: int,
    payload: RegionUpdate,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RegionOut:
    return update_region(db, region_id, payload, auth.user.id, get_client_ip(request))


@router.delete("/{region_id}", response_model=MessageResponse)
def remove_region(
    region_id: int,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    delete_region(db, region_id, auth.user.id, get_client_ip(request))
    return MessageResponse(message="Region deleted successfully.")

