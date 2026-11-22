import base64
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import pyotp
import qrcode
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from jwt import InvalidTokenError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import emailer, ratelimit
from . import otp as otp_service
from .config import settings
from .database import Base, engine, get_db, run_light_migrations
from .dependencies import get_current_user, require_admin
from .market import MarketDataService, SUPPORTED_TIMEFRAMES
from .models import AuditEvent, BackupCode, RiskSettings, User, utc_now
from .schemas import (
    AccessTokenResponse,
    ForgotPasswordRequest,
    HaltResponse,
    LoginRequest,
    RegisterRequest,
    ResendOtpRequest,
    ResetPasswordRequest,
    RiskResponse,
    RiskUpdateRequest,
    SignUpResponse,
    TokenResponse,
    TwoFactorChallengeResponse,
    TwoFactorConfirmRequest,
    TwoFactorDisableRequest,
    TwoFactorLoginRequest,
    TwoFactorSetupResponse,
    VerifyOtpRequest,
)
from .security import (
    DUMMY_HASH,
    create_access_token,
    create_challenge_token,
    decode_challenge_token,
    hash_password,
    verify_password,
)
from .mt5_routes import router as mt5_router

APP_VERSION = settings.app_version
market_service = MarketDataService()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    # create_all never alters existing tables; add columns shipped after the
    # first release so upgrades keep working without manual SQL.
    run_light_migrations()
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


def client_ip(request: Request) -> str:
    """Best-effort client IP. Behind Render/nginx the socket address is the
    proxy, so the first forwarded entry is used when enabled."""
    if settings.trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def too_many_requests(retry_after_seconds: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": message},
        headers={"Retry-After": str(retry_after_seconds)},
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    if request.url.path.startswith("/api/"):
        # Authenticated API answers must never be cached anywhere.
        response.headers.setdefault("Cache-Control", "no-store")
    elif request.method == "GET" and (response.headers.get("content-type") or "").startswith("text/html"):
        connect_src = " ".join(["'self'", *settings.csp_connect_srcs])
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self'; "
            f"style-src 'self' https://fonts.googleapis.com; "
            f"font-src 'self' https://fonts.gstatic.com; "
            f"connect-src {connect_src}; "
            "img-src 'self' data:; "
            "manifest-src 'self'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
        )
        if settings.environment.lower() == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


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
        "email_verified": bool(user.email_verified),
        "two_factor_enabled": bool(user.two_factor_enabled),
        "created_at": created.isoformat() if created else None,
    }


def deliver_otp(db: Session, user: User, purpose: str, sender) -> tuple[str, str | None]:
    """Issue a one-time code and deliver it. SMTP when configured; otherwise
    the code is returned for display mode. Returns (delivery, code_or_None)."""
    if not ratelimit.otp_send_email_limiter.allow(user.email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Codes were sent too often for this address. Request a new one in a few minutes.",
        )
    code = otp_service.issue_otp(db, user, purpose)
    sent = sender(user.email, code, settings.otp_ttl_minutes)
    return ("email" if sent else "display"), (None if sent else code)


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


@app.post("/api/v1/auth/register", response_model=SignUpResponse, status_code=status.HTTP_201_CREATED, tags=["authentication"])
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request)
    if not ratelimit.register_ip_limiter.allow(ip):
        return too_many_requests(ratelimit.REGISTER_WINDOW, "Too many accounts created from this network. Try again later.")
    # Sign-up sends a one-time code to the email address; the account only
    # becomes active after the code is confirmed (valid for 20 minutes).
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        if existing.email_verified:
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        # Unverified duplicate: re-send the verification code instead of failing.
        delivery, shown = deliver_otp(db, existing, otp_service.PURPOSE_SIGNUP, emailer.send_verification_code)
        audit(db, existing.id, "account.otp_resent", f"delivery={delivery}")
        return {
            "otp_required": True,
            "email": existing.email,
            "delivery": delivery,
            "otp": shown,
            "expires_in_minutes": settings.otp_ttl_minutes,
            "message": "A fresh verification code has been sent for this address.",
        }
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
    delivery, shown = deliver_otp(db, user, otp_service.PURPOSE_SIGNUP, emailer.send_verification_code)
    audit(db, user.id, "account.otp_sent", f"delivery={delivery}")
    message = (
        f"We sent a verification code to {user.email}. It expires in {settings.otp_ttl_minutes} minutes."
        if delivery == "email"
        else f"Email delivery is not configured on this deployment — your verification code is shown below and expires in {settings.otp_ttl_minutes} minutes."
    )
    return {
        "otp_required": True,
        "email": user.email,
        "delivery": delivery,
        "otp": shown,
        "expires_in_minutes": settings.otp_ttl_minutes,
        "message": message,
    }


