import logging
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import DEV_SECRET, Settings, allowed_origins, load_settings
from app.database import create_tables, make_engine
from app.errors import AppError
from app.routers import auth, reports, reservations, seats, staff
from app.routers import settings as settings_router
from app.seed import seed_database

logger = logging.getLogger("sitneat")


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode() or str(uuid.uuid4())
        state = scope.setdefault("state", {})
        state["request_id"] = request_id

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_id)


def _field_name(location: tuple) -> str:
    parts = [str(part) for part in location if part not in {"body", "query", "path"}]
    return ".".join(parts) or "request"


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = load_settings()
    if settings.app_env == "production" and settings.secret_key in {"", DEV_SECRET}:
        raise RuntimeError("Set SECRET_KEY in the environment before running in production.")

    logging.basicConfig(level=logging.INFO)
    engine = make_engine(settings.database_url)
    create_tables(engine)
    seed_database(engine, settings)

    app = FastAPI(
        title="SitNeat",
        version="1.0.0",
        summary="Restaurant seat reservation and management",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.state.engine = engine
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(settings.frontend_origin),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(RequestIdMiddleware)

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError):
        body: dict = {"code": exc.code, "message": exc.message}
        if exc.details:
            body["details"] = exc.details
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError):
        details = []
        for error in exc.errors():
            message = str(error.get("msg", "Invalid value"))
            prefix = "Value error, "
            if message.startswith(prefix):
                message = message[len(prefix) :]
            details.append({"field": _field_name(tuple(error.get("loc", ()))), "message": message})
        return JSONResponse(
            status_code=422,
            content={
                "code": "VALIDATION_ERROR",
                "message": "Please check the form and try again.",
                "details": details,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, _exc: Exception):
        logger.exception(
            "unhandled error request_id=%s path=%s",
            getattr(request.state, "request_id", "-"),
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={"code": "SERVER_ERROR", "message": "Something went wrong. Please try again."},
        )

    @app.get("/api/health", tags=["health"])
    @app.get("/api/v1/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(seats.router, prefix="/api/v1")
    app.include_router(reservations.router, prefix="/api/v1")
    app.include_router(staff.router, prefix="/api/v1")
    app.include_router(settings_router.router, prefix="/api/v1")
    app.include_router(reports.router, prefix="/api/v1")

    # On Vercel the React app is its own service. Mounting dist here would only
    # apply when this process is also serving the built frontend locally.
    if os.getenv("VERCEL") != "1":
        frontend_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"
        mount_frontend = getattr(app, "frontend", None)
        if frontend_dir.is_dir() and callable(mount_frontend):
            mount_frontend("/", directory=frontend_dir)

    return app


app = create_app()
