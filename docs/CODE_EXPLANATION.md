# SitNeat code explanation

This document explains the code that is running in the project. It is written so I can walk a faculty member through the application: what each file is for, how a request moves through the system, and where the security and booking rules live.

The product documents in this folder are the plan. `PRD.md` says what the product should do. `SRS.md` says the required behavior. `TDD.md` says how I planned to build it, including PostgreSQL. This file explains the implementation. The running app uses SQLite instead of PostgreSQL, and it does not use Alembic migrations. I should say that clearly if I am asked.

## The one-minute explanation

SitNeat is a seat reservation system for one restaurant. A customer registers, logs in, searches for a free seat, and books a time. The customer also chooses vegetarian or non-vegetarian food and declares any allergies. Staff see today’s bookings and move them from confirmed to seated to completed. The manager manages seats, staff accounts, opening hours, and a simple summary.

The browser is a React application written in TypeScript. It talks to a FastAPI backend through JSON REST calls under `/api/v1`. SQLite stores the data. A logged-in user sends a JWT access token. The backend decides what that user may do from the role stored in the database. The React pages hide buttons for a nicer screen, but the backend is the real security check.

## How one booking travels through the code

1. The customer opens `/book`. `RequireAuth` in `frontend/src/auth.tsx` allows only a customer. Anyone else is sent to login or to `/unauthorized`.
2. `BookPage` loads restaurant settings from `GET /api/v1/settings`, then asks `GET /api/v1/seats/availability` for seats that fit the date, time, and party size.
3. `frontend/src/api.ts` adds `Authorization: Bearer <token>` and calls the API.
4. Vite, while I am developing, forwards `/api` to the FastAPI process on port 8000. On Vercel, `vercel.json` sends `/api` to the backend service.
5. `backend/main.py` receives the request, gives it a request id, and passes it to the seats router.
6. `get_current_user` in `backend/app/deps.py` checks the token, loads the user, and checks that the user’s role includes the scope `seats:read`.
7. `search_availability` in `backend/app/services.py` checks opening hours, lead time, and party size, then removes seats that already have an overlapping confirmed or seated booking.
8. When the customer submits the form, `POST /api/v1/reservations` runs the same checks again and saves a confirmed reservation. The customer does not send the end time. The backend adds the configured duration, which is 90 minutes by default.
9. The page shows the saved booking. Staff later see it on `/today`.

If I am asked “where is the business rule?”, the answer is `backend/app/services.py`. Routers only receive HTTP and call services. React only displays the result.

## Repository map

| Path | What it is |
| --- | --- |
| `frontend/` | React + TypeScript screens |
| `backend/` | FastAPI application |
| `backend/app/` | Application code: models, rules, routes, security |
| `backend/tests/` | Automated API tests |
| `docs/` | Faculty documents and this explanation |
| `vercel.json` | How Vercel serves the site and the API together |
| `.env.example` | Example settings. Real secrets stay out of git |

## Backend startup

### `backend/main.py`

This file builds the FastAPI application. `create_app()` is the factory. The line `app = create_app()` at the bottom is what Vercel and `fastapi dev` both load (`main:app`).

On startup it:

- Loads settings.
- Refuses to start in production if `SECRET_KEY` is missing or still the example value.
- Creates the SQLite engine, creates tables, and seeds restaurant settings.
- Adds CORS so the local Vite site on port 5173 can call the API. On Vercel it also allows the deployed site address.
- Adds a request-id middleware. Every response gets an `X-Request-Id`. Unexpected errors are logged with that id. The client receives a generic message, not a stack trace or a secret.
- Registers three error shapes. `AppError` becomes `{code, message, details?}`. A bad request body becomes HTTP 422 with the same shape. Any other exception becomes HTTP 500 with `SERVER_ERROR`.
- Mounts the routers under `/api/v1`.
- Exposes `GET /api/health` and `GET /api/v1/health`.
- If I run the backend on my own machine and `frontend/dist` exists, it can also serve the built site. On Vercel that mount is skipped because the React app is a separate service.

### `backend/app/config.py`

`Settings` holds the environment: `APP_ENV`, `SECRET_KEY`, `DATABASE_URL`, token lifetime, the frontend origin, and whether demo data should be seeded.

