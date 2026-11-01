from datetime import date, time
from typing import Annotated

from fastapi import APIRouter, Query, Response, Security

from app.deps import SessionDep, get_current_user
from app.models import User
from app.schemas import AvailabilitySeat, SeatCreate, SeatRead, SeatUpdate
from app.services import create_seat, delete_seat, get_seat, list_seats, search_availability, seat_read, update_seat

router = APIRouter(prefix="/seats", tags=["seats"])


@router.get("", response_model=list[SeatRead])
def get_seats(
    session: SessionDep,
    user: Annotated[User, Security(get_current_user, scopes=["seats:read"])],
    include_inactive: bool = False,
) -> list[SeatRead]:
    return list_seats(session, include_inactive, user.role)


@router.get("/availability", response_model=list[AvailabilitySeat])
def availability(
    session: SessionDep,
    user: Annotated[User, Security(get_current_user, scopes=["seats:read"])],
    book_date: Annotated[date, Query(alias="date")],
    start_clock: Annotated[time, Query(alias="start_time")],
    party_size: int = Query(ge=1, le=20),
    exclude_reservation_id: int | None = None,
) -> list[AvailabilitySeat]:
    seats = search_availability(session, book_date, start_clock, party_size, exclude_reservation_id, user)
    return [
        AvailabilitySeat(
            id=seat.id or 0,
            seat_number=seat.seat_number,
            capacity=seat.capacity,
            description=seat.description,
            available=True,
        )
        for seat in seats
    ]


@router.post("", status_code=201, response_model=SeatRead)
def post_seat(
    data: SeatCreate,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user, scopes=["seats:manage"])],
) -> SeatRead:
    return seat_read(create_seat(session, user, data))


@router.get("/{seat_id}", response_model=SeatRead)
def one_seat(
    seat_id: int,
    session: SessionDep,
    _user: Annotated[User, Security(get_current_user, scopes=["seats:read"])],
) -> SeatRead:
    return seat_read(get_seat(session, seat_id))


@router.delete("/{seat_id}", status_code=204)
def remove_seat(
    seat_id: int,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user, scopes=["seats:manage"])],
) -> Response:
    delete_seat(session, user, seat_id)
    return Response(status_code=204)


@router.patch("/{seat_id}", response_model=SeatRead)
def patch_seat(
    seat_id: int,
    data: SeatUpdate,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user, scopes=["seats:manage"])],
) -> SeatRead:
    return seat_read(update_seat(session, user, seat_id, data))
