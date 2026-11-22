# BILLOMADFX
### AI-Powered Automated Gold Trading Platform

**Tagline:** TRADE • ANALYSE • GROW

---

## 1. Project Overview

BILLOMADFX is an AI-powered automated trading platform designed primarily for Gold (XAUUSD) trading through MetaTrader 5 (MT5).

The platform will combine artificial intelligence, machine learning, market analysis, risk management and automated trade execution to help users make informed trading decisions.

The system will independently analyse market conditions and determine whether to:

- BUY
- SELL
- NO TRADE

NO TRADE is a valid and important decision. The system must never force trades simply to remain active.

The project aims to provide a reliable, intelligent, secure and user-friendly automated trading experience.

**Important:** Profitability is an objective, not a guarantee. The system must demonstrate its performance through rigorous testing before any live trading is permitted.

## 2. Project Objectives

1. Develop an AI-powered gold trading engine.
2. Integrate automated trading with MetaTrader 5.
3. Develop and validate a conservative trading strategy.
4. Implement intelligent market analysis using AI, ML and deep learning where justified.
5. Provide strict capital protection and risk management.
6. Support multiple users through a secure platform.
7. Develop a website and mobile application.
8. Provide an administrative dashboard.
9. Maintain transparent trading records and performance reports.
10. Build a scalable platform that can support future improvements.

## 3. Brand Identity

**Project name:** BILLOMADFX

**Tagline:** TRADE • ANALYSE • GROW

**Visual identity:**
- Primary background: Deep black.
- Primary accent: Metallic gold.
- Secondary accent: Deep navy.
- Supporting colors: White, green and red.

**Logo concept:**
A metallic gold bull emblem, circular elements, candlestick bars and an upward-moving arrow.

**Brand personality:**
Professional, intelligent, modern, confident and technology-driven.

The logo and app icon should be included in the project's assets directory.

## 4. Core Features

### 4.1 AI Market Analysis
- Analyse XAUUSD market data.
- Identify market trends and possible reversals.
- Evaluate volatility and market conditions.
- Analyse multiple timeframes.
- Identify potential trading opportunities.
- Generate BUY, SELL or NO TRADE decisions.

### 4.2 Automated Trading
- Connect to MetaTrader 5.
- Execute approved trades automatically.
- Set Stop Loss and Take Profit.
- Calculate position sizes.
- Monitor open positions.
- Manage trade execution and errors.
- Record trading activities.

### 4.3 Risk Management
- Conservative position sizing.
- Mandatory Stop Loss.
- Daily loss limits.
- Weekly loss limits.
- Maximum drawdown protection.
- Spread and slippage restrictions.
- Emergency trading shutdown.
- Protection against duplicate orders.

The system must not use martingale, uncontrolled grid trading or recovery strategies that increase exposure without proper risk limits.

### 4.4 User Platform
- User registration and authentication.
- User dashboard.
- MT5 account connection.
- Trading status.
- Performance history.
- Account and risk settings.
- Notifications.

### 4.5 Administrative Dashboard
- User management.
- System monitoring.
- Trading activity monitoring.
- Risk monitoring.
- System configuration.
- Emergency shutdown controls.
- Audit logs.

### 4.6 Mobile Application
- Android support.
- iPhone support.
- Trading status.
- Account overview.
- Performance reports.
- Notifications.
- Secure user authentication.

## 5. Technology Stack

| Component | Technology |
|---|---|
| Backend | Python |
| API | FastAPI |
| AI and Machine Learning | Python, Scikit-learn, PyTorch |
| Trading integration | MetaTrader 5 Python API |
| Database | PostgreSQL |
| Web frontend | HTML, CSS, JavaScript |
| Mobile application | Flutter and Dart |
| Real-time communication | WebSockets |
| Notifications | Firebase Cloud Messaging |
| Version control | Git and GitHub |
| Development environment | Visual Studio Code |

Technology choices may be adjusted after compatibility and performance testing.

## 6. System Architecture

BILLOMADFX will use a modular architecture.

### Main components

1. User interface
2. Authentication and user management
3. Backend API
4. AI analysis engine
5. Market data processing
6. Strategy engine
7. Risk management engine
8. MT5 integration
9. Database
10. Notification service
11. Administration dashboard

### Trading workflow

Market Data → Data Processing → AI Analysis → Strategy Decision → Risk Validation → MT5 Execution → Trade Monitoring → Database Records → User Notifications

Every proposed trade must pass risk validation before execution.