`load_env_file()` reads a `.env` file from the current folder, `backend/`, or the repository root. A variable already set in the shell wins over the file.

`load_settings()` is what the running app uses. On a Vercel preview or production deployment, two defaults change:

- `APP_ENV` becomes `production` when it was not set.
- A relative SQLite file such as `sqlite:///./sitneat.db` is replaced by `sqlite:////tmp/sitneat.db`, because the deployment directory is not a safe place to write. Local development still uses `backend/sitneat.db`.

`allowed_origins()` builds the CORS list from the configured frontend origin, localhost, and the Vercel host names when those exist.

### `backend/app/database.py`

`make_engine()` opens SQLAlchemy. For SQLite it does three extra things on every connection:

- `PRAGMA foreign_keys=ON`, so a reservation cannot point at a missing user or seat.
- `isolation_level = None`, so SQLAlchemy controls the transaction.
- `BEGIN IMMEDIATE` at the start of a transaction. That takes the write lock before the overlap check, so two customers cannot both pass the “seat is free” test and then both insert.

`create_tables()` runs `SQLModel.metadata.create_all`. There is no migration history. The tables are created from the models the first time the app starts.

### `backend/app/timeutil.py`

The database stores timezone-aware UTC datetimes. The restaurant thinks in `Asia/Dhaka` by default.

- `utc_now()` is the current time in UTC.
- `to_utc()` converts any aware datetime to UTC.
- `local_datetime()` builds a restaurant-local datetime from a calendar date and a clock time.
- `day_bounds_utc()` returns the UTC start and end of one restaurant-local day. The staff “today” list and the manager summary use this so midnight in Dhaka is the boundary, not midnight UTC.

### `backend/app/seed.py`

`seed_database()` always makes sure one `restaurant_settings` row exists: open 11:00, close 22:00, duration 90 minutes, slots every 30 minutes, book at least 60 minutes ahead, book up to 30 days ahead, and customers can change a booking until 120 minutes before it starts. Time zone is `Asia/Dhaka`.

If `SEED_DEMO` is true and the users table is empty, it also creates three accounts and four seats, then tries to place one demo reservation on the first legal slot:

| Role | Name | Email | Password |
| --- | --- | --- | --- |
| Manager | Nadia Karim | manager@sitneat.com | Manager123! |
| Staff | Rahim Uddin | staff@sitneat.com | Staff123! |
| Customer | Maya Chowdhury | customer@sitneat.com | Customer123! |

Seats are A1 (2 guests), A2 (4), B1 (6), and B2 (4). These accounts are for testing. The website does not display them.

## Data model — `backend/app/models.py`

SQLModel classes are both the Python objects and the SQLite tables. Check constraints in the database repeat the important rules so a bad row cannot be inserted even if a service forgets a check.

`Role`: `customer`, `staff`, `manager`.

`ReservationStatus`: `confirmed`, `seated`, `completed`, `cancelled`.

`FoodPreference`: `vegetarian`, `non_vegetarian`.

`AllergyDeclaration`: `none` or `specified`.

`User` (`users`): id, full name, unique email, password hash, role, active flag, timestamps. The password column stores an Argon2 hash, never the password.

`Seat` (`seats`): unique seat number, capacity from 1 to 20, optional description, active flag, timestamps. An inactive seat cannot be booked.

`Reservation` (`reservations`): customer id, seat id, start, end, party size from 1 to 20, food preference, allergy declaration, optional allergy details, status, timestamps. `end_at` must be after `start_at`. Foreign keys point at `users` and `seats`.

`RestaurantSettings` (`restaurant_settings`): one row, id 1, holding hours and booking rules.

`AuditLog` (`audit_logs`): who did an action, the action name, the target type, and the target id. It records seat changes, staff changes, settings changes, staff cancellations, and status changes. It does not store allergy text.

## Request and response shapes — `backend/app/schemas.py`

Pydantic models describe JSON in and JSON out. Database rows are not returned directly. `UserPublic` has no password hash.

Important validation:

