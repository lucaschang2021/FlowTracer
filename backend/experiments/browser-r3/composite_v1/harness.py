"""Pure synthetic graph builder and explicit, non-executing runtime wiring plan."""

from collector import Collector
from contract import LIMITS, MATRIX, POLICY


def synthetic_graph() -> bytes:
    execution = "SYNTHETIC-composite-001"
    collector = Collector(
        {
            "candidate_sha": "0" * 40,
            "input_sha": "0" * 64,
            "image_sha": "0" * 64,
            "payload_sha": "0" * 64,
            "manifest_sha": "0" * 64,
            "driver": "DynamicFetcher.fetch",
            "policy": POLICY,
            "r1e": "R1E-PR66",
            "r2c": "R2C-A4-PR68",
            "source": "synthetic_host",
        },
        execution,
    )
    for index, (route, (surface, actor, action, parent)) in enumerate(MATRIX.items(), 1):
        trigger_id, decision_id = "t-" + route, "d-" + route
        request_id = None if parent else "r-" + route
        parent_route = parent or ("redirect-start" if route == "redirect-end" else "navigation")
        if route == "worker-ws":
            parent_route = "worker-script"
        collector.append(
            "triggers",
            {
                "id": trigger_id,
                "execution_id": execution,
                "clock": "app",
                "seq": index * 3,
                "route": route,
                "surface": surface,
                "actor": actor,
                "parent_id": None if route == "navigation" else "t-" + parent_route,
                "request_id": request_id,
                "result": "PREVENTED_BY_DENIED_PARENT" if parent else "TRIGGERED",
            },
        )
        collector.append(
            "decisions",
            {
                "id": decision_id,
                "execution_id": execution,
                "clock": "app",
                "seq": index * 3 + 1,
                "trigger_id": trigger_id,
                "request_id": request_id,
                "action": action,
                "reason": "denied_parent"
                if parent
                else ("policy_allow" if action == "allow" else "default_deny"),
                "checks": {
                    "network": "PASS",
                    "site": "PASS",
                    "scope": "PASS",
                    "budget": "PASS",
                    "capability": "PASS" if action == "allow" else "DENY",
                },
                "used": {"requests": 1 if action == "allow" else 0, "pages": 0, "bytes": 0},
            },
        )
        sources = (
            {"app": "continued", "proxy": "forwarded", "fixture": "received"}
            if action == "allow"
            else {
                "app": "parent_prevented" if parent else "application_denied",
                "host-network": "parent_prevented" if parent else "policy_prevented_no_egress",
            }
        )
        for source, result in sources.items():
            collector.append(
                "observations",
                {
                    "id": "o-" + source + "-" + route,
                    "execution_id": execution,
                    "clock": source,
                    "seq": index * 3 + 2,
                    "trigger_id": trigger_id,
                    "decision_id": decision_id,
                    "request_id": request_id,
                    "source": source,
                    "result": result,
                    "actor": actor,
                    "transport_id": source + "-" + route
                    if source in {"proxy", "fixture"}
                    else None,
                },
            )
    return collector.finish(
        {
            "outcome": "completed",
            "cleanup": "owned_removed",
            "network_audit": "complete",
            "duration_ms": 1000,
        }
    )


def wiring_plan() -> dict:
    return {
        "status": "NO_GO",
        "driver": "DynamicFetcher.fetch",
        "page_setup": "install policy before navigation; host-owned trigger and decision mapping",
        "page_action": list(MATRIX),
        "budget_limits": dict(LIMITS),
        "missing": [
            "exact host permit",
            "runtime binding attestation",
            "policy adapter",
            "worker denial observer",
            "proxy fixture correlation adapter",
            "host network-audit collector",
            "supervised owned cleanup",
        ],
    }


if __name__ == "__main__":
    raise SystemExit("NO_GO_real_execution_not_authorized")
