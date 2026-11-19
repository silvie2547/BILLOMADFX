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
- Dashboard, position, market-signal, and risk views load from protected API endpoints.
- No account balance or trade is fabricated; unavailable values are shown explicitly.
- Emergency stop calls `/api/v1/risk/emergency-stop` and requires confirmation.
- Broker connection and order controls remain unavailable.