- Names are trimmed. Emails are lowercased.
- `RegisterRequest` may contain a role field, but the register route ignores it.
- `ReservationBody` requires allergy details when the declaration is `specified`, caps them at 300 characters, and stores `null` when the declaration is `none`.
- `StaffCreate` rejects any role other than staff. The service then forces the role to staff anyway.
- `StaffUpdate` can change the name, the active flag, and the password. It has no email field and no role field, so a staff account cannot be turned into a manager from this API.
- `SettingsUpdate` allows slot intervals of 15, 30, or 60 minutes. Closing must be after opening. The open window must fit one reservation. Duration must be a multiple of the slot interval. The time zone must be a real `ZoneInfo` name.

## Errors — `backend/app/errors.py`

`AppError` is the application’s own exception. It carries an HTTP status, a stable `code` such as `SEAT_UNAVAILABLE`, a human message, and optional field details. Services raise it. `main.py` turns it into JSON. The frontend shows the message.

## Security

### `backend/app/security.py`

Passwords are hashed with Argon2id through `pwdlib`. `verify_password()` returns false on a bad password or a broken hash. It does not say which one failed.

Scopes are the named permissions. They are derived from the role in the database. They are not stored in the token, and the client cannot submit them.

| Role | Scopes |
| --- | --- |
| Customer | `seats:read`, `settings:read`, `reservations:create:own`, `reservations:read:own`, `reservations:update:own`, `reservations:cancel:own` |
| Staff | `seats:read`, `settings:read`, `reservations:read:operational`, `reservations:update:operational`, `reservations:cancel:operational` |
| Manager | Every staff scope, plus `seats:manage`, `settings:manage`, `reservations:read:all`, `staff:manage`, `reports:read` |

`create_access_token()` builds an HS256 JWT. The payload is only `sub` (the user id), `iat`, and `exp`. The default lifetime is 120 minutes. `decode_access_token()` requires `sub` and `exp` and accepts only HS256.

### `backend/app/deps.py`

This is the gate on every protected route.

`get_session()` opens a SQLModel session for one request and closes it afterwards.

`get_current_user()` reads the bearer token. Missing, invalid, or expired tokens become HTTP 401. An unknown or inactive user is also 401, with the same kind of message. It then loads scopes from `SCOPES[user.role]`. If the route required a scope the role does not have, the response is HTTP 403. A customer who calls a manager route fails here even if the React page was bypassed.

`require_any()` is for routes where more than one scope is legal. Reading one reservation allows own, operational, or all. Cancelling allows own or operational. The service still checks ownership after the scope check.

The sentence I use in a viva: the token proves who the user is. The database role decides what they may do. The service decides whether this particular row belongs to them.

## Routes

All of these are under `/api/v1` except the extra health check at `/api/health`.

### `backend/app/routers/auth.py`

- `POST /auth/register` creates a customer. A role in the body is ignored. A duplicate email is HTTP 409 `EMAIL_TAKEN`.
- `POST /auth/login` checks the email, that the user is active, and the password. Failure is always `Invalid email or password.` so the API does not reveal whether the email exists.
- `GET /auth/me` returns the current profile. Any logged-in role can call it.

### `backend/app/routers/seats.py`

- `GET /seats` lists seats. Customers and staff see active seats. A manager can pass `include_inactive=true` to see deactivated seats too.
- `GET /seats/availability` searches free seats. The query names are `date` and `start_time`. The Python parameter is not named `date`, because that name would hide Python’s `date` type.
- `POST /seats` and `PATCH /seats/{id}` are manager-only (`seats:manage`).

Availability is a snapshot. Creating the booking checks again.

### `backend/app/routers/reservations.py`

Literal paths are registered before `/{reservation_id}`, so `/mine` and `/today` are not treated as ids.

| Method and path | Who | What it does |
| --- | --- | --- |
| `POST /reservations` | Customer | Creates a confirmed booking |
| `GET /reservations/mine` | Customer | Lists only that customer’s rows |
| `GET /reservations/today` | Staff and manager | Today’s confirmed and seated bookings, in restaurant time |
| `GET /reservations` | Manager | All bookings, optional date and status filters |
| `GET /reservations/{id}` | Customer, staff, or manager | One booking. A customer who does not own it gets 404 |
| `PATCH /reservations/{id}` | Customer | Edits their own confirmed booking before the cutoff |
| `POST /reservations/{id}/cancel` | Customer, staff, or manager | Cancels a confirmed booking |
| `PATCH /reservations/{id}/status` | Staff and manager | Moves confirmed → seated, or seated → completed |

