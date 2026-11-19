## MT5 demo-only read integration

The backend now includes protected read-only endpoints under `/api/v1/mt5/`:

- `GET /api/v1/mt5/status`
- `GET /api/v1/mt5/account`
- `GET /api/v1/mt5/positions`
- `GET /api/v1/mt5/bars?timeframe=H1&count=100`

Install the Windows-only package locally:

```powershell
cd backend
pip install -r requirements.txt
pip install -r requirements-mt5.txt
copy .env.example .env
set MT5_TERMINAL_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
uvicorn app.main:app --reload
```

The integration refuses real, disconnected, unavailable, or non-demo sessions. It contains no code that sends, modifies, cancels, or closes orders. It never accepts account passwords. Credentials are excluded from API responses.
