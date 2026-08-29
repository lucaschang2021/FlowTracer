from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.main import create_app

OPENAPI_PATH = Path(__file__).resolve().parents[1] / "openapi" / "flowtracer-alpha-v0.1.json"
EXPECTED_PATHS = {
    "/api/v1/analyses/{analysis_id}/retry",
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/api/v1/auth/refresh",
    "/api/v1/auth/register",
    "/api/v1/bookmarks",
    "/api/v1/bookmarks/{bookmark_id}",
    "/api/v1/collection-runs/{run_id}",
    "/api/v1/collection-runs/{run_id}/items",
    "/api/v1/collection-runs/{run_id}/retry",
    "/api/v1/health/live",
    "/api/v1/health/ready",
    "/api/v1/intelligence",
    "/api/v1/intelligence/{analysis_id}",
    "/api/v1/memory/search",
    "/api/v1/notifications",
    "/api/v1/notifications/read-all",
    "/api/v1/notifications/{notification_id}/read",
    "/api/v1/radars",
    "/api/v1/radars/{radar_id}",
    "/api/v1/radars/{radar_id}/pause",
    "/api/v1/radars/{radar_id}/resume",
    "/api/v1/radars/{radar_id}/sources",
    "/api/v1/radars/{radar_id}/sources/{source_id}",
    "/api/v1/sources",
    "/api/v1/sources/{source_id}",
    "/api/v1/sources/{source_id}/collect",
    "/api/v1/sources/{source_id}/pause",
    "/api/v1/sources/{source_id}/resume",
    "/api/v1/sources/{source_id}/runs",
    "/api/v1/users/me",
}


def _canonical(document: dict[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def test_openapi_snapshot_matches_implementation() -> None:
    expected = OPENAPI_PATH.read_text(encoding="utf-8")
    actual = _canonical(create_app(Settings()).openapi())
    assert actual == expected


def test_openapi_frozen_surface_bearer_and_error_envelope() -> None:
    document = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    assert set(document["paths"]) == EXPECTED_PATHS
    assert document["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    error = document["components"]["schemas"]["ErrorEnvelope"]["properties"]["error"]
    assert error["$ref"].endswith("/ErrorDetail")
    error_fields = document["components"]["schemas"]["ErrorDetail"]["properties"]
    assert set(error_fields) == {"code", "message", "details", "request_id"}

    public = {
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/refresh",
        "/api/v1/auth/register",
        "/api/v1/health/live",
        "/api/v1/health/ready",
    }
    for path, path_item in document["paths"].items():
        for operation in path_item.values():
            if not isinstance(operation, dict) or "responses" not in operation:
                continue
            if path not in public:
                assert operation["responses"]["401"]["content"]["application/json"]["schema"][
                    "$ref"
                ].endswith("/ErrorEnvelope")
