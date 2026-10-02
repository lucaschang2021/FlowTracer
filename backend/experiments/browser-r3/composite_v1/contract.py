"""Closed offline contract; no import-time I/O or runtime dependencies."""

from __future__ import annotations

import json
import math
import re

SCHEMA = "r3-composite-v1"
POLICY = "r3-composite-policy-v1"
CONTROL = "335c6a2da418b2d3b2c4c70b59ee3d20d08c08cb"
PARENT = "fba06dfa20bde0385d2e6a36408b11ffca48809e"
FILES = (
    "contract.py",
    "fixture.py",
    "collector.py",
    "harness.py",
    "validator.py",
    "supervisor.py",
    "test_composite.py",
    "execution-inputs.json",
    "execution-plan.json",
    "README.md",
)
MATRIX = {
    "navigation": ("navigation", "page", "allow", None),
    "redirect-start": ("redirect", "page", "allow", None),
    "redirect-end": ("redirect", "page", "allow", None),
    "iframe": ("iframe", "frame", "allow", None),
    "script": ("script", "page", "allow", None),
    "xhr": ("xhr", "page", "allow", None),
    "fetch": ("fetch", "page", "allow", None),
    "worker-script": ("script", "dedicated_worker", "allow", None),
    "page-ws": ("websocket", "page", "deny", None),
    "worker-ws": ("websocket", "dedicated_worker", "deny", None),
    "download": ("download", "page", "deny", None),
    "popup": ("popup", "page", "deny", None),
    "sw-register": ("service_worker_register", "page", "deny", None),
    "sw-update": ("service_worker_update", "service_worker", "deny", "sw-register"),
    "sw-fetch": ("service_worker_fetch", "service_worker", "deny", "sw-register"),
}
LIMITS = {"requests": 20, "pages": 4, "bytes": 5242880}


class Rejected(ValueError):
    """Only closed safe codes cross the boundary."""


def reject(code: str) -> None:
    raise Rejected(code)


def object_fields(value: object, fields: set[str]) -> dict:
    if type(value) is not dict or set(value) != fields:
        reject("invalid_fields")
    return value


def identifier(value: object) -> str:
    if type(value) is not str or re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", value) is None:
        reject("invalid_identifier")
    return value


def digest(value: object, size: int = 64) -> str:
    if type(value) is not str or re.fullmatch(rf"[a-f0-9]{{{size}}}", value) is None:
        reject("invalid_digest")
    return value


def integer(value: object) -> int:
    if type(value) is not int or not 0 <= value <= 5242880:
        reject("invalid_integer")
    return value


def strict_json(raw: bytes) -> dict:
    if type(raw) is not bytes or len(raw) > 262144:
        reject("invalid_json")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                reject("duplicate_key")
            result[key] = value
        return result

    def constant(_):
        reject("non_finite")

    def number(text):
        value = float(text)
        if not math.isfinite(value):
            reject("non_finite")
        return value

    try:
        value = json.loads(
            raw, object_pairs_hook=pairs, parse_constant=constant, parse_float=number
        )
    except (ValueError, UnicodeError, RecursionError):
        reject("invalid_json")
    if type(value) is not dict:
        reject("invalid_json")
    return value


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
