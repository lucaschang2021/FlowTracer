from __future__ import annotations

from time import perf_counter
from uuid import UUID, uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.context import bind_context, reset_context
from app.core.errors import error_response
from app.core.logging import get_logger

REQUEST_ID_HEADER = "X-Request-ID"


def normalize_request_id(value: str | None) -> str:
    if value is None:
        return str(uuid4())
    try:
        return str(UUID(value))
    except (ValueError, AttributeError):
        return str(uuid4())


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = normalize_request_id(request.headers.get(REQUEST_ID_HEADER))
        tokens = bind_context(request_id=request_id, correlation_id=request_id)
        started = perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception as exc:
                get_logger().error(
                    "unhandled_exception",
                    message="Unhandled application exception",
                    exception_type=type(exc).__name__,
                )
                response = error_response(
                    status_code=500,
                    code="internal_error",
                    message="An internal error occurred",
                )
            response.headers[REQUEST_ID_HEADER] = request_id
            get_logger().info(
                "http_request_completed",
                message="HTTP request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round((perf_counter() - started) * 1000, 3),
            )
            return response
        finally:
            reset_context(tokens)
