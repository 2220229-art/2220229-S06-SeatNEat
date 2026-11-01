from datetime import date, datetime, time

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models import AllergyDeclaration, FoodPreference, ReservationStatus, Role


def _clean_name(value: str) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) < 2:
        raise ValueError("Name must be at least 2 characters.")
    return cleaned


def _clean_email(value: str) -> str:
    return value.strip().lower()


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str | None = None

    @field_validator("full_name")
    @classmethod
    def name_ok(cls, value: str) -> str:
        return _clean_name(value)

    @field_validator("email")
    @classmethod
    def email_ok(cls, value: str) -> str:
        return _clean_email(value)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def email_ok(cls, value: str) -> str:
        return _clean_email(value)


class UserPublic(BaseModel):
    id: int
    full_name: str
    email: str
    role: Role
    is_active: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


class SeatCreate(BaseModel):
    seat_number: str = Field(min_length=1, max_length=20)
    capacity: int = Field(ge=1, le=20)
    description: str | None = Field(default=None, max_length=200)
    is_active: bool = True

    @field_validator("seat_number")
    @classmethod
    def number_ok(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Seat number is required.")
        return cleaned

    @field_validator("description")
    @classmethod
    def description_ok(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class SeatUpdate(BaseModel):
    seat_number: str | None = Field(default=None, min_length=1, max_length=20)
    capacity: int | None = Field(default=None, ge=1, le=20)
    description: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None

    @field_validator("seat_number")
    @classmethod
    def number_ok(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Seat number is required.")
        return cleaned

    @field_validator("description")
    @classmethod
    def description_ok(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class SeatRead(BaseModel):
    id: int
    seat_number: str
    capacity: int
    description: str | None
    is_active: bool


class AvailabilitySeat(BaseModel):
    id: int
    seat_number: str
    capacity: int
    description: str | None
    available: bool = True


class ReservationBody(BaseModel):
    seat_id: int = Field(ge=1)
    date: date
    start_time: time
    party_size: int = Field(ge=1, le=20)
    food_preference: FoodPreference
    allergy_declaration: AllergyDeclaration
    allergy_details: str | None = None

    @model_validator(mode="after")
    def allergy_rules(self):
        if self.allergy_declaration == AllergyDeclaration.specified:
            details = (self.allergy_details or "").strip()
            if not details:
                raise ValueError("Please describe the allergies.")
            if len(details) > 300:
                raise ValueError("Allergy details must be 300 characters or fewer.")
            self.allergy_details = details
        else:
            self.allergy_details = None
        return self


class ReservationRead(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    seat_id: int
    seat_number: str
    start_at: datetime
    end_at: datetime
    party_size: int
    food_preference: FoodPreference
    allergy_declaration: AllergyDeclaration
    allergy_details: str | None
    status: ReservationStatus


class StatusUpdate(BaseModel):
    status: ReservationStatus


class StaffCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str | None = None

    @field_validator("full_name")
    @classmethod
    def name_ok(cls, value: str) -> str:
        return _clean_name(value)

    @field_validator("email")
    @classmethod
    def email_ok(cls, value: str) -> str:
        return _clean_email(value)

    @model_validator(mode="after")
    def staff_only(self):
        if self.role is not None and self.role != Role.staff.value:
            raise ValueError("Only staff accounts can be created here.")
        return self


class StaffUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("full_name")
    @classmethod
    def name_ok(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_name(value)


class SettingsUpdate(BaseModel):
    open_time: time
    close_time: time
    duration_minutes: int = Field(ge=30, le=300)
    slot_interval_minutes: int
    min_lead_minutes: int = Field(ge=0, le=10080)
    advance_days: int = Field(ge=1, le=365)
    change_cutoff_minutes: int = Field(ge=0, le=10080)
    timezone: str = Field(min_length=1, max_length=64)

    @field_validator("slot_interval_minutes")
    @classmethod
    def slot_ok(cls, value: int) -> int:
        if value not in {15, 30, 60}:
            raise ValueError("Slot interval must be 15, 30, or 60 minutes.")
        return value

    @model_validator(mode="after")
    def hours_ok(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        if self.close_time <= self.open_time:
            raise ValueError("Closing time must be after opening time.")
        open_minutes = self.open_time.hour * 60 + self.open_time.minute
        close_minutes = self.close_time.hour * 60 + self.close_time.minute
        if close_minutes - open_minutes < self.duration_minutes:
            raise ValueError("Opening hours must fit at least one reservation.")
        if self.duration_minutes % self.slot_interval_minutes != 0:
            raise ValueError("Duration must be a multiple of the slot interval.")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            raise ValueError("Timezone is not recognized.")
        return self


class SettingsRead(BaseModel):
    open_time: str
    close_time: str
    duration_minutes: int
    slot_interval_minutes: int
    min_lead_minutes: int
    advance_days: int
    change_cutoff_minutes: int
    timezone: str


class SummaryRead(BaseModel):
    date_from: date
    date_to: date
    total: int
    by_status: dict[str, int]
