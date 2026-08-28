from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type

from app.core.config import Settings

PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)


class InvalidAccessTokenError(ValueError):
    pass


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: uuid.UUID
    expires_at: datetime


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return PASSWORD_HASHER.check_needs_rehash(password_hash)


def create_access_token(user_id: uuid.UUID, settings: Settings, now: datetime | None = None) -> str:
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.access_token_ttl_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "jti": str(uuid.uuid4()),
        "type": "access",
        "iat": issued_at,
        "nbf": issued_at,
        "exp": expires_at,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256")


def decode_access_token_claims(token: str, settings: Settings) -> AccessTokenClaims:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "jti", "type", "iat", "nbf", "exp", "iss", "aud"]},
        )
        if payload["type"] != "access":
            raise InvalidAccessTokenError
        uuid.UUID(str(payload["jti"]))
        expires_at = datetime.fromtimestamp(float(payload["exp"]), tz=UTC)
        return AccessTokenClaims(user_id=uuid.UUID(str(payload["sub"])), expires_at=expires_at)
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise InvalidAccessTokenError from exc


def decode_access_token(token: str, settings: Settings) -> uuid.UUID:
    return decode_access_token_claims(token, settings).user_id


def create_refresh_value(token_id: uuid.UUID) -> str:
    return f"{token_id}.{secrets.token_urlsafe(32)}"


def hash_refresh_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_refresh_token(value: str) -> uuid.UUID:
    try:
        selector, secret = value.split(".", maxsplit=1)
        token_id = uuid.UUID(selector)
        if not secret:
            raise ValueError
        return token_id
    except (ValueError, AttributeError) as exc:
        raise ValueError("invalid refresh token") from exc
