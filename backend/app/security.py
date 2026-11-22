import os
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.models import Role

LOCAL_PEPPER = "sitneat-local-pepper"

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


def password_pepper() -> str:
    return os.getenv("PASSWORD_PEPPER") or LOCAL_PEPPER


def hash_password(password: str) -> str:
    return password_hasher.hash(f"{password}{password_pepper()}")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(f"{password}{password_pepper()}", password_hash)
    except Exception:
        return False


def has_scope(role: str, scope: str) -> bool:
    return scope in SCOPES.get(role, set())


def create_access_token(user_id: int, role: str, secret_key: str, expires_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    minutes = min(max(int(expires_minutes), 1), 15)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def decode_access_token(token: str, secret_key: str) -> dict:
    payload = jwt.decode(
        token,
        secret_key,
        algorithms=["HS256"],
        options={"require": ["exp", "sub", "role"]},
    )
    if payload.get("role") not in {"user", "admin"}:
        raise jwt.InvalidTokenError("Access token role is not valid.")
    return payload
