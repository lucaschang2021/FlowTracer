from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    display_name: str
    profile: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int = 900


class AuthResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


class RefreshResponse(BaseModel):
    tokens: TokenResponse


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class UpdateUserRequest(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=80)
    profile: dict[str, Any] | None = None

    @model_validator(mode="after")
    def require_change(self) -> UpdateUserRequest:
        if self.display_name is None and self.profile is None:
            raise ValueError("at least one field is required")
        return self
