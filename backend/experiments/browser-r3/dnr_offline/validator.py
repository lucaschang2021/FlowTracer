"""Synthetic contract validator only, never consumes fixture authority as DNR."""

from __future__ import annotations

import math

from contract import SESSION, Rejected, check_readback, fingerprint


def validate_model(snapshot: dict, identity: dict, arms: list[dict], baseline: dict) -> dict:
    check_readback(snapshot, identity)
    receipts = snapshot.get("receipts")
    if not isinstance(receipts, list) or len(receipts) != 4 or len(receipts) > 100:
        raise Rejected("receipts_missing_or_overflow")
    if snapshot.get("sequence") != len(receipts):
        raise Rejected("audit_loss")
    if baseline != {
        "ws_proxy_denied": True,
        "wss_proxy_denied": True,
        "dnr_receipts": 0,
        "independent_403": True,
        "upstream_bytes": 0,
        "relay_bytes": 0,
        "fixture_ws_received": 0,
    }:
        raise Rejected("baseline_or_proxy_invalid")
    if len(arms) != 4 or {(a.get("actor"), a.get("scheme")) for a in arms} != {
        (actor, scheme) for actor in ("page", "worker") for scheme in ("ws", "wss")
    }:
        raise Rejected("arms_invalid")
    sequences, request_ids, matches = set(), set(), set()
    for receipt in receipts:
        if (
            set(receipt)
            != {
                "schema_version",
                "session",
                "extension_id",
                "ruleset_id",
                "rule_id",
                "action",
                "resource_type",
                "request_id",
                "timestamp",
                "sequence",
                "observer_epoch",
                "safe_request_fingerprint",
                "tab_id",
                "frame_id",
                "document_id",
                "initiator",
                "initiator_note",
            }
            or receipt.get("schema_version") != "r3-dnr-receipt-v1"
            or receipt.get("session") != SESSION
            or receipt.get("extension_id") != identity["extension_id"]
            or receipt.get("ruleset_id") != "ws_default_deny_v1"
            or receipt.get("rule_id") != 1
            or receipt.get("action") != "block"
            or receipt.get("resource_type") != "websocket"
            or receipt.get("observer_epoch") != snapshot["observer_epoch"]
            or not isinstance(receipt.get("request_id"), str)
            or not receipt["request_id"]
            or type(receipt.get("sequence")) is not int
            or not isinstance(receipt.get("timestamp"), (int, float))
            or not math.isfinite(receipt["timestamp"])
            or receipt.get("sequence") in sequences
            or receipt.get("request_id") in request_ids
            or receipt.get("initiator") is not None
        ):
            raise Rejected("receipt_invalid")
        sequence = receipt["sequence"]
        if sequence != len(sequences) + 1:
            raise Rejected("sequence_invalid")
        sequences.add(sequence)
        request_ids.add(receipt["request_id"])
        candidates = [
            (i, arm)
            for i, arm in enumerate(arms)
            if receipt.get("safe_request_fingerprint") == fingerprint(arm["actor"], arm["scheme"])
            and arm["start_ms"] <= receipt["timestamp"] <= arm["end_ms"]
        ]
        if len(candidates) != 1:
            raise Rejected("association_ambiguous")
        index, arm = candidates[0]
        if index in matches:
            raise Rejected("duplicate_association")
        matches.add(index)
        if (
            arm.get("source") != "native_constructor"
            or arm.get("receipt_source") != "trusted_extension_cdp"
            or arm.get("terminal") not in {"error", "close"}
            or arm.get("terminal_ms", math.inf) - arm["start_ms"] > 5000
            or arm.get("terminal_ms", -math.inf) < arm["start_ms"]
            or arm.get("proxy_attempts") != 0
            or arm.get("fixture_ws_received") != 0
            or arm.get("relay_bytes") != 0
            or arm.get("navigation_alive") is not True
            or arm.get("target_id") is None
            or arm.get("cdp_session_id") is None
            or arm.get("cdp_request_id") is None
            or (
                arm["actor"] == "worker"
                and not all(
                    arm.get(key) is True for key in ("http_script_alive", "pong", "terminated")
                )
            )
        ):
            raise Rejected("arm_evidence_invalid")
    # Names express model acceptance, NOT trusted provenance or real enforcement.
    return {
        "offline_model": "ACCEPTED",
        "runtime_verified": False,
        "r3_status": "BLOCKED",
        "formal_r3_gate": False,
    }
