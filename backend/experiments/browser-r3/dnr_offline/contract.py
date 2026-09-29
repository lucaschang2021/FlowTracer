"""Offline candidate contract; no runtime imports, networking or entrypoint."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

MOUNT = "/opt/flowtracer-r3-dnr"
FLAGS = [f"--load-extension={MOUNT}", f"--disable-extensions-except={MOUNT}"]
SESSION = "flowtracer-r3-dnr-capability-20260928-01"
MANIFEST = {
    "manifest_version": 3,
    "name": "FlowTracer R3 WS Deny Capability",
    "version": "0.1.0",
    "minimum_chrome_version": "151",
    "permissions": ["declarativeNetRequest", "declarativeNetRequestFeedback", "storage"],
    "background": {"service_worker": "observer.js"},
    "declarative_net_request": {
        "rule_resources": [{"id": "ws_default_deny_v1", "enabled": True, "path": "rules.json"}]
    },
}
RULES = [
    {
        "id": 1,
        "priority": 1,
        "action": {"type": "block"},
        "condition": {"resourceTypes": ["websocket"]},
    }
]
FILES = {"manifest.json", "rules.json", "observer.js", "audit.html", "audit.js"}


class Rejected(RuntimeError):
    """Only safe fixed error codes, never include supplied object/value."""


def check_static(directory: Path, expected: dict[str, str]) -> None:
    actual = {item.name for item in directory.iterdir()}
    if actual != FILES or set(expected) != FILES:
        raise Rejected("extension_files_invalid")
    for name, digest in expected.items():
        item = directory / name
        if item.is_symlink() or not item.is_file():
            raise Rejected("extension_path_invalid")
        if hashlib.sha256(item.read_bytes()).hexdigest() != digest:
            raise Rejected("extension_hash_invalid")
    if json.loads((directory / "manifest.json").read_text()) != MANIFEST:
        raise Rejected("manifest_invalid")
    if json.loads((directory / "rules.json").read_text()) != RULES:
        raise Rejected("rules_invalid")


def check_readback(snapshot: dict, identity: dict) -> None:
    """Model check ONLY; trusted CDP + identity collector not implemented/admitted."""
    extension_id = identity.get("extension_id")
    if not isinstance(extension_id, str) or len(extension_id) != 32:
        raise Rejected("extension_identity_missing")
    if any(char not in "abcdefghijklmnop" for char in extension_id):
        raise Rejected("extension_identity_invalid")
    if not all(
        identity.get(key) is True
        for key in ("hashes_match", "readonly_mount", "unique_extension", "trusted_cdp")
    ):
        raise Rejected("unverified_identity")
    if (
        snapshot.get("extension_id") != extension_id
        or snapshot.get("session") != SESSION
        or snapshot.get("schema_version") != "r3-dnr-audit-v1"
        or snapshot.get("ok") is not True
        or snapshot.get("configured") is not True
        or snapshot.get("fatal") is not None
        or snapshot.get("enabled_rulesets") != ["ws_default_deny_v1"]
        or snapshot.get("dynamic_rules") != []
        or snapshot.get("session_rules") != []
        or snapshot.get("observer_registered") is not True
        or snapshot.get("flushed") is not True
        or snapshot.get("storage_access_level") != "TRUSTED_CONTEXTS"
        or not isinstance(snapshot.get("observer_epoch"), str)
        or not snapshot["observer_epoch"]
    ):
        raise Rejected("readback_invalid")


def fingerprint(actor: str, scheme: str) -> str:
    if actor not in {"page", "worker"} or scheme not in {"ws", "wss"}:
        raise Rejected("association_invalid")
    return hashlib.sha256(
        f"{scheme}://websocket-r3.test:8443/dnr-{actor}-{scheme}".encode()
    ).hexdigest()
