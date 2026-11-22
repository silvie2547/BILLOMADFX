"""One-time codes for sign-up verification and password resets.

A code is a cryptographically random 6-digit number. Only its Argon2 hash is
stored. Issue semantics:

- issuing a new code for the same user+purpose invalidates the previous one;
- a code expires otp_ttl_minutes (20 minutes) after issuance;
- a code stops accepting attempts after otp_max_attempts wrong entries;
- a correct code is consumed immediately (single use).
"""
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .config import settings
from .models import OtpCode, User
from .security import hash_password, verify_password

PURPOSE_SIGNUP = "signup_verification"
PURPOSE_RESET = "password_reset"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC (as everywhere else)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _new_code() -> str:
    return f"{secrets.randbelow(10 ** settings.otp_length):0{settings.otp_length}d}"


def issue_otp(db: Session, user: User, purpose: str) -> str:
    """Invalidate any active code for this user+purpose and return a fresh one."""
    db.execute(
        update(OtpCode)
        .where(
            OtpCode.user_id == user.id,
            OtpCode.purpose == purpose,
            OtpCode.consumed_at.is_(None),
        )
        .values(consumed_at=_utc_now())
    )
    code = _new_code()
    db.add(
        OtpCode(
            user_id=user.id,
            purpose=purpose,
            code_hash=hash_password(code),
            expires_at=_utc_now() + timedelta(minutes=settings.otp_ttl_minutes),
        )
    )
    db.commit()
    return code


def verify_otp(db: Session, user: User, purpose: str, code: str) -> tuple[bool, str]:
    """Check a one-time code. Returns (ok, reason); consumes it on success."""
    row = db.scalars(
        select(OtpCode)
        .where(
            OtpCode.user_id == user.id,
            OtpCode.purpose == purpose,
            OtpCode.consumed_at.is_(None),
        )
        .order_by(OtpCode.created_at.desc(), OtpCode.id.desc())
    ).first()
    if row is None:
        return False, "No active code. Request a new one."
    if _as_aware(row.expires_at) < _utc_now():
        row.consumed_at = _utc_now()
        db.commit()
        ttl = settings.otp_ttl_minutes
        return False, f"This code expired {ttl} minutes after it was sent. Request a new one."
    if verify_password(code, row.code_hash):
        row.consumed_at = _utc_now()
        db.commit()
        return True, ""
    row.attempts += 1
    reason: str
    if row.attempts >= settings.otp_max_attempts:
        row.consumed_at = _utc_now()
        reason = "Too many incorrect attempts. Request a new code."
    else:
        remaining = settings.otp_max_attempts - row.attempts
        reason = f"Incorrect code. {remaining} attempt{'s' if remaining != 1 else ''} remaining."
    db.commit()
    return False, reason
