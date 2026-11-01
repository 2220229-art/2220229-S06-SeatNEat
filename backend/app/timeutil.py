from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def local_datetime(day: date, clock: time, tz_name: str) -> datetime:
    return datetime.combine(day, clock.replace(tzinfo=None), tzinfo=ZoneInfo(tz_name))


def day_bounds_utc(day: date, tz_name: str) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=ZoneInfo(tz_name))
    end = start + timedelta(days=1)
    return to_utc(start), to_utc(end)
