# Final Project Submission Report

**Name:** MAKSUDUL KABIR VUBON
**IUB ID:** 2220229
**Section:** 6
**Team:** Individual
**Project:** SitNeat — restaurant seat reservations
**GitHub:** https://github.com/2220229-art/2220229-S06-SeatNEat
**Submitted to:** Sayef Reyadh
**Term:** CSE309 Autumn 2026

The live mid-term site is https://2220229-s06-seatneat.vercel.app. The security and admin work in this report is implemented in the local project. It was not deployed again for this step.

## How to use this report

This file describes the finished SitNeat application. Passwords are not written here. They go only in the course form and in the PDF appendix.

Screenshots S1–S21 are listed in Part D. Take them from the running app and paste them into the PDF. This markdown file does not contain those images.

## Table of Contents

1. Executive Summary
2. Part A. Product Requirements (PRD)
3. Part B. Software Requirements (SRS)
4. Part C. Technical Design (TDD)
5. Part D. Evidence
6. Part E. Project Management and Conclusion

## 1. Executive Summary

### 1.1 Project overview

SitNeat is a seat reservation system for one restaurant. A guest creates an account, checks which tables are free, and books a seat with a food preference and an allergy note. Staff see the day’s bookings and move them from confirmed to seated or completed. A manager looks after seats, staff accounts, opening hours, and booking rules.

The final version adds the security the course asked for on top of that restaurant workflow. Each account is a `user` or an `admin`. Login uses a short access token and a refresh token stored in an httpOnly cookie. People can update their name, change their password, and revoke a session. A shared dining group has an owner and members with different permissions. Admins have a separate dashboard for users, bookings, groups, the audit log, failed logins, and CSV export.

### 1.2 What was built since the mid assessment

The mid assessment already had registration, login, seat booking, staff status updates, and the manager screens. Since then the project adds:

- A password pepper from the environment, and Argon2id hashes.
- An access token of at most 15 minutes that carries the user id and the account role (`user` or `admin`).
- Refresh tokens stored only as a hash, rotated on each refresh, and revoked on logout or reuse.
- Profile update, password change that requires the current password, and a session list.
- A lockout after five failed logins.
- Ban and unban. A banned person is rejected on the next request. An admin cannot ban another admin or change their own role.
- One permission module, `backend/app/access.py`, used by the admin and group routes.
- The dining group **Window party**, where the owner, a member who can update and assign, and a member who can only create do not have the same rights.
- An admin dashboard with overview counts, user search, moderation, the activity log, a security view, and CSV downloads.
- Tests for login, rejected tokens, and the role rules.

### 1.3 Live links

| Item | Link |
| --- | --- |
| GitHub repository | https://github.com/2220229-art/2220229-S06-SeatNEat |
| Planning issue | https://github.com/2220229-art/2220229-S06-SeatNEat/issues/1 |
| Documentation pull request | https://github.com/2220229-art/2220229-S06-SeatNEat/pull/2 |
| Mid-term site | https://2220229-s06-seatneat.vercel.app |

The final security features are ready to deploy with the existing Vercel project and the Neon database. They were left undeployed on purpose for this step, so the public site may still be the mid-term build.

## Part A. Product Requirements (PRD)

### A1. Problem Statement

A small restaurant needs one place to take seat bookings and to see who is coming. Guests should only see their own bookings. Staff should handle today’s floor. The manager should control the room. The same system must also keep accounts safe: short login sessions, a way to sign out a device, and an admin who can ban an account or inspect what happened.

### A2. Users and Roles

SitNeat keeps two ideas separate.

The **account role** is `user` or `admin`. This is the role inside the access token. Admins open the admin dashboard. Users do not.

The **restaurant job** is customer, staff, or manager. It decides the booking screens. A customer books a seat. Staff update today’s visits. A manager runs the restaurant screens. In the demo data both admins are managers, and the other three accounts are users.

A **dining group** is a shared party. The owner can rename it, delete it, and manage members. A member may be allowed to create a booking, update one, or assign a seat. Those three permissions are independent.

### A3. Goals and Success Measures

- A guest can register, log in, and book only for themselves.
- A wrong, missing, expired, or edited token is rejected.
- Logging out invalidates the refresh session.
- Five bad passwords lock the account for 15 minutes.
- A member cannot do a group action they were not given.
- An admin can see users, bookings, groups, and the audit log, and can export them.
- An admin cannot ban another admin or change their own role.

### A4. Scope and Non-Goals

In scope: one restaurant, the booking rules from the mid assessment, account security, groups, and the admin dashboard.

Out of scope: payments, email or SMS notifications, more than one restaurant, a native mobile app, and a public marketing site.

### A5. User Stories

