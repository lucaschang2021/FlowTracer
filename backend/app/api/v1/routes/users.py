from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_session
from app.models.entities import User
from app.schemas.auth import UpdateUserRequest, UserResponse
from app.schemas.errors import documented_error

router = APIRouter(
    responses={
        401: documented_error("Invalid access token"),
        422: documented_error("Invalid request"),
    }
)


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UpdateUserRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.profile is not None:
        user.profile = payload.profile
    await session.commit()
    await session.refresh(user)
    return user
