from pathlib import Path
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator


BASE_DIR = Path(__file__).resolve().parents[3]  # workspace root
BACKEND_DIR = Path(__file__).resolve().parents[2]

# Load environment variables from workspace .env or backend/.env if present
for env_candidate in (BASE_DIR / ".env", BACKEND_DIR / ".env"):
    if env_candidate.exists():
        load_dotenv(env_candidate, override=False)


def normalize_database_url(raw_url: str) -> str:
    url = raw_url.strip()
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+psycopg" not in url.split("://", 1)[0]:
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Settings(BaseModel):
    app_name: str = Field(default="Schnell Electrical Asset Report Management")
    app_env: str = Field(default="development")
    debug: bool = Field(default=False)

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/schnell_reports"
    )

    jwt_secret_key: str = Field(default="dev-only-change-me-in-production-32bytes")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=480)
    jwt_remember_me_expire_minutes: int = Field(default=10080)

    storage_root: Path = Field(default=BASE_DIR / "storage")
    temp_processing_dir: Path = Field(default=BASE_DIR / "storage" / "_tmp")
    max_upload_size_mb: int = Field(default=25)

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    seed_default_data: bool = Field(default=True)
    seed_admin_name: str = Field(default="Schnell Administrator")
    seed_admin_email: str = Field(default="admin@gmail.com")
    seed_admin_username: str = Field(default="admin@gmail.com")
    seed_admin_password: str = Field(default="admin123")

    seed_customer_user_name: str = Field(default="BBMP Viewer")
    seed_customer_user_email: str = Field(default="customer@gmail.com")
    seed_customer_user_username: str = Field(default="customer@gmail.com")
    seed_customer_user_password: str = Field(default="customer123")

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_db_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


def load_settings() -> Settings:
    raw_cors = os.getenv("CORS_ORIGINS", "*")
    cleaned = raw_cors.strip().strip("[]'\"")
    if not cleaned or cleaned == "*":
        cors_list = ["*"]
    else:
        cors_list = [origin.strip().strip("'\"") for origin in cleaned.split(",") if origin.strip().strip("'\"")]
    if "*" not in cors_list:
        # Always ensure localhost and pages.dev wildcard support
        cors_list.extend(["http://localhost:5173", "http://127.0.0.1:5173"])

    storage_env = os.getenv("STORAGE_ROOT")
    storage_root = Path(storage_env) if storage_env else (BASE_DIR / "storage")
    if not storage_root.is_absolute():
        storage_root = (BASE_DIR / storage_root).resolve()

    temp_env = os.getenv("TEMP_PROCESSING_DIR")
    temp_dir = Path(temp_env) if temp_env else (storage_root / "_tmp")
    if not temp_dir.is_absolute():
        temp_dir = (BASE_DIR / temp_dir).resolve()

    app_env = os.getenv("APP_ENV", "development").strip().lower()
    jwt_secret = os.getenv("JWT_SECRET_KEY", "dev-only-change-me-in-production-32bytes")

    if app_env == "production" and (
        not jwt_secret
        or "change-me" in jwt_secret.lower()
        or "replace-with" in jwt_secret.lower()
        or len(jwt_secret) < 32
    ):
        raise RuntimeError(
            "JWT_SECRET_KEY must be set to a secure random string of at least 32 characters in production."
        )

    return Settings(
        app_name=os.getenv("APP_NAME", "Schnell Electrical Asset Report Management"),
        app_env=app_env,
        debug=os.getenv("DEBUG", "false").lower() in {"1", "true", "yes"},
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/schnell_reports",
        ),
        jwt_secret_key=jwt_secret,
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        jwt_access_token_expire_minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "480")),
        jwt_remember_me_expire_minutes=int(os.getenv("JWT_REMEMBER_ME_EXPIRE_MINUTES", "10080")),
        storage_root=storage_root,
        temp_processing_dir=temp_dir,
        max_upload_size_mb=int(os.getenv("MAX_UPLOAD_SIZE_MB", "25")),
        cors_origins=cors_list,
        seed_default_data=os.getenv("SEED_DEFAULT_DATA", "true").lower() in {"1", "true", "yes"},
        seed_admin_name=os.getenv("SEED_ADMIN_NAME", "Schnell Administrator"),
        seed_admin_email=os.getenv("SEED_ADMIN_EMAIL", "admin@gmail.com"),
        seed_admin_username=os.getenv("SEED_ADMIN_USERNAME", "admin@gmail.com"),
        seed_admin_password=os.getenv("SEED_ADMIN_PASSWORD", "admin123"),
        seed_customer_user_name=os.getenv("SEED_CUSTOMER_USER_NAME", "BBMP Viewer"),
        seed_customer_user_email=os.getenv("SEED_CUSTOMER_USER_EMAIL", "customer@gmail.com"),
        seed_customer_user_username=os.getenv("SEED_CUSTOMER_USER_USERNAME", "customer@gmail.com"),
        seed_customer_user_password=os.getenv("SEED_CUSTOMER_USER_PASSWORD", "customer123"),
    )


settings = load_settings()

