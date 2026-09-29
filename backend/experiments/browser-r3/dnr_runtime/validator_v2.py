"""Source-aware strict observation model; real clock equivalence stays unproven."""

from contract_v2 import TIMESTAMP_SOURCE, Rejected, epoch_ms, fingerprint, receipt_identity


def validate_observations(rows, arms, extension_id, epoch):
    if (
        type(rows) is not list
        or type(arms) is not list
        or len(rows) != 4
        or len(arms) != 4
        or any(
            type(a) is not dict
            or type(a.get("actor")) is not str
            or type(a.get("scheme")) is not str
            for a in arms
        )
    ):
        raise Rejected("association_missing")
    if {(a.get("actor"), a.get("scheme")) for a in arms} != {
        (a, s) for a in ("page", "worker") for s in ("ws", "wss")
    }:
        raise Rejected("arms_invalid")
    seen, matched = set(), set()
    for ordinal, row in enumerate(rows, 1):
        receipt_identity(row, extension_id, epoch, ordinal)
        if row["request_id"] in seen:
            raise Rejected("duplicate_receipt")
        seen.add(row["request_id"])
        candidates = [
            a
            for a in arms
            if fingerprint(a["actor"], a["scheme"]) == row["safe_request_fingerprint"]
        ]
        if len(candidates) != 1:
            raise Rejected("association_ambiguous")
        arm = candidates[0]
        key = (arm["actor"], arm["scheme"])
        if key in matched:
            raise Rejected("duplicate_association")
        matched.add(key)
        if (
            arm.get("timestamp_source") != "controlled_fixture_native_date_now_epoch_ms"
            or any(not epoch_ms(arm.get(k)) for k in ("start_ms", "terminal_ms", "end_ms"))
            or not arm["start_ms"] <= row["timestamp"] <= arm["terminal_ms"] <= arm["end_ms"]
            or arm["end_ms"] - arm["start_ms"] > 5000
            or arm.get("terminal") not in {"error", "close"}
            or arm.get("native_constructor") is not True
            or arm.get("navigation_alive") is not True
            or any(
                type(arm.get(k)) is not int or arm[k] != 0
                for k in ("proxy_attempts", "fixture_ws_received", "relay_bytes")
            )
            or (
                arm["actor"] == "worker"
                and any(arm.get(k) is not True for k in ("http_script_alive", "pong", "terminated"))
            )
        ):
            raise Rejected("observation_order_or_arm_invalid")
    return {
        "offline_model": "ACCEPTED",
        "timestamp_source": TIMESTAMP_SOURCE,
        "clock_equivalence": "UNKNOWN",
        "runtime_verified": False,
        "r3_status": "BLOCKED",
    }


def validate_clock_samples(samples):
    if type(samples) is not list or len(samples) < 2:
        raise Rejected("clock_samples_missing")
    previous = None
    for sample in samples:
        if (
            type(sample) is not dict
            or set(sample) != {"source", "epoch_ms", "host_before_ns", "host_after_ns"}
            or sample["source"] != "trusted_extension_native_date_now_epoch_ms"
            or not epoch_ms(sample["epoch_ms"])
            or any(
                type(sample[k]) is not int or sample[k] < 0
                for k in ("host_before_ns", "host_after_ns")
            )
            or sample["host_before_ns"] > sample["host_after_ns"]
            or (
                previous
                and (
                    sample["epoch_ms"] < previous["epoch_ms"]
                    or sample["host_before_ns"] < previous["host_after_ns"]
                )
            )
        ):
            raise Rejected("clock_source_or_order_invalid")
        previous = sample
    # Valid local ordering is NOT inter-process epoch equivalence or a mapping.
    raise Rejected("clock_cross_realm_equivalence_unknown")