@app.post("/api/v1/auth/login", response_model=TokenResponse | TwoFactorChallengeResponse, tags=["authentication"])
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request)
    if not ratelimit.login_ip_limiter.allow(ip):
        return too_many_requests(ratelimit.LOGIN_WINDOW, "Too many sign-in attempts from this network. Try again later.")
    email = payload.email.strip().lower()
    if ratelimit.login_throttle.is_locked(email):
        return too_many_requests(ratelimit.FAILED_LOGIN_WINDOW, "This account is temporarily locked after repeated failed sign-ins. Try again in 15 minutes.")
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        # Burn the same Argon2 work for unknown emails so response timing does
        # not reveal which emails have accounts.
        if user is None:
            verify_password(payload.password, DUMMY_HASH)
        ratelimit.login_throttle.record_failure(email)
        raise HTTPException(status_code=401, detail="Email or password is incorrect", headers={"WWW-Authenticate": "Bearer"})
    ratelimit.login_throttle.clear(email)
    if not user.email_verified:
        # The password was correct; steer the user back to the code screen.
        raise HTTPException(
            status_code=403,
            detail={
                "code": "email_not_verified",
                "message": "Verify your email to finish signing in — enter the code we sent or request a new one.",
            },
        )
    if user.two_factor_enabled and user.totp_secret:
        # Two-step authentication: the password alone is not enough. The
        # challenge token only allows submitting a code; it is not a session.
        challenge, expires = create_challenge_token(user.id)
        return {"totp_required": True, "challenge_token": challenge, "expires_in": expires}
    audit(db, user.id, "account.login")
    token, expires = create_access_token(user.id, user.token_version)
    return {"access_token": token, "expires_in": expires, "user": user_payload(user)}


@app.get("/api/v1/auth/me", tags=["authentication"])
def me(user: User = Depends(get_current_user)):
    return user_payload(user)


@app.post("/api/v1/auth/refresh", response_model=AccessTokenResponse, tags=["authentication"])
def refresh(user: User = Depends(get_current_user)):
    """Sliding sessions: a valid token is exchanged for a fresh one, so an
    active user never hits the expiry while inactive users time out."""
    token, expires = create_access_token(user.id, user.token_version)
    return {"access_token": token, "expires_in": expires}


@app.post("/api/v1/auth/logout", tags=["authentication"])
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Server-side revocation: bumping the token version invalidates every
    # token issued before now, on every device.
    user.token_version += 1
    db.commit()
    audit(db, user.id, "account.logout")
    return {"logged_out": True}


@app.post("/api/v1/auth/verify-otp", response_model=TokenResponse, tags=["authentication"])
def verify_signup_otp(payload: VerifyOtpRequest, request: Request, db: Session = Depends(get_db)):
    """Confirm the sign-up code. Success verifies the email and signs the user in."""
    if not ratelimit.otp_verify_ip_limiter.allow(client_ip(request)):
        return too_many_requests(ratelimit.OTP_VERIFY_IP_WINDOW, "Too many verification attempts. Wait a few minutes.")
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid or expired code.")
    if user.email_verified:
        raise HTTPException(status_code=400, detail="This account is already verified — sign in instead.")
    ok, reason = otp_service.verify_otp(db, user, otp_service.PURPOSE_SIGNUP, payload.code)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    user.email_verified = True
    db.commit()
    audit(db, user.id, "account.verified")
    token, expires = create_access_token(user.id, user.token_version)
    return {"access_token": token, "expires_in": expires, "user": user_payload(user)}


@app.post("/api/v1/auth/resend-otp", tags=["authentication"])
def resend_otp(payload: ResendOtpRequest, request: Request, db: Session = Depends(get_db)):
    """Re-send a sign-up verification code (max 3 per address per 20 minutes)."""
    if not ratelimit.otp_send_ip_limiter.allow(client_ip(request)):
        return too_many_requests(ratelimit.OTP_SEND_IP_WINDOW, "Too many code requests from this network. Try again later.")
    generic = {
        "resent": False,
        "delivery": "email" if emailer.email_delivery_enabled() else "display",
        "message": "If this address needs verification, a new code has been sent.",
    }
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not user.is_active or user.email_verified:
        return generic
    delivery, shown = deliver_otp(db, user, otp_service.PURPOSE_SIGNUP, emailer.send_verification_code)
    audit(db, user.id, "account.otp_resent", f"delivery={delivery}")
    return {
        "resent": True,
        "email": user.email,
        "delivery": delivery,
        "otp": shown,
        "expires_in_minutes": settings.otp_ttl_minutes,
        "message": "A fresh verification code has been sent.",
    }


