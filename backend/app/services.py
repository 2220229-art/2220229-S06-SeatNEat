from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.errors import AppError
from app.models import (
    AllergyDeclaration,
    AuditLog,
    Reservation,
    ReservationStatus,
    RestaurantSettings,
    Role,
    Seat,
    User,
)
from app.schemas import (
    ReservationBody,
    ReservationRead,
    SeatCreate,
    SeatRead,
    SeatUpdate,
    SettingsRead,
    SettingsUpdate,
    StaffCreate,
    StaffUpdate,
    SummaryRead,
    UserPublic,
)
from app.security import hash_password
from app.timeutil import day_bounds_utc, local_datetime, to_utc, utc_now

BLOCKING = (ReservationStatus.confirmed.value, ReservationStatus.seated.value)
STATUS_FLOW = {
    ReservationStatus.confirmed.value: {ReservationStatus.seated.value},
    ReservationStatus.seated.value: {ReservationStatus.completed.value},
}


def user_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id or 0,
        full_name=user.full_name,
        email=user.email,
        role=Role(user.role),
        is_active=user.is_active,
    )


def seat_read(seat: Seat) -> SeatRead:
    return SeatRead(
        id=seat.id or 0,
        seat_number=seat.seat_number,
        capacity=seat.capacity,
        description=seat.description,
        is_active=seat.is_active,
    )


def settings_read(row: RestaurantSettings) -> SettingsRead:
    return SettingsRead(
        open_time=row.open_time,
        close_time=row.close_time,
        duration_minutes=row.duration_minutes,
        slot_interval_minutes=row.slot_interval_minutes,
        min_lead_minutes=row.min_lead_minutes,
        advance_days=row.advance_days,
        change_cutoff_minutes=row.change_cutoff_minutes,
        timezone=row.timezone,
    )


def reservation_read(session: Session, reservation: Reservation) -> ReservationRead:
    customer = session.get(User, reservation.customer_id)
    seat = session.get(Seat, reservation.seat_id)
    return ReservationRead(
        id=reservation.id or 0,
        customer_id=reservation.customer_id,
        customer_name=customer.full_name if customer else "Guest",
        seat_id=reservation.seat_id,
        seat_number=seat.seat_number if seat else "Unknown",
        start_at=to_utc(reservation.start_at),
        end_at=to_utc(reservation.end_at),
        party_size=reservation.party_size,
        food_preference=reservation.food_preference,
        allergy_declaration=reservation.allergy_declaration,
        allergy_details=reservation.allergy_details,
        status=ReservationStatus(reservation.status),
    )


def get_settings_row(session: Session) -> RestaurantSettings:
    row = session.get(RestaurantSettings, 1)
    if row is None:
        row = session.exec(select(RestaurantSettings)).first()
    if row is None:
        raise AppError(500, "SERVER_ERROR", "Restaurant settings are not configured.")
    return row


def audit(session: Session, actor_id: int, action: str, target_type: str, target_id: int | None) -> None:
    session.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
        )
    )


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise AppError(409, "CONFLICT", "Could not save because of a conflicting record.")


def _clock(value: time) -> str:
    return f"{value.hour:02d}:{value.minute:02d}"


def validate_slot(settings: RestaurantSettings, day: date, start_clock: time) -> tuple[datetime, datetime]:
    tz = ZoneInfo(settings.timezone)
    now_local = datetime.now(tz)
    open_h, open_m = (int(part) for part in settings.open_time.split(":"))
    close_h, close_m = (int(part) for part in settings.close_time.split(":"))
    open_minutes = open_h * 60 + open_m
    close_minutes = close_h * 60 + close_m
    start_minutes = start_clock.hour * 60 + start_clock.minute
    if start_clock.second or start_clock.microsecond:
        raise AppError(400, "INVALID_SLOT", "Choose a start time from the available slots.")
    if (start_minutes - open_minutes) % settings.slot_interval_minutes != 0:
        raise AppError(400, "INVALID_SLOT", "Choose a start time from the available slots.")
    if start_minutes < open_minutes or start_minutes + settings.duration_minutes > close_minutes:
        raise AppError(
            400,
            "OUTSIDE_HOURS",
            f"The restaurant is open {settings.open_time}–{settings.close_time}. A booking must finish before closing.",
        )
    local_start = local_datetime(day, time(start_clock.hour, start_clock.minute), settings.timezone)
    if local_start < now_local + timedelta(minutes=settings.min_lead_minutes):
        raise AppError(
            400,
            "LEAD_TIME",
            f"Bookings must be made at least {settings.min_lead_minutes} minutes in advance.",
        )
    last_day = now_local.date() + timedelta(days=settings.advance_days)
    if day > last_day:
        raise AppError(400, "TOO_FAR_AHEAD", f"You can book up to {settings.advance_days} days ahead.")
    local_end = local_start + timedelta(minutes=settings.duration_minutes)
    return to_utc(local_start), to_utc(local_end)