### `backend/app/routers/staff.py`

Manager only. List staff, create a staff account, and update a staff account. Looking up a manager id returns 404 `Staff account not found.` The screen cannot create or edit managers.

### `backend/app/routers/settings.py`

`GET /settings` is any logged-in user (`settings:read`), because the booking page needs the hours and slot list. `PUT /settings` is the manager (`settings:manage`). New rules apply to later bookings. Existing rows keep the start and end already saved.

### `backend/app/routers/reports.py`

`GET /reports/summary?date_from=&date_to=` is manager-only. It returns counts by status. It does not return names, emails, or allergy details.

## Booking rules — `backend/app/services.py`

This is the largest file because it holds the rules. Routers stay thin.

`validate_slot()` turns a date and a clock time into a UTC start and end:

- The start must fall on a slot boundary after opening.
- The booking must finish by closing. End time is start plus `duration_minutes`.
- The start must be at least `min_lead_minutes` in the future.
- The date must be within `advance_days`.
- Failures use codes `INVALID_SLOT`, `OUTSIDE_HOURS`, `LEAD_TIME`, and `TOO_FAR_AHEAD`.

`_require_bookable()` rejects an inactive seat (`SEAT_INACTIVE`) and a party bigger than the seat (`PARTY_TOO_LARGE`).

`ensure_free()` looks for another reservation on the same seat whose status is confirmed or seated and whose time overlaps. Overlap is half-open: `start < other_end` and `end > other_start`. A booking that ends at 19:30 does not block one that starts at 19:30. Completed and cancelled rows do not block. A conflict is HTTP 409 `SEAT_UNAVAILABLE`. When a customer edits a booking, their own row is excluded from this check so they can keep the same seat.

`create_reservation()` sets `customer_id` from the logged-in user. A customer id in the JSON body is not a field on `ReservationBody`, so it cannot be used to book for someone else. Status is always `confirmed`. There is no pending state.

`update_own_reservation()` allows the change only when the row belongs to the customer, the status is still confirmed, and the current time is before start minus `change_cutoff_minutes`. After the cutoff the code is `CUTOFF_PASSED`.

`cancel_reservation()`:

- A customer can cancel only their own confirmed booking, and only before the cutoff. Someone else’s id returns 404, not 403, so the API does not confirm that the other booking exists.
- Staff and the manager can cancel a confirmed booking. They cannot cancel a seated booking.
- Completed and cancelled bookings stay as they are.

`update_status()` follows `STATUS_FLOW`: confirmed can become seated, and seated can become completed. Sending `cancelled` here is rejected. The cancel route is the only way to cancel. Staff actions are written to the audit log.

`list_own()` filters by `customer_id == current user`. `list_today()` uses the restaurant’s local day and only blocking statuses. `summary()` counts statuses in a date range and returns no personal fields.

`create_staff()` always saves `role=staff`. `update_staff()` edits a row only when its role is already staff.

`_commit()` turns a database integrity error into HTTP 409 `CONFLICT` instead of a 500.

## Frontend

### `frontend/src/main.tsx`

This is the browser entry. It renders `App` inside `BrowserRouter` and `AuthProvider`. The router uses normal paths such as `/book`, so a refresh needs the server to return `index.html`. The Vite dev server does that. `vercel.json` does it for the deployed site.

### `frontend/src/App.tsx`

The route table:

| Path | Who sees it |
| --- | --- |
| `/` | Landing page, or a redirect to that role’s home |
| `/login`, `/register` | Public |
| `/book`, `/reservations` | Customer |
| `/today` | Staff. The manager is not given this route; the manager uses `/manage` |
| `/manage` | Manager |
| `/profile` | Any logged-in user |
| `/unauthorized` | Signed in, wrong role |
| anything else | Page not found |

`homePath()` sends staff to `/today`, the manager to `/manage`, and a customer to `/book`.

### `frontend/src/auth.tsx`

