from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.models import Role

# Argon2id with a moderate memory setting so local tests stay practical.
password_hasher = PasswordHash((Argon2Hasher(time_cost=2, memory_cost=19456, parallelism=1),))

CUSTOMER_SCOPES = {
    "seats:read",
    "settings:read",
    "reservations:create:own",
    "reservations:read:own",
    "reservations:update:own",
    "reservations:cancel:own",
    "reservations:delete:own",
}

STAFF_SCOPES = {
    "seats:read",
    "settings:read",
    "reservations:read:operational",
    "reservations:update:operational",
    "reservations:cancel:operational",
}

MANAGER_SCOPES = STAFF_SCOPES | {
    "seats:manage",
    "settings:manage",
    "reservations:read:all",
    "reservations:delete:all",
    "staff:manage",
    "reports:read",
}

SCOPES: dict[str, set[str]] = {
    Role.customer.value: CUSTOMER_SCOPES,
    Role.staff.value: STAFF_SCOPES,
    Role.manager.value: MANAGER_SCOPES,
}


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password, password_hash)
    except Exception:
        return False


def has_scope(role: str, scope: str) -> bool:
    return scope in SCOPES.get(role, set())


def create_access_token(user_id: int, secret_key: str, expires_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def decode_access_token(token: str, secret_key: str) -> dict:
    return jwt.decode(token, secret_key, algorithms=["HS256"], options={"require": ["exp", "sub"]})
