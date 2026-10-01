"""Closed evidence graph validator. Real authority acceptance is intentionally NO_GO."""

from __future__ import annotations

from contract import (
    LIMITS,
    MATRIX,
    POLICY,
    SCHEMA,
    digest,
    identifier,
    integer,
    object_fields,
    reject,
    strict_json,
)
from supervisor import terminal


def _validate(raw: bytes) -> str:
    graph = object_fields(
        strict_json(raw),
        {
            "schema",
            "kind",
            "execution_id",
            "binding",
            "triggers",
            "decisions",
            "observations",
            "completion",
        },
    )
    if graph["schema"] != SCHEMA or graph["kind"] != "SYNTHETIC":
        reject("synthetic_only")
    execution = identifier(graph["execution_id"])
    binding = object_fields(
        graph["binding"],
        {
            "candidate_sha",
            "input_sha",
            "image_sha",
            "payload_sha",
            "manifest_sha",
            "driver",
            "policy",
            "r1e",
            "r2c",
            "source",
        },
    )
    digest(binding["candidate_sha"], 40)
    for field in ("input_sha", "image_sha", "payload_sha", "manifest_sha"):
        digest(binding[field])
    if (
        binding["driver"],
        binding["policy"],
        binding["source"],
        binding["r1e"],
        binding["r2c"],
    ) != (
        "DynamicFetcher.fetch",
        POLICY,
        "synthetic_host",
        "R1E-PR66",
        "R2C-A4-PR68",
    ):
        reject("invalid_binding")
    for category in ("triggers", "decisions", "observations"):
        if type(graph[category]) is not list or not 1 <= len(graph[category]) <= 100:
            reject("invalid_collection")
    ids = set()
    clocks = set()

    def record(value, fields):
        item = object_fields(value, fields | {"id", "execution_id", "clock", "seq"})
        key = identifier(item["id"])
        if key in ids:
            reject("duplicate_id")
        ids.add(key)
        if item["execution_id"] != execution:
            reject("cross_execution")
        if item["clock"] not in {"app", "proxy", "fixture", "host-network"}:
            reject("invalid_clock")
        stamp = (item["clock"], integer(item["seq"]))
        if stamp in clocks:
            reject("duplicate_sequence")
        clocks.add(stamp)
        return item

    triggers = {}
    for value in graph["triggers"]:
        t = record(value, {"route", "surface", "actor", "parent_id", "request_id", "result"})
        route = identifier(t["route"])
        if route not in MATRIX or route in triggers:
            reject("invalid_route")
        surface, actor, _, parent = MATRIX[route]
        if (t["surface"], t["actor"], t["clock"]) != (surface, actor, "app"):
            reject("invalid_trigger")
        expected = "PREVENTED_BY_DENIED_PARENT" if parent else "TRIGGERED"
        if t["result"] != expected:
            reject("trigger_not_proven")
        if parent:
            if t["request_id"] is not None:
                reject("fabricated_child_request")
        else:
            identifier(t["request_id"])
        if t["parent_id"] is not None:
            identifier(t["parent_id"])
        triggers[route] = t
    if set(triggers) != set(MATRIX):
        reject("missing_matrix")
    requests = [t["request_id"] for t in triggers.values() if t["request_id"] is not None]
    if len(set(requests)) != len(requests):
        reject("cross_request")
    for route, t in triggers.items():
        parent_route = MATRIX[route][3]
        if parent_route is None and route != "navigation":
            parent_route = "redirect-start" if route == "redirect-end" else "navigation"
            if route == "worker-ws":
                parent_route = "worker-script"
        expected_parent = triggers[parent_route]["id"] if parent_route else None
        if t["parent_id"] != expected_parent:
            reject("invalid_parent")
        if parent_route and t["seq"] <= triggers[parent_route]["seq"]:
            reject("invalid_parent_order")
    by_id = {t["id"]: t for t in triggers.values()}
    decisions = {}
    consumed = dict.fromkeys(LIMITS, 0)
    for value in graph["decisions"]:
        d = record(value, {"trigger_id", "request_id", "action", "reason", "checks", "used"})
        trigger_id = identifier(d["trigger_id"])
        if trigger_id not in by_id or trigger_id in decisions:
            reject("invalid_decision_link")
        t = by_id[trigger_id]
        if d["clock"] != "app" or d["seq"] <= t["seq"]:
            reject("invalid_order")
        action = MATRIX[t["route"]][2]
        reason = (
            "denied_parent"
            if MATRIX[t["route"]][3]
            else ("policy_allow" if action == "allow" else "default_deny")
        )
        if (d["action"], d["reason"], d["request_id"]) != (action, reason, t["request_id"]):
            reject("invalid_decision")
        checks = object_fields(d["checks"], {"network", "site", "scope", "budget", "capability"})
        if checks != {
            "network": "PASS",
            "site": "PASS",
            "scope": "PASS",
            "budget": "PASS",
            "capability": "PASS" if action == "allow" else "DENY",
        }:
            reject("policy_not_proven")
        used = object_fields(d["used"], set(LIMITS))
        for field, limit in LIMITS.items():
            consumed[field] += integer(used[field])
            if consumed[field] > limit:
                reject("budget_exhausted")
        if used["requests"] != (1 if action == "allow" else 0):
            reject("invalid_consumption")
        decisions[trigger_id] = d
    if set(decisions) != set(by_id):
        reject("missing_decision")
    observations = {key: {} for key in by_id}
    vendor_ids = set()
    for value in graph["observations"]:
        o = record(
            value,
            {
                "trigger_id",
                "decision_id",
                "request_id",
                "source",
                "result",
                "transport_id",
                "actor",
            },
        )
        trigger_id = identifier(o["trigger_id"])
        if trigger_id not in by_id:
            reject("invalid_observation_link")
        t, d = by_id[trigger_id], decisions[trigger_id]
        if (o["decision_id"], o["request_id"], o["actor"]) != (
            d["id"],
            t["request_id"],
            t["actor"],
        ):
            reject("cross_request")
        source = o["source"]
        parent = MATRIX[t["route"]][3]
        allowed = d["action"] == "allow"
        expected = (
            {"app": "continued", "proxy": "forwarded", "fixture": "received"}
            if allowed
            else {
                "app": "parent_prevented" if parent else "application_denied",
                "host-network": "parent_prevented" if parent else "policy_prevented_no_egress",
            }
        )
        if type(source) is not str or source not in expected or source in observations[trigger_id]:
            reject("invalid_source")
        if o["clock"] != source or o["result"] != expected[source]:
            reject("invalid_observation")
        if source == "app" and o["seq"] <= d["seq"]:
            reject("invalid_order")
        if allowed and source in {"proxy", "fixture"}:
            vendor = identifier(o["transport_id"])
            if (source, vendor) in vendor_ids:
                reject("conflicting_vendor_mapping")
            vendor_ids.add((source, vendor))
        elif o["transport_id"] is not None:
            reject("fabricated_transport")
        observations[trigger_id][source] = o
    for trigger_id, sources in observations.items():
        expected_sources = (
            {"app", "proxy", "fixture"}
            if decisions[trigger_id]["action"] == "allow"
            else {
                "app",
                "host-network",
            }
        )
        if set(sources) != expected_sources:
            reject("missing_observation")
    terminal(graph["completion"])
    return "SYNTHETIC_ACCEPTED_NOT_R3_PASS"


def validate_synthetic(raw: bytes) -> str:
    try:
        return _validate(raw)
    except (TypeError, KeyError, OverflowError):
        reject("invalid_type")


def validate_real(*_args, **_kwargs) -> None:
    reject("NO_GO_trusted_host_adapter_not_wired")


if __name__ == "__main__":
    raise SystemExit("NO_GO_real_execution_not_authorized")
