import re
from typing import Self
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _normalize_email(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValueError("Enter a valid email address")
    return value


def _validate_password_strength(value: str, email: str | None) -> str:
    """Standard trading-platform policy: length plus upper/lower/digit."""
    problems = []
    if not re.search(r"[A-Z]", value):
        problems.append("an uppercase letter")
    if not re.search(r"[a-z]", value):
        problems.append("a lowercase letter")
    if not re.search(r"\d", value):
        problems.append("a number")
    if problems:
        raise ValueError(f"Password must contain {', '.join(problems)}")
    local_part = str(email or "").split("@")[0]
    if local_part and local_part.lower() in value.lower():
        raise ValueError("Password must not contain your email address")
    return value


class RegisterRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Display name cannot be blank")
        return value

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str, info) -> str:
        return _validate_password_strength(value, info.data.get("email"))


class LoginRequest(BaseModel):
    email: str
    password: str


class VerifyOtpRequest(BaseModel):
    email: str = Field(max_length=254)
    code: str = Field(min_length=4, max_length=12)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("code")
    @classmethod
    def clean_code(cls, value: str) -> str:
        value = value.strip().replace(" ", "")
        if not value.isdigit():
            raise ValueError("The code is a number")
        return value


class ResendOtpRequest(BaseModel):
    email: str = Field(max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)


class ResetPasswordRequest(BaseModel):
    email: str = Field(max_length=254)
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("code")
    @classmethod
    def clean_code(cls, value: str) -> str:
        value = value.strip().replace(" ", "")
        if not value.isdigit():
            raise ValueError("The code is a number")
        return value

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: str, info) -> str:
        return _validate_password_strength(value, info.data.get("email"))


class SignUpResponse(BaseModel):
    """Register response: a verification code is sent to the email address.

    In "display mode" (no SMTP configured on this deployment) `otp` carries
    the code so the client can show it; otherwise it is None.
    """
    otp_required: bool = True
    email: str
    delivery: str  # "email" | "display"
    otp: str | None = None
    expires_in_minutes: int
    message: str


class TwoFactorChallengeResponse(BaseModel):
    totp_required: bool = True
    challenge_token: str
    expires_in: int


class TwoFactorSetupResponse(BaseModel):
    otpauth_uri: str
    qr_data_uri: str
    secret: str


class TwoFactorConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=12)

    @field_validator("code")
    @classmethod
    def clean_code(cls, value: str) -> str:
        value = value.strip().replace(" ", "")
        if not value:
            raise ValueError("Enter the 6-digit code from your authenticator app")
        return value


class TwoFactorDisableRequest(BaseModel):
    password: str


class TwoFactorLoginRequest(BaseModel):
    challenge_token: str
    code: str = Field(min_length=4, max_length=20)

    @field_validator("code")
    @classmethod
    def clean_code(cls, value: str) -> str:
        value = value.strip().replace(" ", "")
        if not value:
            raise ValueError("Enter your authentication code")
        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    display_name: str
    role: str
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class AccessTokenResponse(BaseModel):
    """Token-only response used by refresh (the client already knows who it is)."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RiskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    daily_loss_limit_pct: float
    weekly_loss_limit_pct: float
    max_drawdown_pct: float
    max_spread_points: int
    is_halted: bool


class RiskUpdateRequest(BaseModel):
    daily_loss_limit_pct: float = Field(ge=0.1, le=2.0)
    weekly_loss_limit_pct: float = Field(ge=0.1, le=5.0)
    max_drawdown_pct: float = Field(ge=0.1, le=10.0)
    max_spread_points: int = Field(ge=1, le=40)

    @model_validator(mode="after")
    def validate_loss_limit_order(self) -> Self:
        if self.daily_loss_limit_pct > self.weekly_loss_limit_pct:
            raise ValueError("Daily loss limit cannot exceed the weekly loss limit")
        if self.weekly_loss_limit_pct > self.max_drawdown_pct:
            raise ValueError("Weekly loss limit cannot exceed the maximum drawdown limit")
        return self


class HaltResponse(BaseModel):
    is_halted: bool
    message: str
