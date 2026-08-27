from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_session
from app.models.entities import User
from app.providers.embedding import build_embedding_provider
from app.schemas.errors import documented_error
from app.schemas.memory import (
    BookmarkCreate,
    BookmarkItem,
    BookmarkPage,
    BookmarkUpdate,
    MemorySearchRequest,
    MemorySearchResponse,
)
from app.services import memory

bookmark_router = APIRouter(
    responses={
        401: documented_error("Invalid access token"),
        404: documented_error("Resource not found"),
        409: documented_error("Bookmark already exists"),
        422: documented_error("Invalid request"),
    }
)


@bookmark_router.post("", response_model=BookmarkItem, status_code=status.HTTP_201_CREATED)
async def create_bookmark(
    payload: BookmarkCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    bookmark = await memory.create_bookmark(
        session, user_id=user.id, document_id=payload.document_id, note=payload.note
    )
    return await memory.bookmark_data(session, bookmark)


@bookmark_router.get("", response_model=BookmarkPage)
async def list_bookmarks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BookmarkPage:
    items, total = await memory.list_bookmarks(
        session, user_id=user.id, page=page, page_size=page_size
    )
    return BookmarkPage.model_validate(
        {"items": items, "page": page, "page_size": page_size, "total": total}
    )


@bookmark_router.patch("/{bookmark_id}", response_model=BookmarkItem)
async def update_bookmark(
    bookmark_id: UUID,
    payload: BookmarkUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    bookmark = await memory.update_bookmark(
        session, user_id=user.id, bookmark_id=bookmark_id, note=payload.note
    )
    return await memory.bookmark_data(session, bookmark)


@bookmark_router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bookmark(
    bookmark_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await memory.delete_bookmark(session, user_id=user.id, bookmark_id=bookmark_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


memory_router = APIRouter(
    responses={
        401: documented_error("Invalid access token"),
        404: documented_error("Resource not found"),
        422: documented_error("Invalid request"),
        502: documented_error("Embedding output invalid"),
        503: documented_error("Embedding provider unavailable"),
    }
)


@memory_router.post("/search", response_model=MemorySearchResponse)
async def search_memory(
    payload: MemorySearchRequest,
    request: Request,
    user: User = Depends(get_current_user),
) -> MemorySearchResponse:
    settings = request.app.state.settings
    provider = getattr(request.app.state, "embedding_provider", None)
    if provider is None:
        provider = build_embedding_provider(settings)
    items = await memory.search_memory(
        request.app.state.session_factory,
        user_id=user.id,
        query=payload.query,
        top_k=payload.top_k,
        radar_id=payload.radar_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
        bookmarked_only=payload.bookmarked_only,
        provider=provider,
        settings=settings,
    )
    return MemorySearchResponse(items=items, query=payload.query, top_k=payload.top_k)