def _seat_or_404(session: Session, seat_id: int) -> Seat:
    seat = session.get(Seat, seat_id)
    if seat is None:
        raise AppError(404, "NOT_FOUND", "Seat not found.")
    return seat


def _require_bookable(seat: Seat, party_size: int) -> None:
    if not seat.is_active:
        raise AppError(400, "SEAT_INACTIVE", "That seat is not available for booking.")
    if party_size > seat.capacity:
        raise AppError(400, "PARTY_TOO_LARGE", f"This seat holds up to {seat.capacity} guests.")


def _overlap_query(session: Session, seat_id: int, start_at: datetime, end_at: datetime, exclude_id: int | None):
    query = select(Reservation).where(
        Reservation.seat_id == seat_id,
        col(Reservation.status).in_(BLOCKING),
        Reservation.start_at < end_at,
        Reservation.end_at > start_at,
    )
    if exclude_id is not None:
        query = query.where(Reservation.id != exclude_id)
    return session.exec(query).first()


def ensure_free(session: Session, seat_id: int, start_at: datetime, end_at: datetime, exclude_id: int | None) -> None:
    if _overlap_query(session, seat_id, start_at, end_at, exclude_id) is not None:
        raise AppError(409, "SEAT_UNAVAILABLE", "That seat is already booked for this time.")


def list_seats(session: Session, include_inactive: bool, role: str) -> list[SeatRead]:
    query = select(Seat).order_by(Seat.seat_number)
    if not (include_inactive and role == Role.manager.value):
        query = query.where(Seat.is_active == True)  # noqa: E712
    return [seat_read(seat) for seat in session.exec(query).all()]


def search_availability(
    session: Session,
    day: date,
    start_clock: time,
    party_size: int,
    exclude_reservation_id: int | None,
    user: User,
) -> list[Seat]:
    settings = get_settings_row(session)
    start_at, end_at = validate_slot(settings, day, start_clock)
    exclude_id = None
    if exclude_reservation_id is not None:
        existing = session.get(Reservation, exclude_reservation_id)
        if existing is not None and existing.customer_id == user.id:
            exclude_id = existing.id
    seats = session.exec(
        select(Seat)
        .where(Seat.is_active == True)  # noqa: E712
        .where(Seat.capacity >= party_size)
        .order_by(Seat.seat_number)
    ).all()
    return [seat for seat in seats if _overlap_query(session, seat.id or 0, start_at, end_at, exclude_id) is None]


def create_seat(session: Session, actor: User, data: SeatCreate) -> Seat:
    if session.exec(select(Seat).where(Seat.seat_number == data.seat_number)).first():
        raise AppError(409, "SEAT_NUMBER_TAKEN", "That seat number is already used.")
    seat = Seat(
        seat_number=data.seat_number,
        capacity=data.capacity,
        description=data.description,
        is_active=data.is_active,
    )
    session.add(seat)
    session.flush()
    audit(session, actor.id or 0, "seat.create", "seat", seat.id)
    _commit(session)
    session.refresh(seat)
    return seat


def get_seat(session: Session, seat_id: int) -> Seat:
    return _seat_or_404(session, seat_id)


