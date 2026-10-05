from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.composition import build_opportunity_dependency, with_database
from app.core.config import get_settings
from app.services.opportunity_evaluation import dispatch_pending_opportunities
from app.tasks.celery_app import celery_app


async def _dispatch() -> int:
    settings = get_settings()
    provider = build_opportunity_dependency(settings)

    async def operation(factory: async_sessionmaker[AsyncSession]) -> int:
        return await dispatch_pending_opportunities(factory, provider, settings)

    return await with_database(settings, operation)


@celery_app.task(name="flowtracer.tasks.opportunity.dispatch_opportunity_evaluations")  # type: ignore[untyped-decorator]
def dispatch_opportunity_evaluations() -> int:
    return int(asyncio.run(_dispatch()))
