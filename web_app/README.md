# BILLOMADFX Web Frontend

A responsive, dependency-free frontend for BILLOMADFX.

## Run with the backend

Start the API:

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Serve the frontend from a separate terminal:

```bash
cd web_app
python -m http.server 8080
```

Open `http://localhost:8080`. The default API URL is `http://127.0.0.1:8000`.

To use another API URL, set it before `app.js` loads:

```html
<script>window.BILLOMADFX_API_URL = 'https://api.example.com';</script>
<script src="app.js"></script>
```

## Integration behavior

- Sign-in and registration use FastAPI bearer authentication.
- JWT tokens are stored in browser `localStorage`.
- Dashboard risk settings and market-signal state load from protected API endpoints.
- MT5 account, positions, and H1 bars are read only from a connected demo account; all other account modes are blocked.
- The trading view plots the returned H1 OHLC bars; the administrator view loads the protected audit log only for administrator accounts.
- No account balance, position, signal, or performance statistic is fabricated; unavailable values are shown explicitly.
- Emergency halt records a per-account flag; it does not stop or manage broker orders in this release.
- There are no order submission, modification, or close controls/endpoints.
