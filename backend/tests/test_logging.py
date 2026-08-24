from __future__ import annotations

import json
from typing import Any

from app.core.config import Settings
from app.core.logging import configure_logging, get_logger


def test_structured_logging_contract_and_redaction(
    capsys: Any,
    test_environment: None,
) -> None:
    settings = Settings()
    configure_logging(settings)
    secret = "never-log-this"  # noqa: S105 - synthetic redaction sentinel

    get_logger().info(
        "security_test",
        message="Checking redaction",
        authorization=f"Bearer {secret}",
        database_url=f"postgresql://user:{secret}@db/name",
        nested={"api_key": secret, "safe": "visible"},
    )

    output = capsys.readouterr().out
    record = json.loads(output)
    assert secret not in output
    assert record["authorization"] == "[REDACTED]"
    assert record["database_url"] == "[REDACTED]"
    assert record["nested"] == {"api_key": "[REDACTED]", "safe": "visible"}
    assert {
        "timestamp",
        "level",
        "service",
        "environment",
        "event",
        "message",
        "request_id",
        "correlation_id",
    } <= record.keys()
