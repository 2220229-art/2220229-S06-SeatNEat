# SitNeat

SitNeat is a seat reservation system for one restaurant. A customer registers, logs in, searches for a free seat, and books a time. The customer also chooses vegetarian or non-vegetarian food and declares any allergies. Staff see today’s bookings and move them from confirmed to seated to completed. The manager manages seats, staff accounts, opening hours, and a simple summary.

The browser is a React application written in TypeScript. It talks to a FastAPI backend through JSON REST calls under /api/v1. SQLite stores the data. A logged-in user sends a JWT access token. The backend decides what that user may do from the role stored in the database. The React pages hide buttons for a nicer screen, but the backend is the real security checkBeta .
# Features
# MVP (demo before mid-term):
-Create, list, view, update, complete and delete tasks through a REST API (/api/v1/tasks).
-Input validation with clear error responses.
-Interactive API docs at /api/docs.

# Beta (demo before final):
-Sign up, log in, log out (JWT access token + refresh token cookie).
-Personal tasks: each user sees only their own.
-Profile page: change your name and password.
-Group tasks: create a group, add members, share and assign tasks.
-Roles: user and admin; admin dashboard with stats, ban / unban users.
-Security: Argon2 password hashing, login lockout, secure cookies, security headers
# Tech stack:
PART        CHOICE
Backend     Python 3.10+, FastAPI, SQLModel
Database    Supabase PostgreSQL (production), SQLite (local)
Frontend    React + TypeScript + Vite
Hosting     Vercel (frontend and backend in one project)
Beta extras Alembic (migrations), PyJWT, pwdlib (Argon2)


## Requirements
- Python 3.10+
- Node.js 22+

## Run locally

Backend:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
fastapi dev main.py
```

Frontend, in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server forwards `/api` to the backend on port 8000.

API docs: http://localhost:8000/api/docs

Copy `.env.example` to `.env` if you want to change the secret, database path, token lifetime, or frontend origin. The app runs with the defaults when no `.env` file is present.

## Demo accounts

These accounts are created the first time the backend starts.

| Role | Email | Password |
| --- | --- | --- |
| Customer | customer@sitneat.com | Customer123! |
| Staff | staff@sitneat.com | Staff123! |
| Manager | manager@sitneat.com | Manager123! |

Public registration always creates a customer. The manager creates staff accounts. A manager account cannot be created from the staff screen.

## Tests

From the `backend` folder, with the virtual environment active:

```powershell
pytest
```

## Booking rules

- One restaurant, time zone `Asia/Dhaka` by default.
- A new booking is confirmed immediately.
- The backend sets the end time from the configured duration. The customer does not send it.
- Confirmed and seated bookings block overlapping times for the same seat. A booking that ends at 19:30 does not block one that starts at 19:30.
- Status flow: confirmed → seated → completed. A confirmed booking can also be cancelled. Seated, completed, and cancelled bookings cannot be reopened.
- Customers can change or cancel their own confirmed booking only before the cutoff.
- Allergy notes are customer-declared. SitNeat does not guarantee allergen-free food.

## Deploy on Vercel

`vercel.json` deploys this repository as one project with two services. The Vite app serves the pages. FastAPI serves `/api`. Set the Vercel project root to this repository folder so both services build together.

In the Vercel project settings, add these environment variables for Production and Preview:

| Name | Value |
| --- | --- |
| `DATABASE_URL` | The Neon **pooled** connection string. The host contains `-pooler`. Reservations stay in Postgres across restarts. |
| `SECRET_KEY` | A long random string. The API refuses to start in production while this is empty or still the example value. |
| `APP_ENV` | `production` |
| `SEED_DEMO` | `true` to create the demo accounts when the database is empty. |

Leave `VITE_API_BASE` unset. The site calls `/api/v1` on the same address, and routes such as `/login` and `/book` fall back to the React app.

Local `fastapi dev` still uses `backend/sitneat.db` until `DATABASE_URL` is set. A Postgres URL is used as given.
