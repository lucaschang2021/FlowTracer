from fastapi import APIRouter, Request

from app.core.errors import AppError
from app.schemas.health import LivenessResponse, ReadinessResponse
from app.services.readiness import ReadinessService

router = APIRouter()


@router.get("/live", response_model=LivenessResponse)
async def liveness(request: Request) -> LivenessResponse:
    settings = request.app.state.settings
    return LivenessResponse(
        status="ok",
        service="flowtracer-api",
        version=settings.app_version,
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(request: Request) -> ReadinessResponse:
    service: ReadinessService = request.app.state.readiness_service
    checks = await service.check()
    if checks.database != "ok" or checks.redis != "ok":
        raise AppError(
            status_code=503,
            code="service_not_ready",
            message="Service dependencies are not ready",
            details={"checks": checks.model_dump()},
        )
    return ReadinessResponse(status="ready", checks=checks)
