from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
)
from app.schemas.errors import documented_error
from app.services.auth import login_user, logout_user, refresh_tokens, register_user

router = APIRouter()


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: documented_error("Email is already registered"),
        422: documented_error("Invalid request"),
    },
)
async def register(
    payload: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    user, tokens = await register_user(
        session,
        request.app.state.settings,
        email=str(payload.email),
        password=payload.password,
        display_name=payload.display_name,
    )
    return AuthResponse(user=user, tokens=tokens)


@router.post(
    "/login",
    response_model=AuthResponse,
    responses={
        401: documented_error("Invalid credentials"),
        422: documented_error("Invalid request"),
    },
)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    user, tokens = await login_user(
        session,
        request.app.state.settings,
        email=str(payload.email),
        password=payload.password,
    )
    return AuthResponse(user=user, tokens=tokens)


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    responses={
        401: documented_error("Invalid refresh token"),
        422: documented_error("Invalid request"),
    },
)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> RefreshResponse:
    tokens = await refresh_tokens(
        session, request.app.state.settings, refresh_value=payload.refresh_token
    )
    return RefreshResponse(tokens=tokens)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={422: documented_error("Invalid request")},
)
async def logout(
    payload: LogoutRequest,
    session: AsyncSession = Depends(get_session),
) -> Response:
    await logout_user(session, refresh_value=payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