## 7. Gold Trading Strategy Research

The primary market is XAUUSD.

The initial strategy research will investigate:

- Multi-timeframe trend analysis.
- Trend continuation.
- Pullback entries.
- Support and resistance.
- Price action.
- Market volatility.
- Momentum.
- Market structure.

### Candidate timeframes

| Timeframe | Proposed purpose |
|---|---|
| D1 | Major market direction |
| H4 | Market regime |
| H1 | Trading setup |
| M15 | Entry confirmation |

### Candidate indicators

- Exponential Moving Averages (EMA).
- Relative Strength Index (RSI).
- Average True Range (ATR).
- Average Directional Index (ADX).

These are research candidates, not a finalized trading strategy.

The strategy must be tested against historical and unseen data before approval.

## 8. AI, Machine Learning and Deep Learning

The AI system will be developed in stages.

### Stage 1: Data collection
- Historical XAUUSD data.
- Market prices.
- Candlestick information.
- Volume information where available.
- Spread and execution information.

### Stage 2: Data preparation
- Data cleaning.
- Missing-value handling.
- Feature engineering.
- Normalization where appropriate.
- Time-series preparation.

### Stage 3: Model research
Evaluate suitable models for:
- Market classification.
- Trend identification.
- Volatility estimation.
- Trading signal classification.

### Stage 4: Model evaluation
Evaluate:
- Accuracy.
- Precision and recall.
- False signals.
- Risk-adjusted performance.
- Out-of-sample performance.

### Stage 5: Integration
Integrate validated models into the trading engine.

AI predictions must never bypass the risk management system.

## 9. MetaTrader 5 Integration

MT5 will provide the connection between BILLOMADFX and the trading environment.

Integration responsibilities include:

- Terminal connection.
- Account information retrieval.
- Symbol information retrieval.
- Historical market data.
- Price monitoring.
- Order submission.
- Order modification.
- Position monitoring.
- Trade history retrieval.
- Execution error handling.

### Account requirements

Initial development will use demo accounts only.

The system must verify:
- MT5 terminal availability.
- Account connection.
- Trading permissions.
- Algo Trading permissions.
- Symbol availability.
- Market availability.
- Broker contract specifications.

Each user's trading session must be isolated and securely managed.

## 10. Risk Management and Safety

Capital protection is a fundamental requirement.

The system must implement:

1. Mandatory Stop Loss.
2. Risk-based position sizing.
3. Maximum exposure limits.
4. Daily loss limits.
5. Weekly loss limits.
6. Maximum drawdown limits.
7. Spread restrictions.
8. Slippage protection.
9. Duplicate-order protection.
10. Emergency shutdown.

The system must account for gold volatility, gaps, spreads, commissions, swaps and execution costs.

An emergency shutdown must prevent new orders. Its treatment of existing open positions must be explicitly configured and tested.

No live trading will be enabled until all required testing and safety reviews are complete.

## 11. Backend and Database

PostgreSQL will store structured application information.

Planned database entities include:

- Users.
- User settings.
- MT5 account connections.
- Trading sessions.
- Market data.
- Trading signals.
- Orders.
- Positions.
- Transactions.
- Risk records.
- Model versions.
- Notifications.
- Audit logs.

The backend will expose secure APIs through FastAPI.

The application must use a dedicated least-privilege database account rather than connecting as the PostgreSQL superuser.

Passwords and account credentials must never be stored in plaintext.

## 12. Website and Mobile Application

### Website

The website will provide:
- Landing page.
- Registration and login.
- User dashboard.
- Trading status.
- Account management.
- Performance reports.
- Administrative dashboard.

### Mobile application

Flutter will be used to develop Android and iOS applications from a shared codebase.

The mobile application will provide:
- Secure login.
- User dashboard.
- Trading status.
- Account information.
- Notifications.
- Performance monitoring.
- User settings.

The mobile application will not contain broker passwords or unrestricted trading credentials.

iOS builds and releases will require access to macOS and Xcode.

## 13. Security

Security requirements include:

- Secure authentication.
- Password hashing.
- Encrypted communication.
- Protected secrets.
- Role-based access control.
- Secure database permissions.
- Input validation.
- API authorization.

### 13.1 Authentication and session security (implemented)

