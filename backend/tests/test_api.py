from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import Settings
from app.models import Reservation
from app.seed import (
    DEMO_CUSTOMER_EMAIL,
    DEMO_CUSTOMER_PASSWORD,
    DEMO_MANAGER_EMAIL,
    DEMO_MANAGER_PASSWORD,
    DEMO_STAFF_EMAIL,
    DEMO_STAFF_PASSWORD,
)
from app.timeutil import to_utc
from main import create_app


@pytest.fixture()
def client(tmp_path):
    database = tmp_path / "test.db"
    settings = Settings(
        app_env="test",
        secret_key="test-secret-key-for-sitneat-course-demo",
        database_url=f"sqlite:///{database.as_posix()}",
        access_token_expire_minutes=60,
        frontend_origin="https://2220229-s06-seatneat.vercel.app/",
        seed_demo=True,
    )
    application = create_app(settings)
    with TestClient(application, raise_server_exceptions=False) as test_client:
        yield test_client


def test_api_docs_are_served_under_the_api_prefix(client: TestClient):
    docs = client.get("/api/docs")
    assert docs.status_code == 200
    assert "swagger" in docs.text.lower()
    trailed = client.get("/api/docs/", follow_redirects=False)
    assert trailed.status_code in {307, 308}
    spec = client.get("/api/openapi.json")
    assert spec.status_code == 200
    assert spec.json()["info"]["title"] == "SitNeat"


def future_day(days: int = 2) -> str:
    return (datetime.now(ZoneInfo("Asia/Dhaka")) + timedelta(days=days)).date().isoformat()


def login(client: TestClient, email: str, password: str):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]


