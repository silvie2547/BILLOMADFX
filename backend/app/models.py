from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(16), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Incremented on logout/password change: every JWT carries the version it
    # was issued with, so bumping this value instantly revokes all older tokens.
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    # Email ownership is proven with a one-time code sent to the address.
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # Two-step authentication (TOTP via authenticator app). Backup codes live
    # in the backup_codes table.
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    risk_settings: Mapped["RiskSettings"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class RiskSettings(Base):
    __tablename__ = "risk_settings"
    __table_args__ = (UniqueConstraint("user_id", name="uq_risk_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    daily_loss_limit_pct: Mapped[float] = mapped_column(Float, default=2.0)
    weekly_loss_limit_pct: Mapped[float] = mapped_column(Float, default=5.0)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, default=10.0)
    max_spread_points: Mapped[int] = mapped_column(Integer, default=40)
    is_halted: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    user: Mapped[User] = relationship(back_populates="risk_settings")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class OtpCode(Base):
    """One-time codes for sign-up verification and password resets.

    Only the hash of the code is stored. Codes expire 20 minutes after they
    are issued, are invalidated when re-issued, and stop accepting attempts
    after otp_max_attempts wrong entries.
    """
    __tablename__ = "otp_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(32), index=True)  # signup_verification | password_reset
    code_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class BackupCode(Base):
    """Single-use recovery codes issued when 2FA is enabled."""
    __tablename__ = "backup_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(255))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
