# BILLOMADFX Web Frontend

A responsive, dependency-free frontend demo for the BILLOMADFX gold trading platform.

## Features

- Overview dashboard
- XAUUSD trading workspace
- AI signal panel
- MT5 account connection status
- Performance analytics
- Risk controls
- Administration view
- Dark and light themes
- Mobile navigation
- Demo-safe order controls

## Run locally

Open `index.html` directly in a browser, or serve the directory:

```bash
cd web_app
python -m http.server 8080
```

Then visit `http://localhost:8080`.

## Safety

The frontend is currently a visual prototype backed by demonstration data. It does not connect to a broker or submit orders. Live execution controls remain disabled until backend authentication, risk validation, MT5 demo verification, testing, and explicit operator approval are implemented.
