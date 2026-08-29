from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = BACKEND_ROOT / "openapi" / "flowtracer-alpha-v0.1.json"
SCHEMA_ENVIRONMENT = {
    "FLOWTRACER_ENV": "test",
    "FLOWTRACER_LOG_LEVEL": "INFO",
    "FLOWTRACER_APP_VERSION": "0.1.0",
    "FLOWTRACER_API_HOST": "127.0.0.1",
    "FLOWTRACER_API_PORT": "8000",
    "DATABASE_URL": "postgresql+asyncpg://flowtracer:placeholder@localhost:5432/flowtracer_test",
    "TEST_DATABASE_URL": (
        "postgresql+asyncpg://flowtracer:placeholder@localhost:5432/flowtracer_test"
    ),
    "REDIS_URL": "redis://localhost:6379/15",
    "CELERY_BROKER_URL": "redis://localhost:6379/15",
    "CELERY_RESULT_BACKEND": "redis://localhost:6379/14",
    "JWT_SECRET": "openapi-export-placeholder-at-least-32-bytes",
    "ACCESS_TOKEN_TTL_MINUTES": "15",
    "REFRESH_TOKEN_TTL_DAYS": "30",
    "JWT_ISSUER": "flowtracer-api",
    "JWT_AUDIENCE": "flowtracer-desktop",
    "AI_PROVIDER": "fake",
    "AI_MODEL": "flowtracer-fake-v1",
    "AI_INPUT_COST_PER_MILLION": "0",
    "AI_OUTPUT_COST_PER_MILLION": "0",
    "EMBEDDING_PROVIDER": "fake",
    "EMBEDDING_MODEL": "flowtracer-fake-embedding-v1",
    "EMBEDDING_INPUT_COST_PER_MILLION": "0",
    "EMBEDDING_CHUNK_SIZE": "1200",
    "EMBEDDING_CHUNK_OVERLAP": "200",
}


def build_openapi_document() -> dict[str, Any]:
    for key, value in SCHEMA_ENVIRONMENT.items():
        os.environ[key] = value
    sys.path.insert(0, str(BACKEND_ROOT))

    from app.core.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app().openapi()


def serialize_openapi(document: dict[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the frozen FlowTracer Alpha OpenAPI schema"
    )
    parser.add_argument("--check", action="store_true", help="fail if the snapshot is stale")
    parser.add_argument("--output", type=Path, default=OPENAPI_PATH)
    arguments = parser.parse_args()
    rendered = serialize_openapi(build_openapi_document())

    if arguments.check:
        if (
            not arguments.output.exists()
            or arguments.output.read_text(encoding="utf-8") != rendered
        ):
            raise SystemExit("OpenAPI snapshot is stale; run scripts/export_openapi.py")
        return

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(rendered, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