- **Auth-first flow:** the app opens on the Sign in / Create account screen. No dashboard content is rendered until the API confirms the session; a stored session is restored silently ("Restoring your session…").
- **Password policy:** minimum 12 characters with uppercase, lowercase and a number; the password must not contain the email address. Hashed with Argon2id.
- **Stay signed in:** tokens last 30 days and slide forward — when fewer than 5 days remain, the client silently exchanges them for a fresh token (`POST /api/v1/auth/refresh`). Regular use never re-asks for the password.
- **Real logout:** signing out bumps the account's token version, instantly revoking every token issued before that moment, on all devices. Old or copied tokens stop working immediately (`401`).
- **Brute-force protection:** an account locks for 15 minutes after 5 failed sign-ins; registration and sign-in are additionally rate-limited per network (8 registrations/hour, 15 sign-ins per 5 minutes). Unknown emails get identical Argon2 work so response timing cannot reveal which accounts exist.
- **Hardened transport:** every response carries `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy` and `Permissions-Policy`; HTML responses get a strict Content-Security-Policy (`default-src 'self'`, no inline script), API responses are `Cache-Control: no-store`, and production adds HSTS.
- Login, registration, logout and emergency-halt events are written to the audit log (Administration page, admin role required).
- Audit logging.
- Session isolation.
- Rate limiting.
- Backup and recovery procedures.

Sensitive trading credentials must not be committed to GitHub or included in source code.

## 14. Testing and Quality Assurance

Testing will take place in stages.

### Stage 1: Unit testing
Test individual application components.

### Stage 2: Integration testing
Test communication between the backend, database and MT5.

### Stage 3: Historical backtesting
Test strategy performance using historical data.

### Stage 4: Out-of-sample testing
Evaluate performance on data not used during model development.

### Stage 5: Demo forward testing
Run the complete system using an MT5 demo account under real market conditions.

### Stage 6: Security and reliability testing
Test authentication, permissions, failure recovery and risk controls.

### Stage 7: Deployment readiness
Verify all components before considering a live release.

Performance evaluation must include spreads, commissions, swaps, slippage and realistic execution assumptions.

## 15. Project Structure

The planned directory structure is:

```text
BILLOMADFX/
│
├── README.md
│
├── assets/
│   ├── logo/
│   ├── app_icon/
│   └── branding/
│
├── backend/
│   ├── app/
│   ├── api/
│   ├── authentication/
│   └── requirements.txt
│
├── trading_engine/
│   ├── data/
│   ├── analysis/
│   ├── strategies/
│   ├── risk_management/
│   ├── execution/
│   └── monitoring/
│
├── ai_models/
│   ├── data/
│   ├── training/
│   ├── evaluation/
│   └── saved_models/
│
├── database/
│   ├── migrations/
│   └── schemas/
│
├── mt5_demo_permissions/
│   ├── ENABLE_MT5_DEMO_PERMISSIONS.ps1
│   ├── check_mt5_trade_permissions.py
│   ├── RUN_MT5_DEMO_PERMISSIONS.bat
│   └── README.txt
│
├── web_app/
│
├── mobile_app/
│
├── admin_dashboard/
│
├── tests/
│
├── docs/
│
├── scripts/
│
├── .env.example
├── .gitignore
└── requirements.txt
```

This is the intended structure. Directories and files will be created gradually as their components are developed.

## 16. Installation and Development Environment

Initial development environment:

- Windows laptop.
- Visual Studio Code.
- Python 3.13.17 (64-bit).
- Git.
- Node.js and npm.
- PostgreSQL 14.25.

The project will use a dedicated Python virtual environment.

Python dependencies will be installed into that environment rather than globally.

The existing Python 3.15 installation will remain untouched.

Docker is optional and will be considered later depending on system resources.

## 17. Current Development Status

### Completed

- [x] BILLOMADFX project concept.
- [x] Initial system architecture.
- [x] Gold trading requirements.
- [x] Conservative risk specifications.
- [x] MT5 integration planning.
- [x] Demo permissions helper received and reviewed.
- [x] Main project folder created.
- [x] Demo permissions helper copied into project.
- [x] PostgreSQL 14.25 installed and running.
- [x] PostgreSQL authentication configured and verified.
- [x] `billomadfx` database created.
- [x] Python 3.13.17 (64-bit) verified.
- [x] pip verified.

### Pending

- [ ] Complete project folder structure.
- [ ] Establish Python virtual environment.
- [ ] Verify required Python package compatibility.
- [ ] Configure database application user.
- [ ] Test Python-to-PostgreSQL connection.
- [ ] Install and configure MT5.
- [ ] Test MT5 demo connectivity.
- [ ] Develop market data pipeline.
- [ ] Research and validate trading strategy.
- [ ] Develop AI analysis engine.
- [ ] Develop risk management engine.
- [ ] Develop automated execution engine.
- [ ] Develop website.
- [ ] Develop mobile application.
- [ ] Develop administration dashboard.
- [ ] Complete system integration and testing.

