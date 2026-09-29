"""Observation v2, never a rule-match timestamp or a real-session admission."""

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
