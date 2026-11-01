import pytest

from app.config import (
    LOCAL_DATABASE_URL,
    VERCEL_DATABASE_URL,
    Settings,
    allowed_origins,
    resolve_app_env,
    resolve_database_url,
)
from main import create_app


def test_postgres_urls_use_the_psycopg_driver():
    from app.database import _sqlalchemy_url

    assert _sqlalchemy_url("postgresql://db.example/sitneat") == "postgresql+psycopg://db.example/sitneat"
    assert _sqlalchemy_url("postgres://db.example/sitneat") == "postgresql+psycopg://db.example/sitneat"
    assert _sqlalchemy_url("sqlite:///./sitneat.db") == "sqlite:///./sitneat.db"


def test_local_database_url_stays_in_the_backend_folder(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    assert resolve_database_url(None) == LOCAL_DATABASE_URL
    assert resolve_database_url("sqlite:///./custom.db") == "sqlite:///./custom.db"


def test_hosted_vercel_uses_a_writable_sqlite_file(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_ENV", "production")
    assert resolve_database_url(None) == VERCEL_DATABASE_URL
    assert resolve_database_url("sqlite:///./sitneat.db") == VERCEL_DATABASE_URL
    assert resolve_database_url("sqlite:////tmp/sitneat.db") == "sqlite:////tmp/sitneat.db"
    assert resolve_database_url("sqlite:///:memory:") == "sqlite:///:memory:"
    assert resolve_database_url("postgresql://db.example/sitneat") == "postgresql://db.example/sitneat"


def test_vercel_dev_keeps_the_local_database(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_ENV", "development")
    assert resolve_database_url("sqlite:///./sitneat.db") == "sqlite:///./sitneat.db"
    assert resolve_app_env(None) == "development"


def test_hosted_vercel_defaults_to_production(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_ENV", "preview")
    assert resolve_app_env(None) == "production"
    assert resolve_app_env("development") == "development"


def test_allowed_origins_include_the_deployed_host(monkeypatch):
    monkeypatch.delenv("VERCEL_BRANCH_URL", raising=False)
    monkeypatch.setenv("VERCEL_URL", "sitneat-abc.vercel.app")
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "https://sitneat.vercel.app")
    assert allowed_origins("http://localhost:5173") == [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "https://sitneat-abc.vercel.app",
        "https://sitneat.vercel.app",
    ]


def test_production_rejects_the_example_secret():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(
            Settings(
                app_env="production",
                secret_key="dev-only-sitneat-change-this-secret",
                database_url="sqlite:///:memory:",
            )
        )
