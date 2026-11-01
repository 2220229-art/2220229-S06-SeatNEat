from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, SecurityScopes
from sqlmodel import Session

from app.config import Settings
from app.errors import AppError
from app.models import User
from app.security import SCOPES, decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_session(request: Request):
    with Session(request.app.state.engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_current_user(
    security_scopes: SecurityScopes,
    request: Request,
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None or not credentials.credentials:
        raise AppError(401, "UNAUTHORIZED", "Please log in to continue.")
    settings = request.app.state.settings
    try:
        payload = decode_access_token(credentials.credentials, settings.secret_key)
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise AppError(401, "UNAUTHORIZED", "Your session has expired. Please log in again.")
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise AppError(401, "UNAUTHORIZED", "Please log in to continue.")
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise AppError(401, "UNAUTHORIZED", "Please log in to continue.")
    allowed = SCOPES.get(user.role, set())
    if any(scope not in allowed for scope in security_scopes.scopes):
        raise AppError(403, "FORBIDDEN", "You do not have permission for this action.")
    return user


def require_any(*scopes: str):
    def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        allowed = SCOPES.get(user.role, set())
        if not any(scope in allowed for scope in scopes):
            raise AppError(403, "FORBIDDEN", "You do not have permission for this action.")
        return user

    return checker