- As a guest, I register and log in so that I can book a seat.
- As a guest, I change my name and password so that my account stays mine.
- As a guest, I revoke a session so that a lost device cannot keep using my account.
- As a group owner, I choose what each member can do so that a shared booking is not open to everyone.
- As a member without create permission, I am stopped if I try to book for the group.
- As an admin, I search users, ban a normal account with a reason, and read the activity log.
- As an admin, I cannot ban the other admin.

## Part B. Software Requirements (SRS)

### B1. Introduction

The requirements below describe the finished SitNeat API and the React screens that call it. The restaurant rules from the mid assessment still apply: Asia/Dhaka by default, a confirmed booking blocks the seat until it ends, and a customer can change their own confirmed booking only before the cutoff.

### B2. Functional Requirements

| ID | Requirement |
| --- | --- |
| FR-1 | Public signup creates an active customer with account role `user`. A submitted role is ignored. |
| FR-2 | Login checks the email and password and returns the same error when the email is unknown or the password is wrong. |
| FR-3 | After five failures the account is locked for 15 minutes. |
| FR-4 | The access token lasts at most 15 minutes and includes the user id and account role. |
| FR-5 | A refresh token is stored as a hash and sent to the browser as an httpOnly cookie. Refresh rotates it. Logout revokes it. Reuse of an old refresh token revokes every session for that account. |
| FR-6 | A person can update their name and can change their password only when the current password is correct and the new password is different. |
| FR-7 | A person can list their sessions and revoke one. |
| FR-8 | A missing, expired, or tampered access token returns 401. A banned or inactive account is rejected on the next request. |
| FR-9 | A normal user receives 403 on admin routes. |
| FR-10 | Only the group owner can rename the group, delete it, or add, change, and remove members. |
| FR-11 | A group booking requires the matching permission: create, update, or assign. |
| FR-12 | An admin sees overview counts, a filterable user list, user detail, ban and unban, role change, session revoke, bulk ban and unban, reservation and group moderation, the audit log, failed-login totals, and CSV export. |
| FR-13 | An admin cannot change their own role and cannot ban another admin. |

### B3. Non-Functional Requirements

- Passwords are hashed with Argon2id plus a server pepper. The pepper is not stored in the database.
- The API returns a code and a message. It does not return a stack trace.
- CORS allows the configured frontend origin, not every origin.
- Secrets live in the environment. `.env.example` has names only.
- The audit log stores the action, actor, IP address, browser, and time for login, failed login, logout, password change, role change, ban, delete, and export.

### B4. Roles and Permission Matrix

| Action | User (customer) | User (staff) | Admin |
| --- | --- | --- | --- |
| Book own seat | Yes | No | Through the manager screens |
| See own bookings | Yes | No | Yes, all bookings |
| Update today’s status | No | Yes | Yes |
| Manage seats, staff, hours | No | No | Yes |
| Open admin dashboard | No | No | Yes |
| Rename or delete a group | Only if owner | Only if owner | Moderation delete |
| Create a group booking | Only if owner or `can_create` | Only if owner or `can_create` | Only with that permission |

In the demo group, the customer is the owner, the staff member can update and assign, and the second guest can create.

### B5. Use Cases

1. Maya registers or logs in, checks free seats, and confirms a booking.
2. Maya opens her profile, changes her name, and is rejected when the current password is wrong.
3. Rahim opens Window party and is rejected when he tries to rename it.
4. Nadia opens Admin, searches for a user, and bans that user with a reason. The user’s next request fails.
5. Nadia tries to ban Arafat and the server refuses.

### B6. Acceptance Criteria

- `pytest` covers login, a tampered token, admin access, group rename, group create permission, the ban rule, the own-role rule, lockout, and password change.
- The React app shows Groups to every signed-in person and Admin only to an admin.
- The README lists the five demo emails and roles and does not list passwords.

### B7. Traceability Matrix

| Requirement | Code | Test |
| --- | --- | --- |
| FR-4, FR-8 | `backend/app/security.py`, `backend/app/deps.py` | `test_login_token_contains_user_id_and_role`, `test_missing_and_tampered_tokens_are_rejected` |
| FR-9, FR-13 | `backend/app/access.py`, `backend/app/routers/admin.py` | `test_customer_cannot_open_admin_overview`, `test_admin_cannot_ban_another_admin`, `test_admin_cannot_change_own_role` |
| FR-10, FR-11 | `backend/app/routers/groups.py` | `test_only_the_owner_can_rename_a_group`, `test_member_without_create_permission_cannot_book_for_the_group` |
| FR-3, FR-6, FR-8 | `backend/app/routers/auth.py` | `test_wrong_password_locks_the_account`, `test_password_change_requires_the_current_password`, `test_banned_user_is_rejected_on_the_next_request` |

