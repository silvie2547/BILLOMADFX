import re
from typing import Self
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RegisterRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value

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
        # Standard trading-platform policy: length plus upper/lower/digit.
        problems = []
        if not re.search(r"[A-Z]", value):
            problems.append("an uppercase letter")
        if not re.search(r"[a-z]", value):
            problems.append("a lowercase letter")
        if not re.search(r"\d", value):
            problems.append("a number")
        if problems:
            raise ValueError(f"Password must contain {', '.join(problems)}")
        local_part = str(info.data.get("email", "")).split("@")[0]
        if local_part and local_part.lower() in value.lower():
            raise ValueError("Password must not contain your email address")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str


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
