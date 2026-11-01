from typing import Annotated

from fastapi import APIRouter, Request, Security

from app.deps import SessionDep, get_current_user
from app.errors import AppError
from app.models import Role, User
from app.schemas import LoginRequest, LoginResponse, RegisterRequest, UserPublic
from app.security import create_access_token, hash_password, verify_password
from app.services import user_public
from sqlmodel import select

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=UserPublic)
def register(data: RegisterRequest, session: SessionDep) -> UserPublic:
    # A submitted role is ignored. Public signup always creates a customer.
    existing = session.exec(select(User).where(User.email == data.email)).first()
    if existing is not None:
        raise AppError(409, "EMAIL_TAKEN", "An account with this email already exists.")
    user = User(
        full_name=data.full_name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=Role.customer.value,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user_public(user)


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, request: Request, session: SessionDep) -> LoginResponse:
    user = session.exec(select(User).where(User.email == data.email)).first()
    if user is None or not user.is_active or not verify_password(data.password, user.password_hash):
        raise AppError(401, "UNAUTHORIZED", "Invalid email or password.")
    settings = request.app.state.settings
    token = create_access_token(user.id or 0, settings.secret_key, settings.access_token_expire_minutes)
    return LoginResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=user_public(user),
    )


@router.get("/me", response_model=UserPublic)
def me(user: Annotated[User, Security(get_current_user)]) -> UserPublic:
    return user_public(user)
