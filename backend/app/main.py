import sys
from pathlib import Path

# Ensure backend root is in sys.path so 'from app...' imports work regardless of cwd
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

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
    wards,
    zones,
)
from app.core.config import settings
from app.database.session import get_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    settings.temp_processing_dir.mkdir(parents=True, exist_ok=True)

    # Automatically create all database tables and seed default users
    try:
        from app.database.session import engine, SessionLocal
        from app.database.base import Base
        from app.database.auto_migrate import auto_heal_schema
        import app.models  # noqa: F401

        # Run safe idempotent schema patches first to ensure existing tables have all columns
        auto_heal_schema(engine)

        # Create any remaining missing tables
        Base.metadata.create_all(bind=engine)

        if settings.seed_default_data:
            from app.database.seed import seed_initial_data
            with SessionLocal() as db:
                seed_initial_data(db)
    except Exception as exc:
        print(f"Startup database initialization error: {exc}")

    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^https?://.*" if ("*" in settings.cors_origins or settings.app_env != "production") else r"^https://.*\.pages\.dev$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.api_route("/", methods=["GET", "HEAD"], tags=["Root"])
def root() -> dict[str, str]:
    return {
        "app": settings.app_name,
        "status": "online",
        "health": "/api/health",
        "docs": "/docs",
    }


@app.api_route("/api/health", methods=["GET", "HEAD"], tags=["Health"])
def health_check(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected", "environment": settings.app_env}


@app.get("/api/db-diagnostics", tags=["Diagnostics"])
def db_diagnostics(db: Session = Depends(get_db)):
    try:
        tables = db.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        ).scalars().all()
        user_cols = db.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'")
        ).scalars().all()
        admin_count = db.execute(
            text("SELECT count(*) FROM users WHERE lower(email) = 'admin@gmail.com'")
        ).scalar()
        return {
            "status": "ok",
            "tables": tables,
            "users_columns": user_cols,
            "admin_user_exists": (admin_count or 0) > 0,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


app.include_router(auth.router, prefix="/api")
app.include_router(customers.router, prefix="/api")
app.include_router(regions.router, prefix="/api")
app.include_router(zones.router, prefix="/api")
app.include_router(wards.router, prefix="/api")
app.include_router(hierarchy.router, prefix="/api")
app.include_router(pole_survey.router, prefix="/api")
app.include_router(lamp_installation.router, prefix="/api")
app.include_router(merged_reports.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(external_links.router, prefix="/api")
app.include_router(admin_routes.router, prefix="/api")
