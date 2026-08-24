from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import install_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.db.session import create_database_engine
from app.services.readiness import ReadinessService, build_readiness_service


def create_app(
    settings: Settings | None = None,
    readiness_service: ReadinessService | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)
    logger = get_logger()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine: AsyncEngine | None = None
        redis_client: Redis | None = None
        if readiness_service is None:
            engine = create_database_engine(resolved_settings)
            redis_client = Redis.from_url(
                resolved_settings.redis_url.get_secret_value(),
                decode_responses=True,
            )
            application.state.readiness_service = build_readiness_service(
                engine,
                redis_client,
                resolved_settings.dependency_timeout_seconds,
            )
        logger.info("application_started", message="FlowTracer API started")
        try:
            yield
        finally:
            if redis_client is not None:
                await redis_client.aclose()
            if engine is not None:
                await engine.dispose()
            logger.info("application_stopped", message="FlowTracer API stopped")

    application = FastAPI(
        title="FlowTracer API",
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.readiness_service = readiness_service
    application.add_middleware(RequestContextMiddleware)
    install_exception_handlers(application)
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
