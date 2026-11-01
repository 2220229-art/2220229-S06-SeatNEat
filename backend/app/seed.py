import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.config import Settings
from app.models import RestaurantSettings, Role, Seat, User
from app.schemas import ReservationBody
from app.security import hash_password
from app.services import create_reservation

logger = logging.getLogger("sitneat")

DEMO_MANAGER_EMAIL = "manager@sitneat.com"
DEMO_MANAGER_PASSWORD = "Manager123!"
DEMO_STAFF_EMAIL = "staff@sitneat.com"
DEMO_STAFF_PASSWORD = "Staff123!"
DEMO_CUSTOMER_EMAIL = "customer@sitneat.com"
DEMO_CUSTOMER_PASSWORD = "Customer123!"

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


def seed_database(engine, settings: Settings) -> None:
    with Session(engine) as session:
        if session.get(RestaurantSettings, 1) is None and session.exec(select(RestaurantSettings)).first() is None:
            session.add(RestaurantSettings(id=1, **DEFAULT_SETTINGS))
            session.commit()
        if not settings.seed_demo:
            return
        if session.exec(select(User)).first() is not None:
            return
        session.add(
            User(
                full_name="Nadia Karim",
                email=DEMO_MANAGER_EMAIL,
                password_hash=hash_password(DEMO_MANAGER_PASSWORD),
                role=Role.manager.value,
            )
        )
        session.add(
            User(
                full_name="Rahim Uddin",
                email=DEMO_STAFF_EMAIL,
                password_hash=hash_password(DEMO_STAFF_PASSWORD),
                role=Role.staff.value,
            )
        )
        customer = User(
            full_name="Maya Chowdhury",
            email=DEMO_CUSTOMER_EMAIL,
            password_hash=hash_password(DEMO_CUSTOMER_PASSWORD),
            role=Role.customer.value,
        )
        session.add(customer)
        session.add(Seat(seat_number="A1", capacity=2, description="Window table for two"))
        session.add(Seat(seat_number="A2", capacity=4, description="Family table"))
        session.add(Seat(seat_number="B1", capacity=6, description="Large table"))
        session.add(Seat(seat_number="B2", capacity=4, description="Corner booth"))
        session.commit()
        session.refresh(customer)

    with Session(engine) as session:
        try:
            row = session.get(RestaurantSettings, 1)
            customer = session.exec(select(User).where(User.email == DEMO_CUSTOMER_EMAIL)).first()
            seat = session.exec(select(Seat).where(Seat.seat_number == "A1")).first()
            if row is None or customer is None or seat is None:
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
