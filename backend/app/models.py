from datetime import datetime
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.timeutil import utc_now


class Role(str, Enum):
    customer = "customer"
    staff = "staff"
    manager = "manager"


class AccountRole(str, Enum):
    user = "user"
    admin = "admin"


class ReservationStatus(str, Enum):
    confirmed = "confirmed"
    seated = "seated"
    completed = "completed"
    cancelled = "cancelled"


class FoodPreference(str, Enum):
    vegetarian = "vegetarian"
    non_vegetarian = "non_vegetarian"


class AllergyDeclaration(str, Enum):
    none = "none"
    specified = "specified"


class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role in ('customer', 'staff', 'manager')", name="ck_user_role"),
    )

    id: int | None = Field(default=None, primary_key=True)
    full_name: str
    email: str = Field(unique=True, index=True)
    password_hash: str
    role: str = Field(index=True)
    account_role: str = Field(default=AccountRole.user.value, index=True)
    is_active: bool = True
    failed_attempts: int = 0
    locked_until: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    banned_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    ban_reason: str | None = None
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class Seat(SQLModel, table=True):
    __tablename__ = "seats"
    __table_args__ = (
        CheckConstraint("capacity >= 1 AND capacity <= 20", name="ck_seat_capacity"),
    )

    id: int | None = Field(default=None, primary_key=True)
    seat_number: str = Field(unique=True, index=True)
    capacity: int
    description: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class Reservation(SQLModel, table=True):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint("party_size >= 1 AND party_size <= 20", name="ck_party_size"),
        CheckConstraint("end_at > start_at", name="ck_reservation_time"),
        CheckConstraint(
            "status in ('confirmed', 'seated', 'completed', 'cancelled')",
            name="ck_reservation_status",
        ),
        CheckConstraint(
            "food_preference in ('vegetarian', 'non_vegetarian')",
            name="ck_food_preference",
        ),
        CheckConstraint(
            "allergy_declaration in ('none', 'specified')",
            name="ck_allergy_declaration",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="users.id", index=True)
    seat_id: int = Field(foreign_key="seats.id", index=True)
    start_at: datetime = Field(index=True, sa_type=DateTime(timezone=True))
    end_at: datetime = Field(sa_type=DateTime(timezone=True))
    party_size: int
    food_preference: str
    allergy_declaration: str
    allergy_details: str | None = None
    status: str = Field(default=ReservationStatus.confirmed.value, index=True)
    group_id: int | None = Field(default=None, foreign_key="dining_groups.id", index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class RestaurantSettings(SQLModel, table=True):
    __tablename__ = "restaurant_settings"

    id: int | None = Field(default=None, primary_key=True)
    open_time: str
    close_time: str
    duration_minutes: int
    slot_interval_minutes: int
    min_lead_minutes: int
    advance_days: int
    change_cutoff_minutes: int
    timezone: str
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: int | None = Field(default=None, primary_key=True)
    actor_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    action: str
    target_type: str
    target_id: int | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    detail: str | None = None
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class RefreshSession(SQLModel, table=True):
    __tablename__ = "refresh_sessions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    token_hash: str = Field(unique=True, index=True)
    expires_at: datetime = Field(sa_type=DateTime(timezone=True))
    revoked_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    replaced_by_id: int | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class DiningGroup(SQLModel, table=True):
    __tablename__ = "dining_groups"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    owner_id: int = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class GroupMember(SQLModel, table=True):
    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_group_member"),)

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="dining_groups.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    can_create: bool = False
    can_update: bool = False
    can_assign: bool = False
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
