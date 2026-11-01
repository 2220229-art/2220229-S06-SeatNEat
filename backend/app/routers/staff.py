from typing import Annotated

from fastapi import APIRouter, Response, Security

from app.deps import SessionDep, get_current_user
from app.models import User
from app.schemas import StaffCreate, StaffUpdate, UserPublic
from app.services import create_staff, delete_staff, get_staff_account, list_staff, update_staff, user_public

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("", response_model=list[UserPublic])
def get_staff(
    session: SessionDep,
    _user: Annotated[User, Security(get_current_user, scopes=["staff:manage"])],
) -> list[UserPublic]:
    return list_staff(session)


@router.post("", status_code=201, response_model=UserPublic)
def post_staff(
    data: StaffCreate,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user, scopes=["staff:manage"])],
) -> UserPublic:
    return user_public(create_staff(session, user, data))


@router.get("/{staff_id}", response_model=UserPublic)
def one_staff(
    staff_id: int,
    session: SessionDep,
    _user: Annotated[User, Security(get_current_user, scopes=["staff:manage"])],
) -> UserPublic:
    return user_public(get_staff_account(session, staff_id))


@router.delete("/{staff_id}", status_code=204)
def remove_staff(
    staff_id: int,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user, scopes=["staff:manage"])],
) -> Response:
    delete_staff(session, user, staff_id)
    return Response(status_code=204)


@router.patch("/{staff_id}", response_model=UserPublic)
def patch_staff(
    staff_id: int,
    data: StaffUpdate,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user, scopes=["staff:manage"])],
) -> UserPublic:
    return user_public(update_staff(session, user, staff_id, data))
