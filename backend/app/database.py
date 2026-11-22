import os

from sqlalchemy import event
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel, create_engine

from app import models  # noqa: F401  (register tables on metadata)


def _sqlalchemy_url(url: str) -> str:
    """Use the psycopg v3 driver for Neon and other Postgres URLs."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def make_engine(url: str):
    if not url.startswith("sqlite"):
        # Neon's pooler is PgBouncer in transaction mode, which cannot keep
        # prepared statements. Serverless runs must not hold a local pool.
        kwargs: dict = {"pool_pre_ping": True, "connect_args": {"prepare_threshold": None}}
        if os.getenv("VERCEL") == "1" or "-pooler." in url:
            kwargs["poolclass"] = NullPool
        return create_engine(_sqlalchemy_url(url), **kwargs)

    connect_args = {"check_same_thread": False, "timeout": 30}
    engine = create_engine(url, connect_args=connect_args)

    @event.listens_for(engine, "connect")
    def _sqlite_connect(dbapi_connection, _connection_record) -> None:
        # Let SQLAlchemy control transactions, and enforce foreign keys.
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _sqlite_begin(connection) -> None:
        # Reserve the write lock before availability checks so two bookings
        # cannot both pass the overlap test for the same seat.
        connection.exec_driver_sql("BEGIN IMMEDIATE")

    return engine


def create_tables(engine) -> None:
    SQLModel.metadata.create_all(engine)
    # create_all does not add columns to a database that already exists.
    statements = (
        "ALTER TABLE users ADD COLUMN account_role VARCHAR DEFAULT 'user'",
        "ALTER TABLE users ADD COLUMN failed_attempts INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN locked_until TIMESTAMP",
        "ALTER TABLE users ADD COLUMN banned_at TIMESTAMP",
        "ALTER TABLE users ADD COLUMN ban_reason VARCHAR",
        "ALTER TABLE audit_logs ADD COLUMN ip_address VARCHAR",
        "ALTER TABLE audit_logs ADD COLUMN user_agent VARCHAR",
        "ALTER TABLE audit_logs ADD COLUMN detail VARCHAR",
        "ALTER TABLE reservations ADD COLUMN group_id INTEGER",
    )
    with engine.begin() as connection:
        for sql in statements:
            try:
                connection.exec_driver_sql(sql)
            except Exception:
                pass
        try:
            connection.exec_driver_sql(
                "UPDATE users SET account_role = 'admin' "
                "WHERE role = 'manager' AND (account_role IS NULL OR account_role = 'user')"
            )
        except Exception:
            pass
