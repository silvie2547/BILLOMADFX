# BILLOMADFX Backend

FastAPI foundation for the BILLOMADFX web app: account registration/login, bearer-token authentication, dashboard data, a safe NO TRADE signal response, demo-only position status, per-user risk defaults, emergency halt, and admin audit-log endpoint.

## Run locally

Requires Python 3.11 or newer.

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
# Copy .env.example to .env and set APP_SECRET_KEY to a random secret.
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API docs. Health check: `GET /health`.

## Authentication

Register with `POST /api/v1/auth/register` using JSON:

```json
{"email":"trader@example.com","password":"a-long-unique-password","display_name":"Trader"}
```

The API returns a short-lived bearer token. Use it in the `Authorization: Bearer <token>` header. Passwords are hashed with Argon2id. Registration never grants administrator privileges.

## Database

For local development, SQLite is created at `backend/data/billomadfx.db`. To use PostgreSQL, set `DATABASE_URL` to a SQLAlchemy URL such as `postgresql+psycopg://user:password@localhost:5432/billomadfx`. Use a dedicated least-privilege application role. `create_all` is for the initial development prototype; production schema changes should use reviewed migrations.

## Safety and production status

This backend is a development foundation, not a production-ready trading service. It has **no broker connector and no order submission, modification, or close endpoints**. Market signal is always `NO TRADE` until trusted market data and a validated strategy are deliberately integrated. Dashboard financial metrics are null rather than fabricated. Emergency stop records a halt flag; it cannot manage broker positions.

Before deployment: configure a strong unique `APP_SECRET_KEY`, PostgreSQL, HTTPS, restrictive `CORS_ORIGINS`, reverse-proxy rate limiting, database backups, monitoring, schema migrations, and security review. Do not expose this prototype publicly or use it for financial decisions.
