from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Response, Security

from app.deps import SessionDep, get_current_user, require_any
from app.models import ReservationStatus, User
from app.schemas import ReservationBody, ReservationRead, StatusUpdate
from app.services import (
    cancel_reservation,
    create_reservation,
    delete_reservation,
    get_visible_reservation,
    list_all,
    list_own,
    list_today,
    reservation_read,
    update_own_reservation,
    update_status,
)

router = APIRouter(prefix="/reservations", tags=["reservations"])


@router.post("", status_code=201, response_model=ReservationRead)
def post_reservation(
    data: ReservationBody,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user, scopes=["reservations:create:own"])],
) -> ReservationRead:
    return reservation_read(session, create_reservation(session, user, data))


@router.get("/mine", response_model=list[ReservationRead])
def mine(
    session: SessionDep,
    user: Annotated[User, Security(get_current_user, scopes=["reservations:read:own"])],
) -> list[ReservationRead]:
    return list_own(session, user)


@router.get("/today", response_model=list[ReservationRead])
def today(
    session: SessionDep,
    _user: Annotated[User, Security(get_current_user, scopes=["reservations:read:operational"])],
) -> list[ReservationRead]:
    return list_today(session)


@router.get("", response_model=list[ReservationRead])
def all_reservations(
    session: SessionDep,
    _user: Annotated[User, Security(get_current_user, scopes=["reservations:read:all"])],
    date_from: date | None = None,
    date_to: date | None = None,
    status: ReservationStatus | None = None,
) -> list[ReservationRead]:
    return list_all(session, date_from, date_to, status.value if status else None)


@router.get("/{reservation_id}", response_model=ReservationRead)
def one_reservation(
    reservation_id: int,
    session: SessionDep,
    user: Annotated[User, Depends(require_any("reservations:read:own", "reservations:read:operational", "reservations:read:all"))],
) -> ReservationRead:
    return reservation_read(session, get_visible_reservation(session, user, reservation_id))


@router.patch("/{reservation_id}", response_model=ReservationRead)
def edit_reservation(
    reservation_id: int,
    data: ReservationBody,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user, scopes=["reservations:update:own"])],
) -> ReservationRead:
    return reservation_read(session, update_own_reservation(session, user, reservation_id, data))


@router.delete("/{reservation_id}", status_code=204)
def remove_reservation(
    reservation_id: int,
    session: SessionDep,
    user: Annotated[User, Depends(require_any("reservations:delete:own", "reservations:delete:all"))],
) -> Response:
    delete_reservation(session, user, reservation_id)
    return Response(status_code=204)


@router.post("/{reservation_id}/cancel", response_model=ReservationRead)
def cancel(
    reservation_id: int,
    session: SessionDep,
    user: Annotated[User, Depends(require_any("reservations:cancel:own", "reservations:cancel:operational"))],
) -> ReservationRead:
    return reservation_read(session, cancel_reservation(session, user, reservation_id))


@router.patch("/{reservation_id}/status", response_model=ReservationRead)
def status(
    reservation_id: int,
    data: StatusUpdate,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user, scopes=["reservations:update:operational"])],
) -> ReservationRead:
    return reservation_read(session, update_status(session, user, reservation_id, data.status))
