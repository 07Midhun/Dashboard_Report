from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import AuthContext, get_current_auth
from app.database.session import get_db
from app.schemas.hierarchy import HierarchyCustomerNode
from app.services.hierarchy_service import get_hierarchy_tree


router = APIRouter(prefix="/hierarchy", tags=["Hierarchy"])


@router.get("/tree", response_model=list[HierarchyCustomerNode])
def read_hierarchy_tree(
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[HierarchyCustomerNode]:
    return get_hierarchy_tree(db, auth)

