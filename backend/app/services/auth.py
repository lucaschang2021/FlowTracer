from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    create_refresh_value,
    hash_password,
    hash_refresh_value,
    parse_refresh_token,
    password_needs_rehash,
    verify_password,
)
from app.models.entities import RefreshToken, User
from app.schemas.auth import TokenResponse

INVALID_CREDENTIALS = AppError(
    status_code=401, code="invalid_credentials", message="Invalid credentials"
)
INVALID_REFRESH = AppError(
    status_code=401, code="invalid_refresh_token", message="Invalid refresh token"
)


def _new_tokens(
    user: User, settings: Settings, now: datetime
) -> tuple[TokenResponse, RefreshToken]:
    token_id = uuid.uuid4()
    refresh_value = create_refresh_value(token_id)
    record = RefreshToken(
        id=token_id,
        user_id=user.id,
        token_hash=hash_refresh_value(refresh_value),
        expires_at=now + timedelta(days=settings.refresh_token_ttl_days),
    )
    response = TokenResponse(
        access_token=create_access_token(user.id, settings, now),
        refresh_token=refresh_value,
        expires_in=settings.access_token_ttl_minutes * 60,
    )
    return response, record


async def register_user(
    session: AsyncSession,
    settings: Settings,
    *,
    email: str,
    password: str,
    display_name: str,
) -> tuple[User, TokenResponse]:
    user = User(email=email, password_hash=hash_password(password), display_name=display_name)
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise AppError(
            status_code=409,
            code="email_already_registered",
            message="Email is already registered",
        ) from None
    tokens, record = _new_tokens(user, settings, datetime.now(UTC))
    session.add(record)
    await session.commit()
    await session.refresh(user)
    return user, tokens


async def login_user(
    session: AsyncSession,
    settings: Settings,
    *,
    email: str,
    password: str,
) -> tuple[User, TokenResponse]:
    user = await session.scalar(
        select(User).where(User.email == email, User.deleted_at.is_(None), User.is_active.is_(True))
    )
    if user is None or not verify_password(user.password_hash, password):
        raise INVALID_CREDENTIALS
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    tokens, record = _new_tokens(user, settings, datetime.now(UTC))
    session.add(record)
    await session.commit()
    await session.refresh(user)
    return user, tokens


async def refresh_tokens(
    session: AsyncSession,
    settings: Settings,
    *,
    refresh_value: str,
) -> TokenResponse:
    try:
        token_id = parse_refresh_token(refresh_value)
    except ValueError:
        raise INVALID_REFRESH from None
    record = await session.scalar(
        select(RefreshToken).where(RefreshToken.id == token_id).with_for_update()
    )
    now = datetime.now(UTC)
    if (
        record is None
        or record.revoked_at is not None
        or record.expires_at <= now
        or not secrets.compare_digest(record.token_hash, hash_refresh_value(refresh_value))
    ):
        await session.rollback()
        raise INVALID_REFRESH
    user = await session.scalar(
        select(User).where(
            User.id == record.user_id, User.deleted_at.is_(None), User.is_active.is_(True)
        )
    )
    if user is None:
        await session.rollback()
        raise INVALID_REFRESH
    tokens, replacement = _new_tokens(user, settings, now)
    record.revoked_at = now
    session.add(replacement)
    await session.flush()
    record.replaced_by_token_id = replacement.id
    await session.commit()
    return tokens


async def logout_user(session: AsyncSession, *, refresh_value: str) -> None:
    try:
        token_id = parse_refresh_token(refresh_value)
    except ValueError:
        return
    record = await session.scalar(
        select(RefreshToken).where(RefreshToken.id == token_id).with_for_update()
    )
    if (
        record is not None
        and record.revoked_at is None
        and secrets.compare_digest(record.token_hash, hash_refresh_value(refresh_value))
    ):
        record.revoked_at = datetime.now(UTC)
        await session.commit()
    else:
        await session.rollback()
