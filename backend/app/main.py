from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes import (
    admin_routes,
    auth,
    customers,
    dashboard,
    external_links,
    hierarchy,
    lamp_installation,
    merged_reports,
    pole_survey,
    regions,
    zones,
)
from app.core.config import settings
from app.database.session import get_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    settings.temp_processing_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected", "environment": settings.app_env}


app.include_router(auth.router, prefix="/api")
app.include_router(customers.router, prefix="/api")
app.include_router(regions.router, prefix="/api")
app.include_router(zones.router, prefix="/api")
app.include_router(hierarchy.router, prefix="/api")
app.include_router(pole_survey.router, prefix="/api")
app.include_router(lamp_installation.router, prefix="/api")
app.include_router(merged_reports.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(external_links.router, prefix="/api")
app.include_router(admin_routes.router, prefix="/api")
