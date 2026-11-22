# BILLOMADFX Web App (PWA)

A dependency-free, installable frontend for BILLOMADFX. Works as a Progressive
Web App on Android, Windows, macOS, Linux and iOS, and is bundled into the
Android app by Capacitor.

## Run (single origin — recommended)

The FastAPI backend serves this folder directly, so there is no CORS setup:

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
copy .env.example .env   # Windows; use cp on macOS/Linux
uvicorn app.main:app
```

Open `http://127.0.0.1:8000` — the app and the API share one origin.

## Frontend-only development (optional)

```bash
cd web_app && python -m http.server 8080
```

Set the API URL in `web_app/config.js` (`window.BILLOMADFX_API_URL = 'http://127.0.0.1:8000'`).

## Install on a device

- **Android (Chrome):** open the deployed URL → tap **Install app** in the
  sidebar (or Chrome menu → *Add to Home screen*). Or install the signed APK
  from the GitHub Releases page.
- **Windows / macOS / Linux (Chrome, Edge):** address-bar install icon →
  *Install BILLOMADFX*.
- **iOS (Safari):** Share → *Add to Home Screen*.

## Integration behavior

- Real user accounts: Argon2-hashed passwords, JWT bearer sessions (no demo mode).
- Live market data: spot gold from gold-api.com; H1/H4/D1 candles and the
  EMA/RSI trend engine from Binance public REST (PAXG/USDT tokenized gold).
  Nothing is fabricated; if a provider is down the UI says so.
- Optional read-only MT5 integration: when the local MT5 desktop terminal is
  connected to a demo account, its data takes precedence over Binance data.
- Risk limits are bounded by project maxima and validated on save.
- No order submission, modification, or close controls/endpoints exist.
