from typing import Annotated

from fastapi import APIRouter, Security

from app.deps import SessionDep, get_current_user
from app.models import User
from app.schemas import SettingsRead, SettingsUpdate
from app.services import get_settings_row, settings_read, update_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsRead)
def get_settings(
    session: SessionDep,
    _user: Annotated[User, Security(get_current_user, scopes=["settings:read"])],
) -> SettingsRead:
    return settings_read(get_settings_row(session))


@router.put("", response_model=SettingsRead)
def put_settings(
    data: SettingsUpdate,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user, scopes=["settings:manage"])],
) -> SettingsRead:
    return settings_read(update_settings(session, user, data))
