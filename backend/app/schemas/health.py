from typing import Literal

from pydantic import BaseModel

DependencyStatus = Literal["ok", "unavailable", "timeout"]


class LivenessResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["flowtracer-api"]
    version: str


class ReadinessChecks(BaseModel):
    database: DependencyStatus
    redis: DependencyStatus


class ReadinessResponse(BaseModel):
    status: Literal["ready"]
    checks: ReadinessChecks