def delete_seat(session: Session, actor: User, seat_id: int) -> None:
    seat = _seat_or_404(session, seat_id)
    in_use = session.exec(select(Reservation).where(Reservation.seat_id == seat_id)).first()
    if in_use is not None:
        raise AppError(
            409,
            "SEAT_IN_USE",
            "This seat has reservations. Deactivate it instead of deleting it.",
        )
    session.delete(seat)
    audit(session, actor.id or 0, "seat.delete", "seat", seat_id)
    _commit(session)


def update_seat(session: Session, actor: User, seat_id: int, data: SeatUpdate) -> Seat:
    seat = _seat_or_404(session, seat_id)
    if data.seat_number is not None and data.seat_number != seat.seat_number:
        taken = session.exec(select(Seat).where(Seat.seat_number == data.seat_number)).first()
        if taken is not None:
            raise AppError(409, "SEAT_NUMBER_TAKEN", "That seat number is already used.")
        seat.seat_number = data.seat_number
    if data.capacity is not None:
        seat.capacity = data.capacity
    if "description" in data.model_fields_set:
        seat.description = data.description
    if data.is_active is not None:
        seat.is_active = data.is_active
    seat.updated_at = utc_now()
    audit(session, actor.id or 0, "seat.update", "seat", seat.id)
    _commit(session)
    session.refresh(seat)
    return seat


def create_reservation(session: Session, user: User, data: ReservationBody) -> Reservation:
    settings = get_settings_row(session)
    start_at, end_at = validate_slot(settings, data.date, data.start_time)
    seat = _seat_or_404(session, data.seat_id)
    _require_bookable(seat, data.party_size)
    ensure_free(session, seat.id or 0, start_at, end_at, None)
    reservation = Reservation(
        customer_id=user.id or 0,
        seat_id=seat.id or 0,
        start_at=start_at,
        end_at=end_at,
        party_size=data.party_size,
        food_preference=data.food_preference.value,
        allergy_declaration=data.allergy_declaration.value,
        allergy_details=data.allergy_details,
        status=ReservationStatus.confirmed.value,
    )
    session.add(reservation)
    _commit(session)
    session.refresh(reservation)
    return reservation


def list_own(session: Session, user: User) -> list[ReservationRead]:
    rows = session.exec(
        select(Reservation)
        .where(Reservation.customer_id == user.id)
        .order_by(col(Reservation.start_at).desc())
    ).all()
    return [reservation_read(session, row) for row in rows]


def get_visible_reservation(session: Session, user: User, reservation_id: int) -> Reservation:
    reservation = session.get(Reservation, reservation_id)
    if reservation is None:
        raise AppError(404, "NOT_FOUND", "Reservation not found.")
    if user.role == Role.customer.value and reservation.customer_id != user.id:
        raise AppError(404, "NOT_FOUND", "Reservation not found.")
    if user.role not in {Role.customer.value, Role.staff.value, Role.manager.value}:
        raise AppError(403, "FORBIDDEN", "You do not have permission for this action.")
    return reservation


def _ensure_customer_cutoff(settings: RestaurantSettings, reservation: Reservation) -> None:
    cutoff = to_utc(reservation.start_at) - timedelta(minutes=settings.change_cutoff_minutes)
    if utc_now() > cutoff:
        raise AppError(
            409,
            "CUTOFF_PASSED",
            "This booking can no longer be changed online. Please contact the restaurant.",
        )


def update_own_reservation(session: Session, user: User, reservation_id: int, data: ReservationBody) -> Reservation:
    reservation = session.get(Reservation, reservation_id)
    if reservation is None or reservation.customer_id != user.id:
        raise AppError(404, "NOT_FOUND", "Reservation not found.")
    if reservation.status != ReservationStatus.confirmed.value:
        raise AppError(409, "CONFLICT", "Only a confirmed booking can be changed.")
    settings = get_settings_row(session)
    _ensure_customer_cutoff(settings, reservation)
    start_at, end_at = validate_slot(settings, data.date, data.start_time)
    seat = _seat_or_404(session, data.seat_id)
    _require_bookable(seat, data.party_size)
    ensure_free(session, seat.id or 0, start_at, end_at, reservation.id)
    reservation.seat_id = seat.id or 0
    reservation.start_at = start_at
    reservation.end_at = end_at
    reservation.party_size = data.party_size
    reservation.food_preference = data.food_preference.value
    reservation.allergy_declaration = data.allergy_declaration.value
    reservation.allergy_details = data.allergy_details
    reservation.updated_at = utc_now()
    _commit(session)
    session.refresh(reservation)
    return reservation