`AuthProvider` keeps the token and the user in React state and in `sessionStorage` under `sitneat_token` and `sitneat_user`. Session storage clears when the browser tab is closed. It is not `localStorage`.

On load, if a token exists, the app calls `GET /auth/me`. If that fails, the saved login is cleared. A 401 from any later call does the same through `setUnauthorizedHandler`.

`login()` posts the email and password, then stores the token and user. `logout()` clears them.

`RequireAuth` is a screen guard only. It is not the security boundary. The API checks the token again.

### `frontend/src/api.ts`

`api()` calls `VITE_API_BASE` or, by default, `/api/v1`. It sends JSON and the bearer token. Failures become `ApiError` with the backend `code`, `message`, and field details. `errorText()` turns that into the sentence shown on the form.

### `frontend/src/types.ts`

These TypeScript types mirror the API: roles, statuses, users, seats, reservations, settings, the summary, and the login result. They keep the pages from guessing the JSON shape.

### `frontend/src/format.ts`

Display helpers. `formatWhen()` prints a UTC timestamp in the restaurant time zone. `timeSlots()` builds the dropdown from opening, closing, duration, and slot interval. `canCustomerChange()` mirrors the cutoff so the Change and Cancel buttons can hide after it. The backend still enforces the cutoff if the button is forced.

`ALLERGY_NOTICE` tells the customer that an allergy note is their declaration and does not guarantee allergen-free food.

### `frontend/src/vite-env.d.ts`

Tells TypeScript that `import.meta.env.VITE_API_BASE` may exist.

### `frontend/vite.config.ts`

During `npm run dev`, requests to `/api` are proxied to `http://localhost:8000`. The production build is a static site. It has no proxy. The host must route `/api` to FastAPI, which `vercel.json` does.

### Pages

`LandingPage.tsx` explains the three roles and links to register and login. It does not list demo accounts.

`LoginPage.tsx` is an email and password form. Success navigates to that role’s home.

`RegisterPage.tsx` collects name, email, and password and posts `/auth/register`. The new account is a customer.

`BookPage.tsx` loads settings, lets the customer pick a date, slot, and party size, then lists seats returned by the availability API. The customer picks a seat, a food preference, and an allergy declaration. If they choose “specified”, the details box is required. Submit calls `POST /reservations` and shows the confirmation, including the end time the server calculated.

`ReservationsPage.tsx` loads `/reservations/mine`. For a confirmed booking that is still before the cutoff, the customer can change the same fields or cancel. The page sends the edit to `PATCH /reservations/{id}`.

`StaffPage.tsx` loads `/reservations/today` and renders `ReservationTable` with `StatusActions`.

`ManagerPage.tsx` is one page with five panels:

- Bookings: filter all reservations and use the same status actions.
- Seats: create and edit seat number, capacity, description, and active flag.
- Staff: create a staff user, rename them, reset their password, or deactivate them.
- Hours and rules: edit the settings row.
- Summary: counts for a date range from `/reports/summary`.

`ProfilePage.tsx` shows the name, email, and role from `/auth/me`. There is no form to change the role.

### Components

`Layout.tsx` is the header. The links depend on the role. Log out clears the session.

`ReservationTable.tsx` renders the shared table: when, seat, party, customer, food, allergy, and status. An optional action column is where staff buttons go.

`StatusActions.tsx` shows Mark seated, Mark completed, or Cancel according to the current status. Cancel asks for a second click. The component calls the status and cancel endpoints. If the backend rejects the transition, the error is shown.

### `frontend/src/index.css`

This is only appearance: a warm page, a dark green header, cards, forms, and the reservation table. It does not contain booking rules.

## Tests — `backend/tests/`

`pytest.ini` puts the backend folder on the Python path and collects `tests/`.

`test_api.py` builds a temporary SQLite file and a `TestClient` for each test, with `raise_server_exceptions=False` so the HTTP 500 handler can be checked. The tests use a long test secret.

