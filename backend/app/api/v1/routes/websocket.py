from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket
from redis.exceptions import RedisError
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.core.security import (
    AccessTokenClaims,
    InvalidAccessTokenError,
    decode_access_token_claims,
)
from app.models.entities import User
from app.schemas.events import EventEnvelope
from app.services.events import channel_for_user

router = APIRouter()
WEBSOCKET_QUEUE_LIMIT = 100


class WebSocketBackpressureError(RuntimeError):
    pass


def enqueue_event(queue: asyncio.Queue[str], payload: str) -> None:
    try:
        queue.put_nowait(payload)
    except asyncio.QueueFull:
        raise WebSocketBackpressureError from None


async def _authenticate(websocket: WebSocket) -> AccessTokenClaims | None:
    authorization = websocket.headers.get("authorization")
    if authorization is None:
        return None
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token:
        return None
    try:
        claims = decode_access_token_claims(token, websocket.app.state.settings)
    except InvalidAccessTokenError:
        return None
    factory = websocket.app.state.session_factory
    async with factory() as session:
        user_id = await session.scalar(
            select(User.id).where(
                User.id == claims.user_id,
                User.deleted_at.is_(None),
                User.is_active.is_(True),
            )
        )
        await session.rollback()
    return claims if user_id is not None else None


async def _read_pubsub(pubsub: object, queue: asyncio.Queue[str]) -> str:
    async for message in pubsub.listen():  # type: ignore[attr-defined]
        if message.get("type") != "message":
            continue
        payload = message.get("data")
        if not isinstance(payload, (str, bytes)):
            raise RedisError("invalid pubsub event")
        event = EventEnvelope.model_validate_json(payload)
        enqueue_event(queue, event.model_dump_json())
    return "redis_unavailable"


async def _send_events(websocket: WebSocket, queue: asyncio.Queue[str]) -> str:
    try:
        while True:
            await websocket.send_text(await queue.get())
    except WebSocketDisconnect:
        return "disconnected"


async def _wait_disconnect(websocket: WebSocket) -> str:
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return "disconnected"
    except WebSocketDisconnect:
        return "disconnected"


async def _wait_expiry(expires_at: datetime) -> str:
    remaining = max(0.0, (expires_at - datetime.now(UTC)).total_seconds())
    await asyncio.sleep(remaining)
    return "expired"


@router.websocket("")
async def websocket_events(websocket: WebSocket) -> None:
    claims = await _authenticate(websocket)
    if claims is None:
        await websocket.accept()
        await websocket.close(code=4401)
        return
    redis_client = getattr(websocket.app.state, "redis_client", None)
    if redis_client is None:
        await websocket.accept()
        await websocket.close(code=1013)
        return
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=WEBSOCKET_QUEUE_LIMIT)
    pubsub = redis_client.pubsub()
    try:
        await pubsub.subscribe(channel_for_user(claims.user_id))
    except RedisError:
        await pubsub.aclose()
        await websocket.accept()
        await websocket.close(code=1013)
        return
    await websocket.accept()
    tasks = {
        asyncio.create_task(_read_pubsub(pubsub, queue)),
        asyncio.create_task(_send_events(websocket, queue)),
        asyncio.create_task(_wait_disconnect(websocket)),
        asyncio.create_task(_wait_expiry(claims.expires_at)),
    }
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        reason = "disconnected"
        for task in done:
            try:
                reason = task.result()
            except (RedisError, WebSocketBackpressureError, ValueError):
                reason = "unavailable"
        for task in pending:
            task.cancel()
        if reason == "expired":
            await websocket.close(code=4401)
        elif reason not in {"disconnected"}:
            await websocket.close(code=1013)
    finally:
        for task in tasks:
            task.cancel()
        try:
            await pubsub.unsubscribe(channel_for_user(claims.user_id))
            await pubsub.aclose()
        except RedisError:
            pass
