import jwt
from fastapi.testclient import TestClient

from app.seed import (
    DEMO_ADMIN_EMAIL,
    DEMO_ADMIN_PASSWORD,
    DEMO_CUSTOMER_EMAIL,
    DEMO_CUSTOMER_PASSWORD,
    DEMO_GROUP_NAME,
    DEMO_GUEST_EMAIL,
    DEMO_GUEST_PASSWORD,
    DEMO_MANAGER_EMAIL,
    DEMO_MANAGER_PASSWORD,
    DEMO_STAFF_EMAIL,
    DEMO_STAFF_PASSWORD,
)
from tests.test_api import client, future_day, login


def test_login_token_contains_user_id_and_role(client: TestClient):
    headers, user = login(client, DEMO_CUSTOMER_EMAIL, DEMO_CUSTOMER_PASSWORD)
    token = headers["Authorization"].removeprefix("Bearer ")
    payload = jwt.decode(token, options={"verify_signature": False})
    assert payload["sub"] == str(user["id"])
    assert payload["role"] == "user"
    assert user["account_role"] == "user"


def test_missing_and_tampered_tokens_are_rejected(client: TestClient):
    missing = client.get("/api/v1/auth/me")
    assert missing.status_code == 401
    headers, _user = login(client, DEMO_CUSTOMER_EMAIL, DEMO_CUSTOMER_PASSWORD)
    token = headers["Authorization"].removeprefix("Bearer ")
    tampered = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}x"})
    assert tampered.status_code == 401


def test_customer_cannot_open_admin_overview(client: TestClient):
    headers, _user = login(client, DEMO_CUSTOMER_EMAIL, DEMO_CUSTOMER_PASSWORD)
    response = client.get("/api/v1/admin/overview", headers=headers)
    assert response.status_code == 403


def test_member_without_create_permission_cannot_book_for_the_group(client: TestClient):
    staff_headers, _staff = login(client, DEMO_STAFF_EMAIL, DEMO_STAFF_PASSWORD)
    customer_headers, _customer = login(client, DEMO_CUSTOMER_EMAIL, DEMO_CUSTOMER_PASSWORD)
    groups = client.get("/api/v1/groups", headers=customer_headers)
    assert groups.status_code == 200
    group = next(item for item in groups.json() if item["name"] == DEMO_GROUP_NAME)
    response = client.post(
        f"/api/v1/groups/{group['id']}/reservations",
        headers=staff_headers,
        json={
            "seat_id": 1,
            "date": future_day(),
            "start_time": "18:00:00",
            "party_size": 2,
            "food_preference": "vegetarian",
            "allergy_declaration": "none",
        },
    )
    assert response.status_code == 403


def test_only_the_owner_can_rename_a_group(client: TestClient):
    staff_headers, _staff = login(client, DEMO_STAFF_EMAIL, DEMO_STAFF_PASSWORD)
    customer_headers, _customer = login(client, DEMO_CUSTOMER_EMAIL, DEMO_CUSTOMER_PASSWORD)
    groups = client.get("/api/v1/groups", headers=customer_headers)
    group = next(item for item in groups.json() if item["name"] == DEMO_GROUP_NAME)
    denied = client.patch(
        f"/api/v1/groups/{group['id']}",
        headers=staff_headers,
        json={"name": "Taken over"},
    )
    assert denied.status_code == 403
    renamed = client.patch(
        f"/api/v1/groups/{group['id']}",
        headers=customer_headers,
        json={"name": "Window party"},
    )
    assert renamed.status_code == 200


def test_admin_cannot_ban_another_admin(client: TestClient):
    headers, _manager = login(client, DEMO_MANAGER_EMAIL, DEMO_MANAGER_PASSWORD)
    users = client.get("/api/v1/admin/users", headers=headers)
    assert users.status_code == 200
    other_admin = next(item for item in users.json()["items"] if item["email"] == DEMO_ADMIN_EMAIL)
    response = client.post(
        f"/api/v1/admin/users/{other_admin['id']}/ban",
        headers=headers,
        json={"reason": "Should not be allowed"},
    )
    assert response.status_code == 403


def test_admin_cannot_change_own_role(client: TestClient):
    headers, manager = login(client, DEMO_MANAGER_EMAIL, DEMO_MANAGER_PASSWORD)
    response = client.post(
        f"/api/v1/admin/users/{manager['id']}/role",
        headers=headers,
        json={"account_role": "user"},
    )
    assert response.status_code == 403


def test_banned_user_is_rejected_on_the_next_request(client: TestClient):
    admin_headers, _admin = login(client, DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD)
    customer_headers, customer = login(client, DEMO_CUSTOMER_EMAIL, DEMO_CUSTOMER_PASSWORD)
    banned = client.post(
        f"/api/v1/admin/users/{customer['id']}/ban",
        headers=admin_headers,
        json={"reason": "Repeated no-shows"},
    )
    assert banned.status_code == 200
    follow_up = client.get("/api/v1/auth/me", headers=customer_headers)
    assert follow_up.status_code == 401


def test_wrong_password_locks_the_account(client: TestClient):
    for _ in range(5):
        failed = client.post(
            "/api/v1/auth/login",
            json={"email": DEMO_STAFF_EMAIL, "password": "not-the-password"},
        )
        assert failed.status_code == 401
    locked = client.post(
        "/api/v1/auth/login",
        json={"email": DEMO_STAFF_EMAIL, "password": DEMO_STAFF_PASSWORD},
    )
    assert locked.status_code == 429


def test_password_change_requires_the_current_password(client: TestClient):
    headers, _user = login(client, DEMO_GUEST_EMAIL, DEMO_GUEST_PASSWORD)
    wrong = client.post(
        "/api/v1/auth/password",
        headers=headers,
        json={"current_password": "Guest000!", "new_password": "Guest456!"},
    )
    assert wrong.status_code == 401
    changed = client.post(
        "/api/v1/auth/password",
        headers=headers,
        json={"current_password": "Guest123!", "new_password": "Guest456!"},
    )
    assert changed.status_code == 204
    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": DEMO_GUEST_EMAIL, "password": "Guest123!"},
    )
    assert old_login.status_code == 401
