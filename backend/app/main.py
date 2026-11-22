from contextlib import asynccontextmanager
from datetime import timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, engine, get_db
from .dependencies import get_current_user, require_admin
from .market import MarketDataService, SUPPORTED_TIMEFRAMES
from .models import AuditEvent, RiskSettings, User
from .schemas import HaltResponse, LoginRequest, RegisterRequest, RiskResponse, RiskUpdateRequest, TokenResponse
from .security import create_access_token, hash_password, verify_password
from .mt5_routes import router as mt5_router

APP_VERSION = settings.app_version
market_service = MarketDataService()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "BILLOMADFX account, live gold market data and risk-control API. Market "
        "prices come from free public providers. Optional MT5 access is read-only "
        "and restricted to connected demo accounts; no order operations are exposed."
    ),
    version=APP_VERSION,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(mt5_router)


def audit(db: Session, user_id: int | None, event_type: str, detail: str = "") -> None:
    db.add(AuditEvent(user_id=user_id, event_type=event_type, detail=detail[:500]))
    db.commit()


def risk_for(db: Session, user: User) -> RiskSettings:
    if user.risk_settings is None:
        settings_row = RiskSettings(user_id=user.id)
        db.add(settings_row)
        db.commit()
        db.refresh(settings_row)
        return settings_row
    return user.risk_settings


def user_payload(user: User) -> dict:
    created = user.created_at
    if created and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "created_at": created.isoformat() if created else None,
    }


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "environment": settings.environment, "version": APP_VERSION, "trading_enabled": False}


@app.get("/api/v1/meta", tags=["system"])
def meta():
    """Public metadata so any client (PWA, Android APK) can identify the API."""
    return {
        "name": settings.app_name,
        "version": APP_VERSION,
        "market_sources": ["gold-api.com (spot XAU)", "Binance public REST (PAXG/USDT candles)"],
        "mt5_read_only": True,
        "order_execution": False,
    }


@app.post("/api/v1/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED, tags=["authentication"])
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    user = User(email=payload.email, display_name=payload.display_name, password_hash=hash_password(payload.password), role="user")
    db.add(user)
    try:
        db.flush()
        db.add(RiskSettings(user_id=user.id))
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    audit(db, user.id, "account.registered")
    token, expires = create_access_token(user.id)
    return {"access_token": token, "expires_in": expires, "user": user_payload(user)}


@app.post("/api/v1/auth/login", response_model=TokenResponse, tags=["authentication"])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect", headers={"WWW-Authenticate": "Bearer"})
    audit(db, user.id, "account.login")
    token, expires = create_access_token(user.id)
    return {"access_token": token, "expires_in": expires, "user": user_payload(user)}


@app.get("/api/v1/auth/me", tags=["authentication"])
def me(user: User = Depends(get_current_user)):
    return user_payload(user)


@app.get("/api/v1/dashboard", tags=["dashboard"])
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    risk = risk_for(db, user)
    quote = market_service.spot_quote()
    trend = market_service.trend("H1")
    return {
        "account": {"connected": False, "mode": None, "balance": None, "currency": None,
                    "message": "Connect the MT5 desktop terminal for account balances."},
        "trading": {"enabled": False, "open_positions": 0, "today_profit": None},
        "market": {
            "quote": quote,
            "trend": trend,
        },
        "signal": {
            "symbol": "XAU",
            "action": trend["trend"],
            "confidence": None,
            "reason": trend["reason"],
        },
        "risk": {"is_halted": risk.is_halted, "daily_loss_limit_pct": risk.daily_loss_limit_pct},
        "data_mode": "live" if quote["available"] else "unavailable",
    }


@app.get("/api/v1/market/quote", tags=["market"])
def market_quote(user: User = Depends(get_current_user)):
    """Live spot gold price from gold-api.com. Real data only; fails honest."""
    return market_service.spot_quote()


@app.get("/api/v1/market/candles", tags=["market"])
def market_candles(
    timeframe: str = Query("H1", pattern="^(M15|H1|H4|D1)$"),
    count: int = Query(100, ge=1, le=500),
    user: User = Depends(get_current_user),
):
    """Live tokenized-gold (PAXG/USDT) OHLC candles from Binance public REST."""
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise HTTPException(status_code=422, detail="Unsupported timeframe")
    return market_service.candles(timeframe, count)


@app.get("/api/v1/market/trend", tags=["market"])
def market_trend(user: User = Depends(get_current_user)):
    """Rule-based EMA/RSI trend read computed from real live candles."""
    return market_service.trend("H1")


@app.get("/api/v1/trading/positions", tags=["trading"])
def positions(user: User = Depends(get_current_user)):
    return {"items": [], "count": 0, "mode": "DEMO", "message": "Broker integration is not configured; no live account data is exposed."}


@app.get("/api/v1/risk", response_model=RiskResponse, tags=["risk"])
def get_risk(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = risk_for(db, user)
    return row


@app.put("/api/v1/risk", response_model=RiskResponse, tags=["risk"])
def update_risk(payload: RiskUpdateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = risk_for(db, user)
    row.daily_loss_limit_pct = payload.daily_loss_limit_pct
    row.weekly_loss_limit_pct = payload.weekly_loss_limit_pct
    row.max_drawdown_pct = payload.max_drawdown_pct
    row.max_spread_points = payload.max_spread_points
    db.add(row)
    db.add(AuditEvent(
        user_id=user.id,
        event_type="risk.settings_updated",
        detail=(
            f"daily={row.daily_loss_limit_pct}%; weekly={row.weekly_loss_limit_pct}%; "
            f"drawdown={row.max_drawdown_pct}%; spread={row.max_spread_points} points"
        ),
    ))
    db.commit()
    db.refresh(row)
    return row


@app.post("/api/v1/risk/emergency-stop", response_model=HaltResponse, tags=["risk"])
def emergency_stop(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = risk_for(db, user)
    row.is_halted = True
    db.add(row)
    db.commit()
    audit(db, user.id, "risk.emergency_stop", "Emergency halt flag recorded; broker orders cannot be managed in this release.")
    return {"is_halted": True, "message": "Emergency halt flag recorded. This API has no broker execution capability."}


@app.get("/api/v1/admin/audit", tags=["administration"])
def audit_log(limit: int = 50, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    return {"items": [{"id": row.id, "user_id": row.user_id, "event_type": row.event_type, "detail": row.detail, "created_at": row.created_at.isoformat()} for row in rows]}


# Single-origin hosting: when the web_app folder is available (Docker image,
# repo checkout, self-hosted install), serve the PWA from the same origin as
# the API so no CORS configuration is needed for the browser app.
def _locate_static_dir() -> Path | None:
    configured = Path(settings.static_dir)
    # Also try relative to the repo layout (backend/app/main.py -> repo root),
    # so the server works regardless of the process working directory.
    beside_repo = Path(__file__).resolve().parent.parent.parent / "web_app"
    inside_backend = Path(__file__).resolve().parent.parent / "web_app"
    for candidate in (configured, beside_repo, inside_backend):
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return candidate
    return None


_static_dir = _locate_static_dir()
if _static_dir is not None:
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="web_app")