def register_customer(client: TestClient, email: str, full_name: str = "Test Guest"):
    response = client.post(
        "/api/v1/auth/register",
        json={"full_name": full_name, "email": email, "password": "password123", "role": "manager"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "customer"
    return login(client, email, "password123")


def seat_ids(client: TestClient, headers: dict) -> dict[str, int]:
    response = client.get("/api/v1/seats", headers=headers)
    assert response.status_code == 200, response.text
    return {seat["seat_number"]: seat["id"] for seat in response.json()}


def book(client: TestClient, headers: dict, seat_id: int, day: str, **overrides):
    payload = {
        "seat_id": seat_id,
        "date": day,
        "start_time": "18:00",
        "party_size": 2,
        "food_preference": "vegetarian",
        "allergy_declaration": "none",
    }
    payload.update(overrides)
    return client.post("/api/v1/reservations", headers=headers, json=payload)


def settings_payload(**overrides):
    payload = {
        "open_time": "11:00",
        "close_time": "22:00",
        "duration_minutes": 90,
        "slot_interval_minutes": 30,
        "min_lead_minutes": 60,
        "advance_days": 30,
        "change_cutoff_minutes": 120,
        "timezone": "Asia/Dhaka",
    }
    payload.update(overrides)
    return payload


def test_health(client: TestClient):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/v1/health").status_code == 200


def test_t01_register_ignores_requested_role(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Amina Rahman",
            "email": "amina@example.com",
            "password": "password123",
            "role": "manager",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "customer"
    assert "password" not in body


def test_t02_bad_password_and_inactive_account_are_rejected(client: TestClient):
    wrong = client.post(
        "/api/v1/auth/login",
        json={"email": DEMO_CUSTOMER_EMAIL, "password": "not-the-password"},
    )
    assert wrong.status_code == 401
    assert wrong.json()["message"] == "Invalid email or password."

    manager, _user = login(client, DEMO_MANAGER_EMAIL, DEMO_MANAGER_PASSWORD)
    created = client.post(
        "/api/v1/staff",
        headers=manager,
        json={"full_name": "Temporary Staff", "email": "temp.staff@sitneat.com", "password": "Staffpass1", "role": "manager"},
    )
    assert created.status_code == 422

    created = client.post(
        "/api/v1/staff",
        headers=manager,
        json={"full_name": "Temporary Staff", "email": "temp.staff@sitneat.com", "password": "Staffpass1"},
    )
    assert created.status_code == 201
    assert created.json()["role"] == "staff"
    staff_headers, _staff = login(client, "temp.staff@sitneat.com", "Staffpass1")
    client.patch(f"/api/v1/staff/{created.json()['id']}", headers=manager, json={"is_active": False})
    assert client.get("/api/v1/auth/me", headers=staff_headers).status_code == 401
    inactive = client.post(
        "/api/v1/auth/login",
        json={"email": "temp.staff@sitneat.com", "password": "Staffpass1"},
    )
    assert inactive.status_code == 401
    assert "inactive" not in inactive.text.lower()


def test_t03_missing_token_is_rejected(client: TestClient):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_t04_customer_cannot_read_another_customers_booking(client: TestClient):
    owner, _owner = register_customer(client, "owner@example.com", "Owner Guest")
    other, _other = register_customer(client, "other@example.com", "Other Guest")
    seats = seat_ids(client, owner)
    created = book(
        client,
        owner,
        seats["A1"],
        future_day(),
        allergy_declaration="specified",
        allergy_details="peanuts and sesame",
    )
    assert created.status_code == 201, created.text
    hidden = client.get(f"/api/v1/reservations/{created.json()['id']}", headers=other)
    assert hidden.status_code == 404
    assert hidden.json()["message"] == "Reservation not found."
    assert "peanuts" not in hidden.text
    own = client.get("/api/v1/reservations/mine", headers=other)
    assert all(item["id"] != created.json()["id"] for item in own.json())


def test_t05_customer_cannot_manage_seats_or_staff(client: TestClient):
    headers, _user = register_customer(client, "guest@example.com")
    seat = client.post(
        "/api/v1/seats",
        headers=headers,
        json={"seat_number": "Z1", "capacity": 2, "description": "Extra"},
    )
    staff = client.get("/api/v1/staff", headers=headers)
    assert seat.status_code == 403
    assert staff.status_code == 403


def test_t06_party_larger_than_capacity_is_rejected(client: TestClient):
    headers, _user = register_customer(client, "party@example.com")
    seats = seat_ids(client, headers)
    response = book(client, headers, seats["A1"], future_day(), party_size=4)
    assert response.status_code == 400
    assert response.json()["code"] == "PARTY_TOO_LARGE"


def test_t07_inactive_seat_cannot_be_booked(client: TestClient):
    manager, _user = login(client, DEMO_MANAGER_EMAIL, DEMO_MANAGER_PASSWORD)
    customer, _customer = register_customer(client, "inactive-seat@example.com")
    seats = seat_ids(client, customer)
    updated = client.patch(f"/api/v1/seats/{seats['A2']}", headers=manager, json={"is_active": False})
    assert updated.status_code == 200
    response = book(client, customer, seats["A2"], future_day())
    assert response.status_code == 400
    assert response.json()["code"] == "SEAT_INACTIVE"


def test_t08_overlapping_booking_conflicts_and_exact_end_does_not(client: TestClient):
    first, _first = register_customer(client, "first@example.com", "First Guest")
    second, _second = register_customer(client, "second@example.com", "Second Guest")
    seats = seat_ids(client, first)
    day = future_day()
    original = book(client, first, seats["A1"], day, start_time="18:00")
    assert original.status_code == 201, original.text
    overlap = book(client, second, seats["A1"], day, start_time="19:00")
    assert overlap.status_code == 409
    assert overlap.json()["code"] == "SEAT_UNAVAILABLE"
    adjacent = book(client, second, seats["A1"], day, start_time="19:30")
    assert adjacent.status_code == 201, adjacent.text
    other_seat = book(client, second, seats["B1"], day, start_time="18:00")
    assert other_seat.status_code == 201, other_seat.text


def test_t09_allergy_details_are_required_when_specified(client: TestClient):
    headers, _user = register_customer(client, "allergy@example.com")
    seats = seat_ids(client, headers)
    response = book(
        client,
        headers,
        seats["A1"],
        future_day(),
        allergy_declaration="specified",
        allergy_details="   ",
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert any("allerg" in item["message"].lower() for item in response.json()["details"])


def test_t10_customer_cannot_change_after_cutoff(client: TestClient):
    manager, _manager = login(client, DEMO_MANAGER_EMAIL, DEMO_MANAGER_PASSWORD)
    saved = client.put("/api/v1/settings", headers=manager, json=settings_payload(change_cutoff_minutes=10080))
    assert saved.status_code == 200
    headers, _user = register_customer(client, "cutoff@example.com")
    seats = seat_ids(client, headers)
    created = book(client, headers, seats["A1"], future_day())
    assert created.status_code == 201, created.text
    reservation_id = created.json()["id"]
    cancelled = client.post(f"/api/v1/reservations/{reservation_id}/cancel", headers=headers)
    assert cancelled.status_code == 409
    assert cancelled.json()["code"] == "CUTOFF_PASSED"


def test_t11_illegal_status_transition_is_rejected(client: TestClient):
    customer, _customer = register_customer(client, "status@example.com")
    staff, _staff = login(client, DEMO_STAFF_EMAIL, DEMO_STAFF_PASSWORD)
    seats = seat_ids(client, customer)
    created = book(client, customer, seats["B1"], future_day())
    assert created.status_code == 201, created.text
    reservation_id = created.json()["id"]
    skipped = client.patch(
        f"/api/v1/reservations/{reservation_id}/status",
        headers=staff,
        json={"status": "completed"},
    )
    assert skipped.status_code == 409
    assert skipped.json()["code"] == "INVALID_STATUS"
    seated = client.patch(
        f"/api/v1/reservations/{reservation_id}/status",
        headers=staff,
        json={"status": "seated"},
    )
    assert seated.status_code == 200
    assert seated.json()["status"] == "seated"
    cannot_cancel = client.post(f"/api/v1/reservations/{reservation_id}/cancel", headers=staff)
    assert cannot_cancel.status_code == 409
    completed = client.patch(
        f"/api/v1/reservations/{reservation_id}/status",
        headers=staff,
        json={"status": "completed"},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"


def test_t12_staff_cannot_change_settings(client: TestClient):
    staff, _staff = login(client, DEMO_STAFF_EMAIL, DEMO_STAFF_PASSWORD)
    response = client.put("/api/v1/settings", headers=staff, json=settings_payload())
    assert response.status_code == 403


def test_t13_manager_settings_apply_to_future_bookings_only(client: TestClient):
    manager, _manager = login(client, DEMO_MANAGER_EMAIL, DEMO_MANAGER_PASSWORD)
    customer, _customer = register_customer(client, "duration@example.com")
    seats = seat_ids(client, customer)
    day = future_day()
    original = book(client, customer, seats["A1"], day)
    assert original.status_code == 201, original.text
    original_body = original.json()
    start = datetime.fromisoformat(original_body["start_at"])
    end = datetime.fromisoformat(original_body["end_at"])
    assert end - start == timedelta(minutes=90)

    updated = client.put("/api/v1/settings", headers=manager, json=settings_payload(duration_minutes=120))
    assert updated.status_code == 200
    assert updated.json()["duration_minutes"] == 120
    unchanged = client.get(f"/api/v1/reservations/{original_body['id']}", headers=customer)
    still_end = datetime.fromisoformat(unchanged.json()["end_at"])
    assert still_end - start == timedelta(minutes=90)

    later = book(client, customer, seats["A2"], day, start_time="18:00")
    assert later.status_code == 201, later.text
    later_start = datetime.fromisoformat(later.json()["start_at"])
    later_end = datetime.fromisoformat(later.json()["end_at"])
    assert later_end - later_start == timedelta(minutes=120)


def test_t14_unexpected_error_does_not_leak_secrets(client: TestClient):
    @client.app.get("/api/v1/boom")
    def boom():
        raise RuntimeError("SECRET_DB_PASSWORD=super-secret")

    response = client.get("/api/v1/boom")
    assert response.status_code == 500
    assert response.json()["code"] == "SERVER_ERROR"
    assert "SECRET_DB_PASSWORD" not in response.text
    assert "Traceback" not in response.text


def test_cancelled_booking_releases_the_seat(client: TestClient):
    headers, _user = register_customer(client, "cancel@example.com")
    seats = seat_ids(client, headers)
    day = future_day()
    created = book(client, headers, seats["A2"], day)
    assert created.status_code == 201, created.text
    cancelled = client.post(f"/api/v1/reservations/{created.json()['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    again = book(client, headers, seats["A2"], day)
    assert again.status_code == 201, again.text


def test_staff_can_cancel_for_a_guest_and_customer_cannot_list_today(client: TestClient):
    customer, _customer = register_customer(client, "guest-cancel@example.com")
    staff, _staff = login(client, DEMO_STAFF_EMAIL, DEMO_STAFF_PASSWORD)
    seats = seat_ids(client, customer)
    created = book(client, customer, seats["B2"], future_day())
    assert created.status_code == 201, created.text
    denied = client.get("/api/v1/reservations/today", headers=customer)
    assert denied.status_code == 403
    cancelled = client.post(f"/api/v1/reservations/{created.json()['id']}/cancel", headers=staff)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_today_list_and_summary(client: TestClient):
    customer, _customer = register_customer(client, "today@example.com")
    staff, _staff = login(client, DEMO_STAFF_EMAIL, DEMO_STAFF_PASSWORD)
    manager, _manager = login(client, DEMO_MANAGER_EMAIL, DEMO_MANAGER_PASSWORD)
    seats = seat_ids(client, customer)
    day = future_day()
    created = book(client, customer, seats["B2"], day)
    assert created.status_code == 201, created.text
    reservation_id = created.json()["id"]

    local = datetime.combine(datetime.now(ZoneInfo("Asia/Dhaka")).date(), datetime.min.time()).replace(
        hour=15, tzinfo=ZoneInfo("Asia/Dhaka")
    )
    with Session(client.app.state.engine) as session:
        reservation = session.get(Reservation, reservation_id)
        assert reservation is not None
        reservation.start_at = to_utc(local)
        reservation.end_at = to_utc(local + timedelta(minutes=90))
        session.add(reservation)
        session.commit()

    today = client.get("/api/v1/reservations/today", headers=staff)
    assert today.status_code == 200
    assert any(item["id"] == reservation_id for item in today.json())

    summary = client.get(
        "/api/v1/reports/summary",
        headers=manager,
        params={"date_from": day, "date_to": day},
    )
    assert summary.status_code == 200
    assert summary.json()["by_status"]["confirmed"] == 0
    staff_summary = client.get(
        "/api/v1/reports/summary",
        headers=staff,
        params={"date_from": day, "date_to": day},
    )
    assert staff_summary.status_code == 403


def test_customer_edit_and_server_owned_fields(client: TestClient):
    headers, user = register_customer(client, "edit@example.com")
    seats = seat_ids(client, headers)
    day = future_day()
    created = book(client, headers, seats["A1"], day, customer_id=999, status="seated", end_time="20:00")
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["customer_id"] == user["id"]
    assert body["status"] == "confirmed"
    start = datetime.fromisoformat(body["start_at"])
    end = datetime.fromisoformat(body["end_at"])
    assert end - start == timedelta(minutes=90)

    edited = client.patch(
        f"/api/v1/reservations/{body['id']}",
        headers=headers,
        json={
            "seat_id": seats["A2"],
            "date": day,
            "start_time": "18:30",
            "party_size": 3,
            "food_preference": "non_vegetarian",
            "allergy_declaration": "specified",
            "allergy_details": "shellfish",
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["seat_number"] == "A2"
    assert edited.json()["party_size"] == 3
    assert edited.json()["allergy_details"] == "shellfish"


def test_crud_read_single_and_delete(client: TestClient):
    owner, _owner = register_customer(client, "crud-owner@example.com")
    other, _other = register_customer(client, "crud-other@example.com")
    staff, _staff = login(client, DEMO_STAFF_EMAIL, DEMO_STAFF_PASSWORD)
    manager, _manager = login(client, DEMO_MANAGER_EMAIL, DEMO_MANAGER_PASSWORD)
    seats = seat_ids(client, owner)
    day = future_day()

    created = book(client, owner, seats["B2"], day)
    assert created.status_code == 201, created.text
    reservation_id = created.json()["id"]

    single = client.get(f"/api/v1/reservations/{reservation_id}", headers=owner)
    assert single.status_code == 200
    assert single.json()["seat_number"] == "B2"
    assert client.delete(f"/api/v1/reservations/{reservation_id}", headers=other).status_code == 404
    assert client.delete(f"/api/v1/reservations/{reservation_id}", headers=staff).status_code == 403

    removed = client.delete(f"/api/v1/reservations/{reservation_id}", headers=owner)
    assert removed.status_code == 204
    assert client.get(f"/api/v1/reservations/{reservation_id}", headers=owner).status_code == 404
    mine = client.get("/api/v1/reservations/mine", headers=owner)
    assert all(item["id"] != reservation_id for item in mine.json())

    again = book(client, owner, seats["B2"], day)
    assert again.status_code == 201, again.text
    manager_delete = client.delete(f"/api/v1/reservations/{again.json()['id']}", headers=manager)
    assert manager_delete.status_code == 204

    seat = client.post(
        "/api/v1/seats",
        headers=manager,
        json={"seat_number": "Z9", "capacity": 2, "description": "Temporary"},
    )
    assert seat.status_code == 201, seat.text
    seat_id = seat.json()["id"]
    assert client.get(f"/api/v1/seats/{seat_id}", headers=owner).json()["seat_number"] == "Z9"
    assert client.delete(f"/api/v1/seats/{seat_id}", headers=owner).status_code == 403
    booked = book(client, owner, seats["A2"], day)
    assert booked.status_code == 201, booked.text
    assert client.delete(f"/api/v1/seats/{seats['A2']}", headers=manager).status_code == 409
    assert client.delete(f"/api/v1/seats/{seat_id}", headers=manager).status_code == 204
    assert client.get(f"/api/v1/seats/{seat_id}", headers=manager).status_code == 404

    created_staff = client.post(
        "/api/v1/staff",
        headers=manager,
        json={"full_name": "Delete Me", "email": "delete.me@sitneat.com", "password": "Staffpass1"},
    )
    assert created_staff.status_code == 201, created_staff.text
    staff_id = created_staff.json()["id"]
    assert client.get(f"/api/v1/staff/{staff_id}", headers=manager).json()["email"] == "delete.me@sitneat.com"
    assert client.get(f"/api/v1/staff/{staff_id}", headers=owner).status_code == 403
    assert client.delete(f"/api/v1/staff/{staff_id}", headers=manager).status_code == 204
    assert client.get(f"/api/v1/staff/{staff_id}", headers=manager).status_code == 404


def test_demo_accounts_can_log_in(client: TestClient):
    _customer, customer = login(client, DEMO_CUSTOMER_EMAIL, DEMO_CUSTOMER_PASSWORD)
    _staff, staff = login(client, DEMO_STAFF_EMAIL, DEMO_STAFF_PASSWORD)
    _manager, manager = login(client, DEMO_MANAGER_EMAIL, DEMO_MANAGER_PASSWORD)
    assert customer["role"] == "customer"
    assert staff["role"] == "staff"
    assert manager["role"] == "manager"
