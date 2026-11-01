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