## Part C. Technical Design (TDD)

### C1. Technology Stack

- Frontend: React 19, TypeScript, Vite.
- Backend: FastAPI, SQLModel, Pydantic.
- Passwords: pwdlib with Argon2id.
- Tokens: PyJWT, HS256.
- Database: SQLite locally, PostgreSQL on Neon when `DATABASE_URL` is set.
- Tests: pytest and FastAPI’s test client.

### C2. System Architecture

The browser talks to `/api/v1`. Vite proxies that path to FastAPI on port 8000 during development. The access token is sent as `Authorization: Bearer`. The refresh token is a cookie named `sitneat_refresh` with `HttpOnly` and `SameSite=Lax`. The cookie path is `/api`, so it is sent only to the API.

`backend/app/access.py` is the shared permission module. Route files call `require_admin`, `require_owner`, or `require_group_permission` instead of copying those checks.

### C3. Backend and Frontend Structure

Backend routes live in `backend/app/routers/`. Auth, groups, and admin are the final additions. Restaurant booking stays in the seats, reservations, staff, settings, and reports routers.

The React pages are `ProfilePage` (name, password, sessions), `GroupsPage`, and `AdminPage`. `auth.tsx` keeps the screen on “Loading…” until `/auth/me` or `/auth/refresh` finishes, so a returning visitor does not briefly see the guest menu.

### C4. Data Model

Existing tables: `users`, `seats`, `reservations`, `restaurant_settings`, `audit_logs`.

New or extended fields:

- `users.account_role` is `user` or `admin`.
- `users.failed_attempts`, `locked_until`, `banned_at`, and `ban_reason` support lockout and bans.
- `refresh_sessions` stores the SHA-256 hash of the refresh token, expiry, revocation time, IP, and browser.
- `dining_groups` has a name and an owner.
- `group_members` stores `can_create`, `can_update`, and `can_assign`.
- `reservations.group_id` is optional.
- `audit_logs` stores IP address, browser, and a short detail. The actor can be empty when the email is unknown.

### C5. API Design

Auth: `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me`, `PATCH /auth/profile`, `POST /auth/password`, `GET /auth/sessions`, `DELETE /auth/sessions/{id}`.

Groups: list, create, read, rename, delete, member add, member update, member remove, group booking, party-size update, and seat assign.

Admin: `/admin/overview`, `/admin/users`, `/admin/users/{id}`, ban, unban, role, revoke sessions, bulk ban, bulk unban, `/admin/records`, `/admin/groups`, `/admin/activity`, `/admin/security`, and three CSV exports.

Restaurant routes from the mid assessment are unchanged in purpose.

### C6. JWT Authentication Design

`create_access_token` puts `sub`, `role`, `iat`, and `exp` in an HS256 token. The lifetime is capped at 15 minutes even if the environment asks for longer. `decode_access_token` rejects a token that is signed with another secret, is expired, or has no role.

The refresh token is a random string. Only its SHA-256 hash is stored. Login sets the cookie. Refresh revokes the presented row and issues a new one. If a revoked refresh token is presented again, every session for that user is revoked. Logout revokes the current refresh row and clears the cookie.

The React client retries a 401 once by calling `/auth/refresh`. If that fails, it clears the local session and sends the person to log in.

### C7. RBAC Design

`account_role_of` and `require_admin` live in `backend/app/access.py`. Group checks live in the same file: the owner may do everything in the group; a member may do only the flags that are true; everyone else receives 403, or 404 when the group is not visible to them.

Restaurant scopes in `security.py` still protect seat management, staff management, and booking lists. A customer still cannot open another person’s reservation.

### C8. Admin Dashboard Design

The Admin page has Overview, Users, Records, Activity, and Security.

Overview shows users, banned accounts, reservations, groups, and how many users and bookings were created in the last seven days.

Users supports search, role filter, status filter, a detail panel (counts, sessions, recent activity), ban with a reason, unban, role change, session revoke, and bulk ban or unban. Admins are skipped by bulk ban.

Records lists reservations and groups and can delete them. Activity can be filtered by action and search text. Security groups failed logins by IP and by account. Each list can be downloaded as CSV, and the download is written to the audit log.

### C9. Security Design and Threats

| Threat | What SitNeat does |
| --- | --- |
| Stolen password database | Argon2id plus a pepper that is not in the database |
| Guessing passwords | Same login error for unknown email and bad password, then a 15-minute lock |
| Stolen access token | Token expires within 15 minutes |
| Stolen refresh cookie from script | Cookie is httpOnly |
| Replayed refresh token | Rotation, and reuse revokes all sessions |
| Banned person keeps calling the API | `get_current_user` rejects `banned_at` or an inactive account |
| Admin attacking another admin | Ban and own-role change return 403 |
| Extra origins calling the API | CORS list is the frontend origin plus local development |