| Test | What I can say it proves |
| --- | --- |
| `test_health` | The health route responds |
| `test_t01_register_ignores_requested_role` | Public signup stays a customer even if the body asks to be a manager |
| `test_t02_bad_password_and_inactive_account_are_rejected` | Wrong password and inactive user get the same generic login error |
| `test_t03_missing_token_is_rejected` | A protected route without a token is 401 |
| `test_t04_customer_cannot_read_another_customers_booking` | Another customer’s reservation is 404 |
| `test_t05_customer_cannot_manage_seats_or_staff` | A customer receives 403 on manager routes |
| `test_t06_party_larger_than_capacity_is_rejected` | Party size cannot exceed the seat |
| `test_t07_inactive_seat_cannot_be_booked` | Inactive seats are rejected |
| `test_t08_overlapping_booking_conflicts_and_exact_end_does_not` | Overlap is 409, and a booking that starts when another ends is allowed |
| `test_t09_allergy_details_are_required_when_specified` | “Specified” without details is 422, and “none” stores no details |
| `test_t10_customer_cannot_change_after_cutoff` | Late edits and cancels are rejected |
| `test_t11_illegal_status_transition_is_rejected` | Skipping seated, or cancelling through the status route, is rejected |
| `test_t12_staff_cannot_change_settings` | Staff cannot `PUT /settings` |
| `test_t13_manager_settings_apply_to_future_bookings_only` | A saved booking keeps its old end time after the duration setting changes |
| `test_t14_unexpected_error_does_not_leak_secrets` | A 500 body has no traceback and no secret |
| `test_cancelled_booking_releases_the_seat` | After cancel, the same seat and time can be booked |
| `test_staff_can_cancel_for_a_guest_and_customer_cannot_list_today` | Staff cancel works, and a customer cannot open the today list |
| `test_today_list_and_summary` | Today’s list and the manager summary behave, and staff cannot read the summary |
| `test_customer_edit_and_server_owned_fields` | The customer can edit, and cannot set status, end time, or another customer id |
| `test_demo_accounts_can_log_in` | The three seeded accounts authenticate |

`test_config.py` checks the Vercel database path, the production secret refusal, and the extra CORS origins. `conftest.py` is only a note. The client fixture lives in `test_api.py`.

## Deployment files

`vercel.json` defines two services. `backend` is FastAPI with entry `main:app`. `frontend` is the Vite build. A request whose path starts with `/api` goes to FastAPI and keeps that path, so `/api/v1/auth/login` still matches the routers. Every other path goes to the frontend, and unknown paths inside the frontend fall back to `index.html` so React Router can open `/book` after a refresh.

`backend/.python-version` asks Vercel to use Python 3.12. `frontend/package.json` asks for Node 22.

`backend/requirements.txt` is what the backend install uses: FastAPI, SQLModel, PyJWT, pwdlib with Argon2, email validation, time-zone data, pytest, and httpx.

On Vercel, SQLite in `/tmp` is wiped when a new instance starts. Demo accounts are created again if the database is empty and `SEED_DEMO` is true. I should describe that as suitable for a demonstration. A hosted database is required if bookings must last.

## What I should say if the design document is compared with the code

- The TDD names PostgreSQL, SQLAlchemy, Alembic, and an exclusion constraint. The code uses SQLite, SQLModel, `create_all`, and an overlap query inside a `BEGIN IMMEDIATE` transaction. The half-open overlap rule is the same idea. The database product is different because the project was built to stay simple.
- The TDD mentions frontend tests with Vitest. The automated tests in the repository are the backend pytest suite.
- The token is a bearer JWT in `sessionStorage`. It is not an HttpOnly cookie. Closing the tab drops it. The backend still checks every request.
- There is one restaurant and one settings row. There are no payments, no menu ordering, and no medical allergy guarantee.
- Public registration cannot create staff or managers. Only the manager can create staff, and that flow cannot create another manager.

## A short speaking order

If I have a few minutes, I explain in this order:

1. Three roles and what each screen is for.
2. React calls `/api/v1`, and FastAPI is the security boundary.
3. Register ignores role. Login returns a JWT that contains only the user id and expiry.
4. Scopes come from the database role. Show one customer route and one manager route.
5. A booking: the client sends seat, date, start, party, food, and allergy. The server calculates the end, checks hours, and rejects an overlap.
6. Status flow: confirmed, seated, completed, and cancel only from confirmed.
7. A customer asking for another customer’s reservation gets 404.
8. Tests in `backend/tests/test_api.py` lock those rules in.
