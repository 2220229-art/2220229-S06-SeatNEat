import hashlib
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Request, Response, Security
from pydantic import BaseModel, Field, field_validator
from sqlmodel import select

from app.access import account_role_of
from app.deps import SessionDep, get_current_user
from app.errors import AppError
from app.models import AccountRole, RefreshSession, Role, User
from app.request_meta import client_agent, client_ip
from app.schemas import LoginRequest, LoginResponse, RegisterRequest, UserPublic
from app.security import create_access_token, hash_password, verify_password
from app.services import audit, user_public
from app.timeutil import to_utc, utc_now

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "sitneat_refresh"
LOCK_AFTER = 5
LOCK_MINUTES = 15


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Name must be at least 2 characters.")
        return cleaned


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_enough(cls, value: str) -> str:
        if not any(character.isalpha() for character in value) or not any(character.isdigit() for character in value):
            raise ValueError("Use at least one letter and one number.")
        return value


class SessionRead(BaseModel):
    id: int
    ip_address: str | None
    user_agent: str | None
    created_at: str
    expires_at: str
    revoked: bool
    current: bool


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _meta(request: Request) -> tuple[str | None, str | None]:
    return client_ip(request), client_agent(request)


def _token_for(user: User, request: Request) -> str:
    settings = request.app.state.settings
    return create_access_token(
        user.id or 0,
        account_role_of(user),
        settings.secret_key,
        settings.access_token_expire_minutes,
    )


def _set_refresh_cookie(response: Response, raw: str, request: Request) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        REFRESH_COOKIE,
        raw,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        path="/api",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/api")


def _new_refresh(session: SessionDep, user: User, request: Request) -> str:
    settings = request.app.state.settings
    raw = secrets.token_urlsafe(32)
    ip_address, user_agent = _meta(request)
    session.add(
        RefreshSession(
            user_id=user.id or 0,
            token_hash=_hash_token(raw),
            expires_at=utc_now() + timedelta(days=settings.refresh_token_days),
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
    return raw


def _login_response(user: User, request: Request, response: Response, session: SessionDep) -> LoginResponse:
    raw = _new_refresh(session, user, request)
    ip_address, user_agent = _meta(request)
    audit(session, user.id, "login", "session", user.id, ip_address, user_agent)
    session.commit()
    _set_refresh_cookie(response, raw, request)
    settings = request.app.state.settings
    minutes = min(max(int(settings.access_token_expire_minutes), 1), 15)
    return LoginResponse(
        access_token=_token_for(user, request),
        expires_in=minutes * 60,
        user=user_public(user),
    )


@router.post("/register", status_code=201, response_model=UserPublic)
def register(data: RegisterRequest, session: SessionDep) -> UserPublic:
    existing = session.exec(select(User).where(User.email == data.email)).first()
    if existing is not None:
        raise AppError(409, "EMAIL_TAKEN", "An account with this email already exists.")
    user = User(
        full_name=data.full_name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=Role.customer.value,
        account_role=AccountRole.user.value,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user_public(user)


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, request: Request, response: Response, session: SessionDep) -> LoginResponse:
    ip_address, user_agent = _meta(request)
    user = session.exec(select(User).where(User.email == data.email)).first()
    if user is not None and user.locked_until is not None and to_utc(user.locked_until) > utc_now():
        audit(session, user.id, "login_failed", "session", user.id, ip_address, user_agent, "locked")
        session.commit()
        raise AppError(429, "LOCKED", "Too many attempts. Try again later.")
    password_ok = user is not None and user.is_active and user.banned_at is None and verify_password(
        data.password, user.password_hash
    )
    if user is None or not password_ok:
        if user is not None:
            user.failed_attempts += 1
            if user.failed_attempts >= LOCK_AFTER:
                user.locked_until = utc_now() + timedelta(minutes=LOCK_MINUTES)
            session.add(user)
            audit(session, user.id, "login_failed", "session", user.id, ip_address, user_agent, "rejected")
        else:
            audit(session, None, "login_failed", "session", None, ip_address, user_agent, data.email)
        session.commit()
        raise AppError(401, "UNAUTHORIZED", "Invalid email or password.")
    user.failed_attempts = 0
    user.locked_until = None
    session.add(user)
    return _login_response(user, request, response, session)


@router.post("/refresh", response_model=LoginResponse)
def refresh(request: Request, response: Response, session: SessionDep) -> LoginResponse:
    raw = request.cookies.get(REFRESH_COOKIE, "")
    if not raw:
        raise AppError(401, "UNAUTHORIZED", "Please log in to continue.")
    row = session.exec(select(RefreshSession).where(RefreshSession.token_hash == _hash_token(raw))).first()
    if row is None or to_utc(row.expires_at) <= utc_now():
        _clear_refresh_cookie(response)
        raise AppError(401, "UNAUTHORIZED", "Please log in to continue.")
    if row.revoked_at is not None:
        _revoke_all(session, row.user_id)
        session.commit()
        _clear_refresh_cookie(response)
        raise AppError(401, "UNAUTHORIZED", "Please log in to continue.")
    user = session.get(User, row.user_id)
    if user is None or not user.is_active or user.banned_at is not None:
        _clear_refresh_cookie(response)
        raise AppError(401, "UNAUTHORIZED", "Please log in to continue.")
    replacement = _new_refresh(session, user, request)
    session.commit()
    session.refresh(user)
    stored = session.exec(select(RefreshSession).where(RefreshSession.token_hash == _hash_token(replacement))).first()
    row.revoked_at = utc_now()
    row.replaced_by_id = stored.id if stored else None
    session.add(row)
    session.commit()
    _set_refresh_cookie(response, replacement, request)
    settings = request.app.state.settings
    minutes = min(max(int(settings.access_token_expire_minutes), 1), 15)
    return LoginResponse(
        access_token=_token_for(user, request),
        expires_in=minutes * 60,
        user=user_public(user),
    )


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user)],
) -> Response:
    raw = request.cookies.get(REFRESH_COOKIE, "")
    if raw:
        row = session.exec(select(RefreshSession).where(RefreshSession.token_hash == _hash_token(raw))).first()
        if row is not None and row.revoked_at is None:
            row.revoked_at = utc_now()
            session.add(row)
    ip_address, user_agent = _meta(request)
    audit(session, user.id, "logout", "session", user.id, ip_address, user_agent)
    session.commit()
    _clear_refresh_cookie(response)
    return Response(status_code=204)


