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
