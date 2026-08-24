from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any]
    request_id: str


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


def documented_error(description: str) -> dict[str, Any]:
    return {"model": ErrorEnvelope, "description": description}
