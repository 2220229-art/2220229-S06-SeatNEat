from typing import Annotated

from fastapi import APIRouter, Response, Security
from pydantic import BaseModel, Field
from sqlmodel import select

from app.access import membership, require_group_permission, require_owner
from app.deps import SessionDep, get_current_user
from app.errors import AppError
from app.models import DiningGroup, GroupMember, Reservation, Seat, User
from app.schemas import ReservationBody, ReservationRead
from app.services import create_reservation, reservation_read
from app.timeutil import utc_now

router = APIRouter(prefix="/groups", tags=["groups"])


class GroupCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class GroupRename(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class MemberWrite(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    can_create: bool = False
    can_update: bool = False
    can_assign: bool = False


class MemberPatch(BaseModel):
    can_create: bool | None = None
    can_update: bool | None = None
    can_assign: bool | None = None


class MemberRead(BaseModel):
    user_id: int
    full_name: str
    email: str
    can_create: bool
    can_update: bool
    can_assign: bool


class GroupRead(BaseModel):
    id: int
    name: str
    owner_id: int
    owner_name: str
    is_owner: bool
    members: list[MemberRead]


def _clean_email(value: str) -> str:
    return value.strip().lower()


def _read_group(session: SessionDep, group: DiningGroup, viewer: User) -> GroupRead:
    owner = session.get(User, group.owner_id)
    rows = session.exec(select(GroupMember).where(GroupMember.group_id == group.id)).all()
    members: list[MemberRead] = []
    for row in rows:
        person = session.get(User, row.user_id)
        if person is None:
            continue
        members.append(
            MemberRead(
                user_id=person.id or 0,
                full_name=person.full_name,
                email=person.email,
                can_create=row.can_create,
                can_update=row.can_update,
                can_assign=row.can_assign,
            )
        )
    return GroupRead(
        id=group.id or 0,
        name=group.name,
        owner_id=group.owner_id,
        owner_name=owner.full_name if owner else "Unknown",
        is_owner=group.owner_id == viewer.id,
        members=members,
    )


def _visible_group(session: SessionDep, user: User, group_id: int) -> DiningGroup:
    group = session.get(DiningGroup, group_id)
    if group is None:
        raise AppError(404, "NOT_FOUND", "That group was not found.")
    if group.owner_id == user.id or membership(session, group_id, user.id or 0) is not None:
        return group
    raise AppError(404, "NOT_FOUND", "That group was not found.")


@router.get("", response_model=list[GroupRead])
def list_groups(
    session: SessionDep,
    user: Annotated[User, Security(get_current_user)],
) -> list[GroupRead]:
    owned = session.exec(select(DiningGroup).where(DiningGroup.owner_id == user.id)).all()
    joined = session.exec(select(GroupMember).where(GroupMember.user_id == user.id)).all()
    groups = {row.id: row for row in owned}
    for row in joined:
        group = session.get(DiningGroup, row.group_id)
        if group is not None:
            groups[group.id] = group
    return [_read_group(session, group, user) for group in groups.values()]


@router.post("", status_code=201, response_model=GroupRead)
def create_group(
    data: GroupCreate,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user)],
) -> GroupRead:
    group = DiningGroup(name=" ".join(data.name.split()), owner_id=user.id or 0)
    session.add(group)
    session.commit()
    session.refresh(group)
    return _read_group(session, group, user)


@router.get("/{group_id}", response_model=GroupRead)
def get_group(
    group_id: int,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user)],
) -> GroupRead:
    return _read_group(session, _visible_group(session, user, group_id), user)


@router.patch("/{group_id}", response_model=GroupRead)
def rename_group(
    group_id: int,
    data: GroupRename,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user)],
) -> GroupRead:
    group = require_owner(session, user, group_id)
    group.name = " ".join(data.name.split())
    session.add(group)
    session.commit()
    session.refresh(group)
    return _read_group(session, group, user)


@router.delete("/{group_id}", status_code=204)
def delete_group(
    group_id: int,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user)],
) -> Response:
    group = require_owner(session, user, group_id)
    for row in session.exec(select(GroupMember).where(GroupMember.group_id == group.id)).all():
        session.delete(row)
    for reservation in session.exec(select(Reservation).where(Reservation.group_id == group.id)).all():
        reservation.group_id = None
        session.add(reservation)
    session.delete(group)
    session.commit()
    return Response(status_code=204)


