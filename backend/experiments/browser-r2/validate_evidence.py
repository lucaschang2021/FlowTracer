from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    evidence = Path(sys.argv[1] if len(sys.argv) > 1 else "evidence")
    probe = load_json(evidence / "browser-probe.json")
    control = load_json(evidence / "control-client.json")
    topology = load_json(evidence / "topology.json")
    cleanup = load_json(evidence / "cleanup.json")
    dns_events = [
        json.loads(line) for line in (evidence / "dns-events.jsonl").read_text().splitlines()
    ]
    events = [
        json.loads(line) for line in (evidence / "proxy-events.jsonl").read_text().splitlines()
    ]
    if not isinstance(probe, dict) or probe.get("uid") != 10001:
        raise RuntimeError("browser probe identity evidence is invalid")
    if (
        probe.get("system_dns") != "authoritative_nxdomain"
        or probe.get("docker_socket") != "absent"
    ):
        raise RuntimeError("browser namespace isolation evidence is incomplete")
    direct_results = probe.get("direct_network_results")
    if not isinstance(direct_results, list) or len(direct_results) != 4:
        raise RuntimeError("direct network denial evidence is incomplete")
    if any(
        not isinstance(result, dict)
        or result.get("outcome") != "unreachable"
        or result.get("errno") != 101
        for result in direct_results
    ):
        raise RuntimeError("direct network denial is not exact ENETUNREACH evidence")
    host_endpoint = probe.get("host_gateway_endpoint")
    if (
        not isinstance(control, dict)
        or control.get("uid") != 10001
        or control.get("response") != "R2_HOST_CANARY"
        or not isinstance(host_endpoint, dict)
        or control.get("endpoint_ip") != host_endpoint.get("address")
        or control.get("port") != host_endpoint.get("port")
    ):
        raise RuntimeError("host gateway same-endpoint positive control is invalid")
    matching_host_denials = [
        result
        for result in direct_results
        if result.get("address") == control.get("endpoint_ip")
        and result.get("port") == control.get("port")
    ]
    if len(matching_host_denials) != 1:
        raise RuntimeError("Browser host gateway denial does not match the control endpoint")
    if not isinstance(topology, dict) or topology.get("networks") != {
        "browser": ["r2_browser"],
        "control_client": ["r2_control_client"],
        "decoy": ["r2_fixture"],
        "dns_canary": ["r2_browser"],
        "fixture": ["r2_fixture"],
        "host_canary": ["r2_host_canary"],
        "proxy": ["r2_browser", "r2_fixture"],
        "redis": ["r2_browser"],
    }:
        raise RuntimeError("container network topology does not match the frozen R2 graph")
    if topology.get("internal_networks") != ["r2_browser", "r2_fixture"]:
        raise RuntimeError("Browser and fixture networks are not both internal")
    if topology.get("privileged") != [] or topology.get("docker_socket_mounts") != []:
        raise RuntimeError("privilege or Docker socket exposure detected")
    host_control = topology.get("host_canary_control")
    if (
        not isinstance(host_control, dict)
        or host_control.get("address") != "127.0.0.1"
        or host_control.get("port") != 49175
        or host_control.get("response") != "R2_HOST_CANARY"
        or not isinstance(host_control.get("attempts"), int)
    ):
        raise RuntimeError("host canary control path was not proven")
    runtime = topology.get("runtime")
    if not isinstance(runtime, dict) or set(runtime) != {
        "browser",
        "control_client",
        "decoy",
        "dns_canary",
        "fixture",
        "host_canary",
        "proxy",
        "redis",
    }:
        raise RuntimeError("runtime inspect evidence is incomplete")
    project = topology.get("project")
    if not isinstance(project, str) or not project.startswith("flowtracer-r2-"):
        raise RuntimeError("runtime project identity is invalid")
    expected_network_modes = {
        "browser": f"{project}_r2_browser",
        "control_client": f"{project}_r2_control_client",
        "decoy": f"{project}_r2_fixture",
        "dns_canary": f"{project}_r2_browser",
        "fixture": f"{project}_r2_fixture",
        "host_canary": f"{project}_r2_host_canary",
        "proxy": f"{project}_r2_browser",
        "redis": f"{project}_r2_browser",
    }
    for role, facts in runtime.items():
        if not isinstance(facts, dict):
            raise RuntimeError(f"runtime inspect evidence invalid for {role}")
        if facts.get("user") != "10001:10001":
            raise RuntimeError(f"unexpected runtime user for {role}")
        if facts.get("read_only_rootfs") is not True or facts.get("cap_drop") != ["ALL"]:
            raise RuntimeError(f"runtime hardening invalid for {role}")
        if facts.get("security_opt") != ["no-new-privileges:true"]:
            raise RuntimeError(f"security options invalid for {role}")
        if facts.get("network_mode") != expected_network_modes[role]:
            raise RuntimeError(f"unexpected network mode for {role}")
        expected_bindings = (
            {"49175/tcp": [{"HostIp": "127.0.0.1", "HostPort": "49175"}]}
            if role == "host_canary"
            else {}
        )
        if facts.get("port_bindings") != expected_bindings:
            raise RuntimeError(f"unexpected port binding for {role}")
    dns_matrix = [(event.get("name"), event.get("qtype")) for event in dns_events]
    if sorted(dns_matrix) != [("fixture-r2.test", "A"), ("fixture-r2.test", "AAAA")]:
        raise RuntimeError("authoritative DNS query evidence is incomplete")
    if any(
        event.get("decision") != "nxdomain"
        or event.get("source") != "browser-system-resolver"
        or event.get("authoritative") is not True
        or event.get("recursion_available") is not False
        or event.get("upstream_queries") != 0
        for event in dns_events
    ):
        raise RuntimeError("DNS canary evidence contains an unexpected decision")
    expected_image = {
        "id": "sha256:83464fd58248b3af79903c3d4ce3d33140f498bdfef4d9efec9c4552718a3eec",
        "tag": "flowtracer-browser-r1:r1-final-build2",
    }
    if not isinstance(cleanup, dict) or cleanup.get("containers_remaining") != []:
        raise RuntimeError("cleanup container evidence is invalid")
    if cleanup.get("networks_remaining") != [] or cleanup.get("volumes_created") != 0:
        raise RuntimeError("cleanup network/volume evidence is invalid")
    host_port = cleanup.get("host_port")
    if (
        not isinstance(host_port, dict)
        or host_port.get("address") != "127.0.0.1"
        or host_port.get("port") != 49175
        or host_port.get("available_for_exclusive_bind") is not True
        or not isinstance(host_port.get("attempts"), int)
    ):
        raise RuntimeError("host canary port release was not proven")
    if cleanup.get("r1_image") != expected_image:
        raise RuntimeError("post-cleanup R1 image identity is invalid")
    decisions = Counter((event["decision"], event["reason"]) for event in events)
    required_denials = {
        "connect_required",
        "dangerous_port",
        "direct_ip",
        "dns_rebinding",
        "link_local",
        "loopback",
        "metadata",
        "mixed_answer",
        "multicast",
        "not_declared_fixture",
        "private",
        "reserved",
        "unspecified",
    }
    actual_denials = {
        reason for (decision, reason), count in decisions.items() if decision == "deny" and count
    }
    if not required_denials <= actual_denials:
        raise RuntimeError(
            f"missing proxy denial evidence: {sorted(required_denials - actual_denials)}"
        )
    if decisions[("allow", "validated")] != 4:
        raise RuntimeError("CONNECT/redirect allow event count is not exact")
    if sum(count for (decision, _), count in decisions.items() if decision == "deny") != 14:
        raise RuntimeError("proxy denial event count is not exact")
    print(
        json.dumps(
            {
                "allow_events": sum(
                    count for (decision, _), count in decisions.items() if decision == "allow"
                ),
                "deny_events": sum(
                    count for (decision, _), count in decisions.items() if decision == "deny"
                ),
                "result": "R2_PASS",
                "validated_denial_reasons": sorted(actual_denials),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
