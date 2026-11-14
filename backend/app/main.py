import sys
from pathlib import Path

# Ensure backend root is in sys.path so 'from app...' imports work regardless of cwd
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
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

startup_error: str | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global startup_error
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
        startup_error = str(exc)
        print(f"Startup database initialization error: {exc}")

    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    import traceback

    tb = traceback.format_exc()
    print(f"Unhandled error on {request.method} {request.url.path}: {tb}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"{exc.__class__.__name__}: {str(exc)}"},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^https?://.*",
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
def db_diagnostics(reseed: bool = False, db: Session = Depends(get_db)):
    global startup_error
    reseed_result = None
    if reseed:
        try:
            from app.database.auto_migrate import auto_heal_schema
            from app.database.seed import seed_initial_data
            from app.database.session import engine
            auto_heal_schema(engine)
            seed_initial_data(db)
            startup_error = None
            reseed_result = "success"
        except Exception as err:
            startup_error = str(err)
            reseed_result = f"failed: {err}"

    try:
        tables = db.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        ).scalars().all()
        user_cols = db.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'")
        ).scalars().all()
        region_cols = db.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'regions'")
        ).scalars().all()
        zone_cols = db.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'zones'")
        ).scalars().all()
        ward_cols = db.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'wards'")
        ).scalars().all()
        audit_cols = db.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'audit_logs'")
        ).scalars().all()
        has_admin = False
        admin_info = None
        if "email" in user_cols:
            admin_row = db.execute(
                text("SELECT id, name, email, username, role, status FROM users WHERE lower(email) = 'admin@gmail.com' LIMIT 1")
            ).first()
            if admin_row:
                has_admin = True
                admin_info = {
                    "id": admin_row[0],
                    "name": admin_row[1],
                    "email": admin_row[2],
                    "username": admin_row[3],
                    "role": admin_row[4],
                    "status": admin_row[5],
                }
        regions_data = []
        if "region_name" in region_cols:
            rows = db.execute(text("SELECT id, customer_id, region_name, region_code, status FROM regions")).all()
            regions_data = [{"id": r[0], "customer_id": r[1], "region_name": r[2], "region_code": r[3], "status": r[4]} for r in rows]
        return {
            "status": "ok",
            "reseed_result": reseed_result,
            "startup_error": startup_error,
            "tables": tables,
            "users_columns": user_cols,
            "region_columns": region_cols,
            "zone_columns": zone_cols,
            "ward_columns": ward_cols,
            "audit_columns": audit_cols,
            "regions": regions_data,
            "admin_user_exists": has_admin,
            "admin_info": admin_info,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "startup_error": startup_error}


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