### C10. Deployment on Vercel

`vercel.json` already builds the Vite app and the FastAPI app as two services. `/api` is rewritten to FastAPI. Other paths go to the React app. Production should set `DATABASE_URL` to the Neon pooled URL, `SECRET_KEY`, `PASSWORD_PEPPER`, `APP_ENV=production`, and `SEED_DEMO`. `VITE_API_BASE` stays unset.

This report does not claim a new production deploy. The URL above is the site from the earlier deployment. A later deploy is required before the public site shows the admin and group screens.

### C11. Testing

From `backend`, with the virtual environment active, run `pytest`. The suite uses a fresh SQLite file per test. `tests/test_final_security.py` covers the final rules. The older `tests/test_api.py` still covers booking, seats, and staff.

## Part D. Evidence: Screenshots of the Running Application

Paste these into the PDF after you capture them locally at http://localhost:5173 or, after a later deploy, on the live URL.

### D1. User Side

*[S1: signup and login page, with a validation error shown (for example a weak password)]*

*[S2: the main feature page of a logged-in user, showing only that user's records]*

*[S3: profile page and the change password form, with the wrong current password rejected]*

*[S4: the sessions list with the revoke action]*

*[S5: a group page showing members and their permissions]*

*[S6: an action denied by RBAC, showing the message in the app and the 403 response in the browser network tab]*

### D2. Security Behaviour

*[S7: network tab showing the Authorization header (token masked) and an expired token returning 401]*

*[S8: the refresh request returning a new access token, and the httpOnly cookie in the application tab]*

*[S9: a banned user rejected on the next request]*

### D3. Admin Dashboard

*[S10: overview statistics]*

*[S11: users list with search, filters and pagination]*

*[S12: user detail with sessions and recent activity]*

*[S13: the ban dialog with a reason, and the banned state afterwards]*

*[S14: records and groups moderation list with filters and a bulk action]*

*[S15: activity log with filters, showing the events caused by the steps above]*

*[S16: security view with failed logins by IP and by account]*

*[S17: a CSV export downloaded and opened]*

### D4. Deployment

*[S18: the Vercel frontend project with the production deployment and domain]*

*[S19: the Vercel API project with the environment variable names (values hidden)]*

*[S20: the live API documentation page]*

S18–S20 can be taken from the existing Vercel project. The live API docs page shows the new routes only after the project is deployed again.

### D5. Tests

*[S21: test run output showing all tests and the result]*

## Part E. Project Management and Conclusion

### E1. How to Run and Test

Backend:

```powershell
cd backend
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
fastapi dev main.py
```

Frontend, second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. API docs: http://localhost:8000/api/docs.

Tests: from `backend`, run `pytest`.

If an old `backend/sitneat.db` is missing the new columns, stop the server and delete that file so the demo accounts and the Window party group are created again. Do not commit that database file.

### E2. GitHub Work

The public repository is https://github.com/2220229-art/2220229-S06-SeatNEat.

The planning issue is https://github.com/2220229-art/2220229-S06-SeatNEat/issues/1. The documentation pull request is https://github.com/2220229-art/2220229-S06-SeatNEat/pull/2.

This final implementation was prepared locally and was not pushed.

### E3. Limitations

- The final admin and group screens are not on the public Vercel URL until a new deploy.
- Screenshot images are not embedded in this markdown file. They belong in the PDF.
- Demo passwords are not in this file or in the README.
- The access token is still kept in `sessionStorage` so the existing pages can send it. The refresh token is the httpOnly cookie. A stolen access token works only until it expires.
- Group seat assignment checks that the seat exists. It does not re-run the full overlap rules that a new booking uses.
- An existing SQLite file does not gain new tables by itself until the app starts and `create_all` runs. Added columns are applied with `ALTER TABLE` on startup.

### E4. Future Work

- Deploy the final build to the existing Vercel project with `PASSWORD_PEPPER` set.
- Move the access token fully into memory and rely on the refresh cookie after every page load.
- Apply the same overlap check when a member assigns a different seat.
- Add page numbers on the admin lists in the React screen. The API already accepts `offset` and `limit`.

### E5. Sources, Libraries and Tools

- FastAPI, Starlette, Pydantic, and SQLModel for the API and tables.
- PyJWT for HS256 access tokens.
- pwdlib and Argon2 for password hashes.
- React, React Router, TypeScript, and Vite for the interface.
- pytest and httpx for the API tests.
- Neon for hosted Postgres, and Vercel for the earlier deployment.
- Course examples were used only as a heading guide for this report. The SitNeat text and code are for this restaurant project.