## 18. Development Roadmap

**Phase 1:** Environment and project preparation.

**Phase 2:** Project structure and documentation.

**Phase 3:** Backend and database development.

**Phase 4:** MT5 connection and market data collection.

**Phase 5:** Gold trading strategy research.

**Phase 6:** AI, machine learning and model development.

**Phase 7:** Risk management and execution engine.

**Phase 8:** Website and administration dashboard.

**Phase 9:** Android and iOS application.

**Phase 10:** Full system integration.

**Phase 11:** Backtesting, demo testing and security review.

**Phase 12:** Deployment and release readiness.

## 19. Important Development Principles

- Build incrementally.
- Test every major component.
- Never skip risk validation.
- Never assume a trade signal is profitable.
- Never expose user credentials.
- Maintain clean and documented code.
- Keep backups of important project files.
- Use demo accounts during development.
- Do not enable live trading prematurely.
- Preserve the original MT5 demo helper as a reference.
- Document every important configuration change.

## 20. Project Vision

BILLOMADFX aims to become a complete AI-powered trading ecosystem combining intelligent analysis, automated execution, strict risk management and accessible user technology.

The goal is not simply to create a bot that places trades.

The goal is to build a dependable, secure and carefully tested trading platform.

## 21. Releases, Versioning and Installation

The repository ships a real, installable app on every push to `main` via the `Release` GitHub Action:

- **Versioning:** releases start at **v0.0.1** and the patch number increases by **+0.0.1** on every push (`v0.0.2`, `v0.0.3`, ...). The version is stamped into the Android app (`versionName`/`versionCode`), the release tag, and the API (`GET /api/v1/meta`).
- **Artifacts per release:** `BILLOMADFX-vX.Y.Z.apk` (signed Android app) and `BILLOMADFX-PWA-vX.Y.Z.zip` (installable web app for self-hosting).

### Install on Android

1. Download the APK from the GitHub Releases page.
2. Open it; allow *Install unknown apps* for the browser if prompted.
3. New releases install directly over the old one (stable signing key).

### Install on Windows / macOS / Linux / iOS

The web app is a full PWA. Deploy the backend (below), open its URL and install:

- Chrome/Edge (desktop and Android): in-app **Install app** button or address-bar install icon.
- iOS Safari: *Share → Add to Home Screen*.

### Android app and the API

The APK bundles this web frontend and calls the deployed backend for accounts and market data. Set the repository variable `APP_API_URL` (Settings → Secrets and variables → Actions → Variables) to the backend's public URL before pushing, and it is baked into the built app.

## 22. Deploying the API (real users)

Anyone can create an account once the backend is reachable over HTTPS:

- **Render (easiest):** New + → Blueprint → select this repository. `render.yaml` provisions the web service and a PostgreSQL database (`APP_SECRET_KEY` is generated automatically).
- **Docker (self-host):**
  ```bash
  docker compose up --build -d    # app on http://localhost:8000
  ```
- **Local:** `cd backend && pip install -r requirements.txt && uvicorn app.main:app`

The backend serves the web app and the API from one origin; browsers, PWAs and the Android app all talk to the same URL. Users, passwords (Argon2id), risk limits and audit events are stored persistently (SQLite locally/PostgreSQL in production).

**Create the first administrator** after registering your own account in the app:

```bash
cd backend && python make_admin.py you@your-domain.com   # promote
python make_admin.py --list                              # see all accounts
```

On Render: run the same command from the service's Shell tab — `DATABASE_URL` is already set by the blueprint. Administrators see the Administration page and the audit log.

## 23. Live Market Data

Prices and candles are real and fetched from free public providers, with no API keys:

- Spot gold (XAU/USD): `gold-api.com`.
- Candlesticks and the EMA/RSI trend engine: Binance public REST, `PAXG/USDT` (a gold-backed token, 1 token = 1 troy ounce), on M15/H1/H4/D1.
- If a provider is unreachable the app reports the failure instead of showing invented numbers.
- Optional read-only MetaTrader 5 integration remains available for users with a connected desktop terminal.

The app does not submit, modify, or close broker orders, and no component does.

**BILLOMADFX — TRADE • ANALYSE • GROW**

---
