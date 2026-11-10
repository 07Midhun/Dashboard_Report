from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.dependencies import AuthContext, get_client_ip, get_current_auth, require_admin
from app.database.session import get_db
from app.schemas.admin import ExternalLinkOut, ExternalLinksBulkUpdate
from app.services.admin_service import list_external_links, update_external_links


router = APIRouter(prefix="/external-links", tags=["External Links"])


@router.get("", response_model=list[ExternalLinkOut])
def get_external_links(
    _: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[ExternalLinkOut]:
    return list_external_links(db)


@router.put("", response_model=list[ExternalLinkOut])
def put_external_links(
    payload: ExternalLinksBulkUpdate,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[ExternalLinkOut]:
    return update_external_links(db, payload, auth.user.id, get_client_ip(request))