def delete_reservation(session: Session, user: User, reservation_id: int) -> None:
    reservation = session.get(Reservation, reservation_id)
    if reservation is None:
        raise AppError(404, "NOT_FOUND", "Reservation not found.")
    if user.role == Role.customer.value and reservation.customer_id != user.id:
        raise AppError(404, "NOT_FOUND", "Reservation not found.")
    if user.role not in {Role.customer.value, Role.manager.value}:
        raise AppError(403, "FORBIDDEN", "You do not have permission for this action.")
    audit(session, user.id or 0, "reservation.delete", "reservation", reservation.id)
    session.delete(reservation)
    _commit(session)


def cancel_reservation(session: Session, user: User, reservation_id: int) -> Reservation:
    reservation = session.get(Reservation, reservation_id)
    if reservation is None:
        raise AppError(404, "NOT_FOUND", "Reservation not found.")
    if user.role == Role.customer.value and reservation.customer_id != user.id:
        raise AppError(404, "NOT_FOUND", "Reservation not found.")
    if user.role == Role.customer.value:
        if reservation.status != ReservationStatus.confirmed.value:
            raise AppError(409, "CONFLICT", "Only a confirmed booking can be cancelled.")
        _ensure_customer_cutoff(get_settings_row(session), reservation)
    elif user.role in {Role.staff.value, Role.manager.value}:
        if reservation.status == ReservationStatus.seated.value:
            raise AppError(409, "CONFLICT", "Seated bookings cannot be cancelled.")
        if reservation.status != ReservationStatus.confirmed.value:
            raise AppError(409, "CONFLICT", "Only a confirmed booking can be cancelled.")
        audit(session, user.id or 0, "reservation.cancel", "reservation", reservation.id)
    else:
        raise AppError(403, "FORBIDDEN", "You do not have permission for this action.")
    reservation.status = ReservationStatus.cancelled.value
    reservation.updated_at = utc_now()
    _commit(session)
    session.refresh(reservation)
    return reservation


def update_status(session: Session, actor: User, reservation_id: int, new_status: ReservationStatus) -> Reservation:
    reservation = session.get(Reservation, reservation_id)
    if reservation is None:
        raise AppError(404, "NOT_FOUND", "Reservation not found.")
    target = new_status.value
    if target == ReservationStatus.cancelled.value:
        raise AppError(400, "INVALID_STATUS", "Use the cancel action to cancel a booking.")
    if reservation.status == target:
        raise AppError(409, "CONFLICT", f"This booking is already {target}.")
    if target not in STATUS_FLOW.get(reservation.status, set()):
        raise AppError(409, "INVALID_STATUS", "That status change is not allowed.")
    reservation.status = target
    reservation.updated_at = utc_now()
    audit(session, actor.id or 0, "reservation.status", "reservation", reservation.id)
    _commit(session)
    session.refresh(reservation)
    return reservation


def list_today(session: Session) -> list[ReservationRead]:
    settings = get_settings_row(session)
    today = datetime.now(ZoneInfo(settings.timezone)).date()
    start, end = day_bounds_utc(today, settings.timezone)
    rows = session.exec(
        select(Reservation)
        .where(col(Reservation.status).in_(BLOCKING))
        .where(Reservation.start_at >= start)
        .where(Reservation.start_at < end)
        .order_by(Reservation.start_at)
    ).all()
    return [reservation_read(session, row) for row in rows]