@router.get("/me", response_model=UserPublic)
def me(user: Annotated[User, Security(get_current_user)]) -> UserPublic:
    return user_public(user)


@router.patch("/profile", response_model=UserPublic)
def update_profile(
    data: ProfileUpdate,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user)],
) -> UserPublic:
    user.full_name = data.full_name
    user.updated_at = utc_now()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user_public(user)


@router.post("/password", status_code=204)
def change_password(
    data: PasswordChange,
    request: Request,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user)],
) -> Response:
    if not verify_password(data.current_password, user.password_hash):
        raise AppError(401, "UNAUTHORIZED", "Current password is not correct.")
    if data.current_password == data.new_password:
        raise AppError(422, "VALIDATION_ERROR", "Choose a different password.")
    user.password_hash = hash_password(data.new_password)
    user.updated_at = utc_now()
    ip_address, user_agent = _meta(request)
    audit(session, user.id, "password_change", "user", user.id, ip_address, user_agent)
    session.add(user)
    session.commit()
    return Response(status_code=204)


@router.get("/sessions", response_model=list[SessionRead])
def list_sessions(
    request: Request,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user)],
) -> list[SessionRead]:
    current_hash = _hash_token(request.cookies.get(REFRESH_COOKIE, ""))
    rows = session.exec(
        select(RefreshSession).where(RefreshSession.user_id == user.id).order_by(RefreshSession.id.desc())
    ).all()
    return [
        SessionRead(
            id=row.id or 0,
            ip_address=row.ip_address,
            user_agent=row.user_agent,
            created_at=to_utc(row.created_at).isoformat(),
            expires_at=to_utc(row.expires_at).isoformat(),
            revoked=row.revoked_at is not None,
            current=row.token_hash == current_hash,
        )
        for row in rows
    ]


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(
    session_id: int,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user)],
) -> Response:
    row = session.get(RefreshSession, session_id)
    if row is None or row.user_id != user.id:
        raise AppError(404, "NOT_FOUND", "That session was not found.")
    if row.revoked_at is None:
        row.revoked_at = utc_now()
        session.add(row)
        session.commit()
    return Response(status_code=204)


def _revoke_all(session: SessionDep, user_id: int) -> None:
    rows = session.exec(select(RefreshSession).where(RefreshSession.user_id == user_id)).all()
    now = utc_now()
    for row in rows:
        if row.revoked_at is None:
            row.revoked_at = now
            session.add(row)
