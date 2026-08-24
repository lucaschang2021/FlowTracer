from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import AppError
from app.core.security import InvalidAccessTokenError, decode_access_token
from app.models.entities import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    error = AppError(
        status_code=401,
        code="invalid_access_token",
        message="Invalid access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise error
    try:
        user_id = decode_access_token(credentials.credentials, request.app.state.settings)
    except InvalidAccessTokenError:
        raise error from None
    user = await session.scalar(
        select(User).where(User.id == user_id, User.deleted_at.is_(None), User.is_active.is_(True))
    )
    if user is None:
        raise error
    return user
