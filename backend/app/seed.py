import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.config import Settings
from app.models import AccountRole, DiningGroup, GroupMember, Reservation, RestaurantSettings, Role, Seat, User
from app.schemas import ReservationBody
from app.security import hash_password, password_hasher, verify_password
from app.services import create_reservation

logger = logging.getLogger("sitneat")

DEMO_MANAGER_EMAIL = "manager@sitneat.com"
DEMO_MANAGER_PASSWORD = "Manager123!"
DEMO_STAFF_EMAIL = "staff@sitneat.com"
DEMO_STAFF_PASSWORD = "Staff123!"
DEMO_CUSTOMER_EMAIL = "customer@sitneat.com"
DEMO_CUSTOMER_PASSWORD = "Customer123!"
DEMO_ADMIN_EMAIL = "arafat.admin@sitneat.com"
DEMO_ADMIN_PASSWORD = "Admin123!"
DEMO_GUEST_EMAIL = "rifat.guest@sitneat.com"
DEMO_GUEST_PASSWORD = "Guest123!"
DEMO_GROUP_NAME = "Window party"

DEFAULT_SETTINGS = {
    "open_time": "11:00",
    "close_time": "22:00",
    "duration_minutes": 90,
    "slot_interval_minutes": 30,
    "min_lead_minutes": 60,
    "advance_days": 30,
    "change_cutoff_minutes": 120,
    "timezone": "Asia/Dhaka",
}


