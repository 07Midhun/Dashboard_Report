from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import AuthContext, get_client_ip, get_current_auth, require_admin
from app.database.session import get_db
from app.schemas.common import MessageResponse
from app.schemas.hierarchy import CustomerCreate, CustomerOut, CustomerUpdate
from app.services.hierarchy_service import (
    create_customer,
    delete_customer,
    list_customers,
    update_customer,
)


router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("", response_model=list[CustomerOut])
def get_customers(
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[CustomerOut]:
    return list_customers(db, auth)


@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def post_customer(
    payload: CustomerCreate,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CustomerOut:
    return create_customer(db, payload, auth.user.id, get_client_ip(request))


@router.put("/{customer_id}", response_model=CustomerOut)
def put_customer(
    customer_id: int,
    payload: CustomerUpdate,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CustomerOut:
    return update_customer(db, customer_id, payload, auth.user.id, get_client_ip(request))


@router.delete("/{customer_id}", response_model=MessageResponse)
def remove_customer(
    customer_id: int,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    delete_customer(db, customer_id, auth.user.id, get_client_ip(request))
    return MessageResponse(message="Customer deleted successfully.")

