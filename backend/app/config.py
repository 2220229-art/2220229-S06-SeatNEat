import os
from dataclasses import dataclass
from pathlib import Path


DEV_SECRET = "dev-only-sitneat-change-this-secret"
LOCAL_DATABASE_URL = "sqlite:///./sitneat.db"
VERCEL_DATABASE_URL = "sqlite:////tmp/sitneat.db"


@dataclass
class Settings:
    app_env: str = "development"
    secret_key: str = DEV_SECRET
    database_url: str = LOCAL_DATABASE_URL
    access_token_expire_minutes: int = 120
    frontend_origin: str = "http://localhost:5173"
    seed_demo: bool = True


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_env_file() -> None:
    """Load a local .env without overriding variables already set in the shell."""
    backend_dir = Path(__file__).resolve().parents[1]
    candidates = (
        Path.cwd() / ".env",
        backend_dir / ".env",
        backend_dir.parent / ".env",
    )
    for candidate in candidates:
        if not candidate.is_file():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        return


def hosted_on_vercel() -> bool:
    """True for a Vercel preview or production deployment.

    `vercel dev` sets VERCEL=1 with VERCEL_ENV=development, and that process can
    still write the local SQLite file. A missing VERCEL_ENV on the platform is
    treated as hosted so the API does not try to write a read-only directory.
    """
    if os.getenv("VERCEL") != "1":
        return False
    return os.getenv("VERCEL_ENV", "") != "development"


def resolve_app_env(configured: str | None) -> str:
    value = (configured or "").strip()
    if value:
        return value
    return "production" if hosted_on_vercel() else "development"


def resolve_database_url(configured: str | None) -> str:
    value = (configured or "").strip()
    if hosted_on_vercel() and _sqlite_needs_writable_path(value):
        return VERCEL_DATABASE_URL
    return value or LOCAL_DATABASE_URL


def _sqlite_needs_writable_path(url: str) -> bool:
    if not url:
        return True
    if not url.startswith("sqlite:"):
        return False
    if ":memory:" in url:
        return False
    return not url.startswith("sqlite:////")


def allowed_origins(frontend_origin: str) -> list[str]:
    origins = {frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"}
    for key in ("VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_URL", "VERCEL_BRANCH_URL"):
        host = os.getenv(key, "").strip().removeprefix("https://").removeprefix("http://").strip("/")
        if host:
            origins.add(f"https://{host}")
    return sorted(origin for origin in origins if origin)


def load_settings() -> Settings:
    load_env_file()
    return Settings(
        app_env=resolve_app_env(os.getenv("APP_ENV")),
        secret_key=os.getenv("SECRET_KEY", DEV_SECRET),
        database_url=resolve_database_url(os.getenv("DATABASE_URL")),
        access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120")),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"),
        seed_demo=_as_bool(os.getenv("SEED_DEMO"), True),
    )