def list_all(
    session: Session,
    day_from: date | None,
    day_to: date | None,
    status: str | None,
) -> list[ReservationRead]:
    settings = get_settings_row(session)
    if day_from and day_to and day_from > day_to:
        raise AppError(400, "VALIDATION_ERROR", "The start date must be on or before the end date.")
    query = select(Reservation).order_by(col(Reservation.start_at).desc())
    if status:
        query = query.where(Reservation.status == status)
    if day_from:
        start, _end = day_bounds_utc(day_from, settings.timezone)
        query = query.where(Reservation.start_at >= start)
    if day_to:
        _start, end = day_bounds_utc(day_to, settings.timezone)
        query = query.where(Reservation.start_at < end)
    return [reservation_read(session, row) for row in session.exec(query).all()]


def create_staff(session: Session, actor: User, data: StaffCreate) -> User:
    if session.exec(select(User).where(User.email == data.email)).first():
        raise AppError(409, "EMAIL_TAKEN", "An account with this email already exists.")
    staff = User(
        full_name=data.full_name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=Role.staff.value,
        is_active=True,
    )
    session.add(staff)
    session.flush()
    audit(session, actor.id or 0, "staff.create", "user", staff.id)
    _commit(session)
    session.refresh(staff)
    return staff


def list_staff(session: Session) -> list[UserPublic]:
    rows = session.exec(select(User).where(User.role == Role.staff.value).order_by(User.full_name)).all()
    return [user_public(row) for row in rows]


def get_staff_account(session: Session, staff_id: int) -> User:
    staff = session.get(User, staff_id)
    if staff is None or staff.role != Role.staff.value:
        raise AppError(404, "NOT_FOUND", "Staff account not found.")
    return staff


def delete_staff(session: Session, actor: User, staff_id: int) -> None:
    staff = get_staff_account(session, staff_id)
    acted = session.exec(select(AuditLog).where(AuditLog.actor_id == staff.id)).first()
    booked = session.exec(select(Reservation).where(Reservation.customer_id == staff.id)).first()
    if acted is not None or booked is not None:
        raise AppError(
            409,
            "ACCOUNT_IN_USE",
            "This account has activity and cannot be deleted. Deactivate it instead.",
        )
    session.delete(staff)
    audit(session, actor.id or 0, "staff.delete", "user", staff_id)
    _commit(session)


def update_staff(session: Session, actor: User, staff_id: int, data: StaffUpdate) -> User:
    staff = get_staff_account(session, staff_id)
    if data.full_name is not None:
        staff.full_name = data.full_name
    if data.is_active is not None:
        staff.is_active = data.is_active
    if data.password is not None:
        staff.password_hash = hash_password(data.password)
    staff.updated_at = utc_now()
    audit(session, actor.id or 0, "staff.update", "user", staff.id)
    _commit(session)
    session.refresh(staff)
    return staff


def update_settings(session: Session, actor: User, data: SettingsUpdate) -> RestaurantSettings:
    row = get_settings_row(session)
    row.open_time = _clock(data.open_time)
    row.close_time = _clock(data.close_time)
    row.duration_minutes = data.duration_minutes
    row.slot_interval_minutes = data.slot_interval_minutes
    row.min_lead_minutes = data.min_lead_minutes
    row.advance_days = data.advance_days
    row.change_cutoff_minutes = data.change_cutoff_minutes
    row.timezone = data.timezone
    row.updated_at = utc_now()
    audit(session, actor.id or 0, "settings.update", "settings", row.id)
    _commit(session)
    session.refresh(row)
    return row


def summary(session: Session, day_from: date, day_to: date) -> SummaryRead:
    if day_from > day_to:
        raise AppError(400, "VALIDATION_ERROR", "The start date must be on or before the end date.")
    settings = get_settings_row(session)
    start, _end = day_bounds_utc(day_from, settings.timezone)
    _start, end = day_bounds_utc(day_to, settings.timezone)
    statuses = session.exec(
        select(Reservation.status).where(Reservation.start_at >= start).where(Reservation.start_at < end)
    ).all()
    counts = {status.value: 0 for status in ReservationStatus}
    for status in statuses:
        counts[status] = counts.get(status, 0) + 1
    return SummaryRead(date_from=day_from, date_to=day_to, total=len(statuses), by_status=counts)