@app.post("/api/v1/auth/forgot-password", tags=["authentication"])
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Start a password reset. The answer is identical whether or not the
    account exists, so this endpoint cannot be used to probe addresses."""
    if not ratelimit.forgot_ip_limiter.allow(client_ip(request)):
        return too_many_requests(ratelimit.FORGOT_IP_WINDOW, "Too many reset requests from this network. Try again later.")
    generic = {
        "message": "If an account exists for this address, a reset code has been sent. It expires in 20 minutes and can be used once.",
    }
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not user.is_active:
        return generic
    try:
        delivery, shown = deliver_otp(db, user, otp_service.PURPOSE_RESET, emailer.send_password_reset_code)
    except HTTPException:
        # Per-address resend ceiling hit: keep the generic (non-enumerating) answer.
        return {**generic, "delivery": "email" if emailer.email_delivery_enabled() else "display"}
    audit(db, user.id, "account.password_reset_requested", f"delivery={delivery}")
    if delivery == "display":
        return {**generic, "delivery": "display", "otp": shown}
    return {**generic, "delivery": "email"}


@app.post("/api/v1/auth/reset-password", tags=["authentication"])
def reset_password(payload: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Set a new password with a valid reset code. Revokes every session."""
    if not ratelimit.otp_verify_ip_limiter.allow(client_ip(request)):
        return too_many_requests(ratelimit.OTP_VERIFY_IP_WINDOW, "Too many attempts. Wait a few minutes.")
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid or expired code.")
    ok, reason = otp_service.verify_otp(db, user, otp_service.PURPOSE_RESET, payload.code)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1
    user.email_verified = True
    db.commit()
    audit(db, user.id, "account.password_reset", "All sessions revoked")
    return {
        "password_reset": True,
        "message": "Your password is updated and previous sessions were signed out everywhere. Sign in with your new password.",
    }


@app.post("/api/v1/auth/2fa/setup", response_model=TwoFactorSetupResponse, tags=["authentication"])
def twofactor_setup(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Start 2FA enrollment: returns the TOTP secret, otpauth URI and QR code."""
    if user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="Two-step authentication is already enabled for this account.")
    secret = pyotp.random_base32()
    user.totp_secret = secret
    db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="BILLOMADFX")
    buffer = BytesIO()
    qrcode.make(uri).save(buffer, format="PNG")
    data_uri = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    audit(db, user.id, "security.2fa_setup_started")
    return {"otpauth_uri": uri, "qr_data_uri": data_uri, "secret": secret}


@app.post("/api/v1/auth/2fa/confirm", tags=["authentication"])
def twofactor_confirm(payload: TwoFactorConfirmRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Activate 2FA after the user proves they can read the authenticator."""
    if user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="Two-step authentication is already enabled.")
    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="Start the setup first.")
    if not pyotp.TOTP(user.totp_secret).verify(payload.code, valid_window=1):
        raise HTTPException(status_code=400, detail="That code is not correct — enter the current 6-digit code from your authenticator app.")
    user.two_factor_enabled = True
    db.commit()
    codes = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(8)]
    # Store the dash-less lowercase form so sign-in can compare a normalized input.
    db.add_all([BackupCode(user_id=user.id, code_hash=hash_password(code.replace("-", "").lower())) for code in codes])
    db.commit()
    audit(db, user.id, "security.2fa_enabled")
    emailer.send_2fa_enabled_notice(user.email)
    return {
        "enabled": True,
        "backup_codes": codes,
        "message": "Two-step authentication is on. Store these one-time codes somewhere safe — each works once if you lose your authenticator.",
    }


@app.post("/api/v1/auth/2fa/disable", tags=["authentication"])
def twofactor_disable(payload: TwoFactorDisableRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Turn 2FA off. Requires the account password, not just a valid session."""
    if not user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="Two-step authentication is not enabled.")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Password incorrect — two-step authentication stays on.")
    user.two_factor_enabled = False
    user.totp_secret = None
    db.execute(delete(BackupCode).where(BackupCode.user_id == user.id))
    db.commit()
    audit(db, user.id, "security.2fa_disabled")
    return {"enabled": False, "message": "Two-step authentication is off for this account."}


@app.post("/api/v1/auth/login/2fa", response_model=TokenResponse, tags=["authentication"])
def twofactor_login(payload: TwoFactorLoginRequest, request: Request, db: Session = Depends(get_db)):
    """Finish a 2FA sign-in with a TOTP code or a single-use backup code."""
    if not ratelimit.login_ip_limiter.allow(client_ip(request)):
        return too_many_requests(ratelimit.LOGIN_WINDOW, "Too many sign-in attempts from this network. Try again later.")
    try:
        user_id = decode_challenge_token(payload.challenge_token)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="This sign-in attempt expired. Start again with your email and password.")
    user = db.get(User, user_id)
    if user is None or not user.is_active or not user.two_factor_enabled or not user.totp_secret:
        raise HTTPException(status_code=401, detail="This sign-in attempt is no longer valid. Start again.")
    code = payload.code.strip().replace("-", "").lower()
    verified = False
    if code.isdigit() and len(code) == 6:
        verified = pyotp.TOTP(user.totp_secret).verify(code, valid_window=1)
    if not verified:
        # Fall back to single-use backup codes (stored hashed, dash-less).
        for row in db.scalars(select(BackupCode).where(BackupCode.user_id == user.id, BackupCode.used_at.is_(None))).all():
            if verify_password(code, row.code_hash):
                row.used_at = utc_now()
                db.commit()
                verified = True
                audit(db, user.id, "security.2fa_backup_code_used")
                break
    if not verified:
        raise HTTPException(status_code=401, detail="Incorrect authentication code.")
    audit(db, user.id, "account.login", "two-step verification")
    token, expires = create_access_token(user.id, user.token_version)
    return {"access_token": token, "expires_in": expires, "user": user_payload(user)}


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
