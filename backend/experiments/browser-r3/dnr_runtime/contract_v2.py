"""Observation v2, never a rule-match timestamp or a real-session admission."""

import re

from contract import FLAGS, MANIFEST, MOUNT, RULES, SESSION, Rejected, check_static, fingerprint

__all__ = [
    "FLAGS",
    "MANIFEST",
    "MOUNT",
    "RULES",
    "SESSION",
    "Rejected",
    "check_static",
    "fingerprint",
]

AUDIT_SCHEMA = "r3-dnr-audit-v2"
RECEIPT_SCHEMA = "r3-dnr-receipt-v2"
TIMESTAMP_SOURCE = "trusted_observer_callback_epoch_ms"
RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "session",
        "extension_id",
        "ruleset_id",
        "rule_id",
        "action",
        "resource_type",
        "request_id",
        "timestamp",
        "timestamp_source",
        "sequence",
        "observer_epoch",
        "safe_request_fingerprint",
        "tab_id",
        "frame_id",
        "document_id",
        "initiator",
        "initiator_note",
    }
)
ARM_FINGERPRINTS = frozenset(
    fingerprint(actor, scheme) for actor in ("page", "worker") for scheme in ("ws", "wss")
)


def epoch_ms(value):
    # Native Date.now(): integral, finite, positive epoch milliseconds.
    return type(value) is int and 10**12 <= value <= 2**53 - 1


def receipt_identity(row, extension_id, epoch, ordinal):
    if (
        type(row) is not dict
        or set(row) != RECEIPT_FIELDS
        or any(
            type(row[key]) is not str
            for key in (
                "schema_version",
                "session",
                "extension_id",
                "ruleset_id",
                "action",
                "resource_type",
                "request_id",
                "timestamp_source",
                "observer_epoch",
                "safe_request_fingerprint",
                "initiator_note",
            )
        )
        or row["schema_version"] != RECEIPT_SCHEMA
        or row["timestamp_source"] != TIMESTAMP_SOURCE
        or not epoch_ms(row["timestamp"])
        or type(row["sequence"]) is not int
        or row["sequence"] != ordinal
        or row["session"] != SESSION
        or row["extension_id"] != extension_id
        or row["observer_epoch"] != epoch
        or row["ruleset_id"] != "ws_default_deny_v1"
        or type(row["rule_id"]) is not int
        or row["rule_id"] != 1
        or row["action"] != "block"
        or row["resource_type"] != "websocket"
        or not row["request_id"]
        or row["safe_request_fingerprint"] not in ARM_FINGERPRINTS
        or any(row[key] is not None and type(row[key]) is not int for key in ("tab_id", "frame_id"))
        or (row["document_id"] is not None and type(row["document_id"]) is not str)
        or row["initiator"] is not None
        or row["initiator_note"] != "omitted_to_prevent_origin_secret_exposure"
    ):
        raise Rejected("audit_receipt_invalid")
    return tuple((key, type(row[key]), row[key]) for key in sorted(row))


def check_snapshot(snapshot, identity):
    """Necessary typed v2 checks only; caller booleans do NOT prove readiness."""
    required = {
        "schema_version",
        "extension_id",
        "session",
        "ok",
        "configured",
        "fatal",
        "enabled_rulesets",
        "dynamic_rules",
        "session_rules",
        "observer_registered",
        "flushed",
        "storage_access_level",
        "observer_epoch",
        "sequence",
        "receipts",
    }
    if (
        type(identity) is not dict
        or type(identity.get("extension_id")) is not str
        or not re.fullmatch(r"[a-p]{32}", identity["extension_id"])
        or any(
            identity.get(k) is not True
            for k in ("trusted_cdp", "hashes_match", "readonly_mount", "unique_extension")
        )
        or type(snapshot) is not dict
        or set(snapshot) not in (required, required | {"code"})
        or snapshot.get("code") is not None
        or snapshot["schema_version"] != AUDIT_SCHEMA
        or snapshot["extension_id"] != identity["extension_id"]
        or snapshot["session"] != SESSION
        or any(
            snapshot[k] is not True for k in ("ok", "configured", "observer_registered", "flushed")
        )
        or snapshot["fatal"] is not None
        or type(snapshot["enabled_rulesets"]) is not list
        or snapshot["enabled_rulesets"] != ["ws_default_deny_v1"]
        or type(snapshot["dynamic_rules"]) is not list
        or snapshot["dynamic_rules"]
        or type(snapshot["session_rules"]) is not list
        or snapshot["session_rules"]
        or snapshot["storage_access_level"] != "TRUSTED_CONTEXTS"
        or type(snapshot["observer_epoch"]) is not str
        or not snapshot["observer_epoch"]
        or type(snapshot["sequence"]) is not int
        or not 0 <= snapshot["sequence"] <= 100
        or type(snapshot["receipts"]) is not list
        or len(snapshot["receipts"]) != snapshot["sequence"]
    ):
        raise Rejected("snapshot_or_identity_invalid")
    seen = set()
    for ordinal, row in enumerate(snapshot["receipts"], 1):
        receipt_identity(row, identity["extension_id"], snapshot["observer_epoch"], ordinal)
        if row["request_id"] in seen:
            raise Rejected("duplicate_receipt")
        seen.add(row["request_id"])
