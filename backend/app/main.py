from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.composition import api_dependencies, build_embedding_dependency
from app.core.config import Settings, get_settings
from app.core.errors import install_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.services.readiness import ReadinessService


def create_app(
    settings: Settings | None = None,
    readiness_service: ReadinessService | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)
    logger = get_logger()
    embedding_provider = build_embedding_dependency(resolved_settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        try:
            async with api_dependencies(
                resolved_settings,
                readiness_service=readiness_service,
                embedding_provider=embedding_provider,
            ) as dependencies:
                if dependencies.session_factory is not None:
                    application.state.session_factory = dependencies.session_factory
                application.state.redis_client = dependencies.redis_client
                application.state.event_publisher = dependencies.event_publisher
                application.state.readiness_service = dependencies.readiness_service
                application.state.embedding_provider = dependencies.embedding_provider
                logger.info("application_started", message="FlowTracer API started")
                yield
        finally:
            logger.info("application_stopped", message="FlowTracer API stopped")

    application = FastAPI(
        title="FlowTracer API",
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.readiness_service = readiness_service
    application.state.redis_client = None
    application.state.event_publisher = None
    application.state.embedding_provider = embedding_provider
    application.add_middleware(RequestContextMiddleware)
    install_exception_handlers(application)
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
