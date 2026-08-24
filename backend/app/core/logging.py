from __future__ import annotations

import io
import logging
import sys
from collections.abc import Mapping, MutableMapping
from typing import Any, TextIO, cast

import structlog

from app.core.config import Settings
from app.core.context import correlation_id_context, request_id_context

SENSITIVE_KEY_PARTS = (
    "authorization",
    "password",
    "token",
    "api_key",
    "secret",
    "database_url",
    "redis_url",
    "content",
    "body",
)

_service = "flowtracer-api"
_environment = "unknown"


class DynamicStdout(io.TextIOBase):
    """A stream proxy that follows capture and worker stdout changes."""

    def write(self, message: str) -> int:
        return sys.stdout.write(message)

    def flush(self) -> None:
        sys.stdout.flush()


def _redact(value: Any, key: str = "") -> Any:
    if any(part in key.lower() for part in SENSITIVE_KEY_PARTS):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {
            str(child_key): _redact(child_value, str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value)
    return value


def add_contract_fields(
    _logger: Any,
    method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    event_dict.setdefault("level", method_name.upper())
    event_dict.setdefault("service", _service)
    event_dict.setdefault("environment", _environment)
    event_dict.setdefault("message", str(event_dict.get("event", "")))
    event_dict.setdefault("request_id", request_id_context.get())
    event_dict.setdefault("correlation_id", correlation_id_context.get())
    return dict(_redact(event_dict))


def configure_logging(settings: Settings, service: str = "flowtracer-api") -> None:
    global _environment, _service
    _environment = settings.environment
    _service = service
    logging.basicConfig(
        stream=DynamicStdout(),
        level=settings.log_level,
        format="%(message)s",
        force=True,
    )
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
            add_contract_fields,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[settings.log_level]
        ),
        logger_factory=structlog.PrintLoggerFactory(file=cast(TextIO, DynamicStdout())),
        cache_logger_on_first_use=False,
    )


def get_logger() -> structlog.stdlib.BoundLogger:
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger())