def _first_bookable(row: RestaurantSettings) -> tuple[datetime, time] | None:
    tz = ZoneInfo(row.timezone)
    now = datetime.now(tz)
    open_h, open_m = (int(part) for part in row.open_time.split(":"))
    close_h, close_m = (int(part) for part in row.close_time.split(":"))
    open_minutes = open_h * 60 + open_m
    close_minutes = close_h * 60 + close_m
    earliest = now + timedelta(minutes=row.min_lead_minutes)
    for offset in range(3):
        day = now.date() + timedelta(days=offset)
        minute = open_minutes
        while minute + row.duration_minutes <= close_minutes:
            clock = time(minute // 60, minute % 60)
            local = datetime.combine(day, clock, tzinfo=tz)
            if local >= earliest:
                return local, clock
            minute += row.slot_interval_minutes
    return None


def _ensure_account(
    session: Session,
    full_name: str,
    email: str,
    password: str,
    role: str,
    account_role: str,
) -> User:
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing is not None:
        return existing
    user = User(
        full_name=full_name,
        email=email,
        password_hash=hash_password(password),
        role=role,
        account_role=account_role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _sync_demo_password(session: Session, email: str, password: str) -> None:
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None or verify_password(password, user.password_hash):
        return
    try:
        legacy = password_hasher.verify(password, user.password_hash)
    except Exception:
        legacy = False
    if not legacy:
        return
    user.password_hash = hash_password(password)
    user.failed_attempts = 0
    user.locked_until = None
    session.add(user)


def _ensure_demo_group(session: Session) -> None:
    existing = session.exec(select(DiningGroup).where(DiningGroup.name == DEMO_GROUP_NAME)).first()
    owner = session.exec(select(User).where(User.email == DEMO_CUSTOMER_EMAIL)).first()
    staff = session.exec(select(User).where(User.email == DEMO_STAFF_EMAIL)).first()
    guest = session.exec(select(User).where(User.email == DEMO_GUEST_EMAIL)).first()
    if owner is None or staff is None or guest is None:
        return
    if existing is None:
        existing = DiningGroup(name=DEMO_GROUP_NAME, owner_id=owner.id or 0)
        session.add(existing)
        session.commit()
        session.refresh(existing)
    for person, can_create, can_update, can_assign in (
        (staff, False, True, True),
        (guest, True, False, False),
    ):
        member = session.exec(
            select(GroupMember).where(
                GroupMember.group_id == existing.id,
                GroupMember.user_id == person.id,
            )
        ).first()
        if member is None:
            session.add(
                GroupMember(
                    group_id=existing.id or 0,
                    user_id=person.id or 0,
                    can_create=can_create,
                    can_update=can_update,
                    can_assign=can_assign,
                )
            )


def seed_database(engine, settings: Settings) -> None:
    with Session(engine) as session:
        if session.get(RestaurantSettings, 1) is None and session.exec(select(RestaurantSettings)).first() is None:
            session.add(RestaurantSettings(id=1, **DEFAULT_SETTINGS))
            session.commit()
        if not settings.seed_demo:
            return
        fresh = session.exec(select(User)).first() is None
        if fresh:
            session.add(
                User(
                    full_name="Nadia Karim",
                    email=DEMO_MANAGER_EMAIL,
                    password_hash=hash_password(DEMO_MANAGER_PASSWORD),
                    role=Role.manager.value,
                    account_role=AccountRole.admin.value,
                )
            )
            session.add(
                User(
                    full_name="Rahim Uddin",
                    email=DEMO_STAFF_EMAIL,
                    password_hash=hash_password(DEMO_STAFF_PASSWORD),
                    role=Role.staff.value,
                    account_role=AccountRole.user.value,
                )
            )
            session.add(
                User(
                    full_name="Maya Chowdhury",
                    email=DEMO_CUSTOMER_EMAIL,
                    password_hash=hash_password(DEMO_CUSTOMER_PASSWORD),
                    role=Role.customer.value,
                    account_role=AccountRole.user.value,
                )
            )
            session.add(Seat(seat_number="A1", capacity=2, description="Window table for two"))
            session.add(Seat(seat_number="A2", capacity=4, description="Family table"))
            session.add(Seat(seat_number="B1", capacity=6, description="Large table"))
            session.add(Seat(seat_number="B2", capacity=4, description="Corner booth"))
            session.commit()
        _ensure_account(
            session,
            "Arafat Hossain",
            DEMO_ADMIN_EMAIL,
            DEMO_ADMIN_PASSWORD,
            Role.manager.value,
            AccountRole.admin.value,
        )
        _ensure_account(
            session,
            "Rifat Ahmed",
            DEMO_GUEST_EMAIL,
            DEMO_GUEST_PASSWORD,
            Role.customer.value,
            AccountRole.user.value,
        )
        for email, account_role in (
            (DEMO_MANAGER_EMAIL, AccountRole.admin.value),
            (DEMO_STAFF_EMAIL, AccountRole.user.value),
            (DEMO_CUSTOMER_EMAIL, AccountRole.user.value),
        ):
            existing = session.exec(select(User).where(User.email == email)).first()
            if existing is not None and existing.account_role != account_role:
                existing.account_role = account_role
                session.add(existing)
        _ensure_demo_group(session)
        for email, password in (
            (DEMO_MANAGER_EMAIL, DEMO_MANAGER_PASSWORD),
            (DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD),
            (DEMO_STAFF_EMAIL, DEMO_STAFF_PASSWORD),
            (DEMO_CUSTOMER_EMAIL, DEMO_CUSTOMER_PASSWORD),
            (DEMO_GUEST_EMAIL, DEMO_GUEST_PASSWORD),
        ):
            _sync_demo_password(session, email, password)
        session.commit()

    with Session(engine) as session:
        try:
            row = session.get(RestaurantSettings, 1)
            customer = session.exec(select(User).where(User.email == DEMO_CUSTOMER_EMAIL)).first()
            seat = session.exec(select(Seat).where(Seat.seat_number == "A1")).first()
            if row is None or customer is None or seat is None:
                return
            already = session.exec(select(Reservation).where(Reservation.customer_id == customer.id)).first()
            if already is not None:
                return
            slot = _first_bookable(row)
            if slot is None:
                return
            local, _clock = slot
            create_reservation(
                session,
                customer,
                ReservationBody(
                    seat_id=seat.id or 0,
                    date=local.date(),
                    start_time=local.time().replace(tzinfo=None),
                    party_size=2,
                    food_preference="vegetarian",
                    allergy_declaration="none",
                ),
            )
            logger.info("Demo reservation created.")
        except Exception:
            session.rollback()
            logger.info("Demo reservation was not created.")
