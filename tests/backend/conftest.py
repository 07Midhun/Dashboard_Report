import os
from pathlib import Path
import shutil
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres@127.0.0.1:5432/schnell_reports_test",
)
TEST_STORAGE_ROOT = Path(__file__).resolve().parent / ".test_storage"

os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["STORAGE_ROOT"] = str(TEST_STORAGE_ROOT)
os.environ["TEMP_PROCESSING_DIR"] = str(TEST_STORAGE_ROOT / "_tmp")
os.environ["APP_ENV"] = "testing"

from app.core.config import settings  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.database.seed import seed_initial_data  # noqa: E402
from app.database.session import get_db  # noqa: E402
import app.models  # noqa: F401, E402
from app.main import app as fastapi_app  # noqa: E402


engine = create_engine(TEST_DB_URL, pool_pre_ping=True, future=True)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    settings.storage_root = TEST_STORAGE_ROOT
    settings.temp_processing_dir = TEST_STORAGE_ROOT / "_tmp"
    TEST_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    settings.temp_processing_dir.mkdir(parents=True, exist_ok=True)

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db:
        seed_initial_data(db)

    yield

    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if TEST_STORAGE_ROOT.exists():
        shutil.rmtree(TEST_STORAGE_ROOT, ignore_errors=True)


@pytest.fixture()
def db_session():
    with TestingSessionLocal() as db:
        yield db


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def admin_headers(client):
    resp = client.post(
        "/api/auth/login",
        json={
            "identifier": settings.seed_admin_email,
            "password": settings.seed_admin_password,
            "login_type": "admin",
        },
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def customer_headers(client):
    resp = client.post(
        "/api/auth/login",
        json={
            "identifier": settings.seed_customer_user_email,
            "password": settings.seed_customer_user_password,
            "login_type": "customer",
        },
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