@router.post("/{group_id}/members", response_model=GroupRead)
def add_member(
    group_id: int,
    data: MemberWrite,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user)],
) -> GroupRead:
    group = require_owner(session, user, group_id)
    email = _clean_email(data.email)
    person = session.exec(select(User).where(User.email == email)).first()
    if person is None:
        raise AppError(404, "NOT_FOUND", "No account uses that email.")
    if person.id == group.owner_id:
        raise AppError(409, "CONFLICT", "The owner is already on this group.")
    if membership(session, group.id or 0, person.id or 0) is not None:
        raise AppError(409, "CONFLICT", "That person is already a member.")
    session.add(
        GroupMember(
            group_id=group.id or 0,
            user_id=person.id or 0,
            can_create=data.can_create,
            can_update=data.can_update,
            can_assign=data.can_assign,
        )
    )
    session.commit()
    return _read_group(session, group, user)


@router.patch("/{group_id}/members/{member_id}", response_model=GroupRead)
def update_member(
    group_id: int,
    member_id: int,
    data: MemberPatch,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user)],
) -> GroupRead:
    group = require_owner(session, user, group_id)
    row = membership(session, group.id or 0, member_id)
    if row is None:
        raise AppError(404, "NOT_FOUND", "That member was not found.")
    if data.can_create is not None:
        row.can_create = data.can_create
    if data.can_update is not None:
        row.can_update = data.can_update
    if data.can_assign is not None:
        row.can_assign = data.can_assign
    session.add(row)
    session.commit()
    return _read_group(session, group, user)


@router.delete("/{group_id}/members/{member_id}", status_code=204)
def remove_member(
    group_id: int,
    member_id: int,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user)],
) -> Response:
    group = require_owner(session, user, group_id)
    row = membership(session, group.id or 0, member_id)
    if row is None:
        raise AppError(404, "NOT_FOUND", "That member was not found.")
    session.delete(row)
    session.commit()
    return Response(status_code=204)


@router.post("/{group_id}/reservations", status_code=201, response_model=ReservationRead)
def book_for_group(
    group_id: int,
    data: ReservationBody,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user)],
) -> ReservationRead:
    require_group_permission(session, user, group_id, "create")
    data.group_id = group_id
    return reservation_read(session, create_reservation(session, user, data))


class SeatAssign(BaseModel):
    seat_id: int = Field(ge=1)


class GroupReservationPatch(BaseModel):
    party_size: int = Field(ge=1, le=20)


@router.patch("/{group_id}/reservations/{reservation_id}", response_model=ReservationRead)
def update_group_reservation(
    group_id: int,
    reservation_id: int,
    data: GroupReservationPatch,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user)],
) -> ReservationRead:
    require_group_permission(session, user, group_id, "update")
    reservation = session.get(Reservation, reservation_id)
    if reservation is None or reservation.group_id != group_id:
        raise AppError(404, "NOT_FOUND", "That reservation was not found.")
    reservation.party_size = data.party_size
    reservation.updated_at = utc_now()
    session.add(reservation)
    session.commit()
    session.refresh(reservation)
    return reservation_read(session, reservation)


@router.patch("/{group_id}/reservations/{reservation_id}/seat", response_model=ReservationRead)
def assign_seat(
    group_id: int,
    reservation_id: int,
    data: SeatAssign,
    session: SessionDep,
    user: Annotated[User, Security(get_current_user)],
) -> ReservationRead:
    require_group_permission(session, user, group_id, "assign")
    reservation = session.get(Reservation, reservation_id)
    if reservation is None or reservation.group_id != group_id:
        raise AppError(404, "NOT_FOUND", "That reservation was not found.")
    seat = session.get(Seat, data.seat_id)
    if seat is None or not seat.is_active:
        raise AppError(404, "NOT_FOUND", "That seat was not found.")
    reservation.seat_id = data.seat_id
    reservation.updated_at = utc_now()
    session.add(reservation)
    session.commit()
    session.refresh(reservation)
    return reservation_read(session, reservation)
