from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

EXPECTED_IDENTITY = {
    "entry_count": 10340,
    "manifest_sha256": "8428859de54769e2faa0470f92c8ae8e0f94464b2003b98f0497b7fcc4bdd49a",
    "payload_bytes": 1750557,
    "payload_sha256": "06e891370ef3af86bda0bcf5539bb292e42ffdd3c6db3a55abc3023fc1e4761e",
}
EXPECTED_DENIALS = {
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
    "undeclared_host",
    "unspecified",
}
EXPECTED_ALLOWED_HOSTS = {
    "dynamic-r2c.test",
    "redirect-r2c.test",
    "redirect-target-r2c.test",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def validate_identity(evidence: Path) -> dict[str, Any]:
    gate = load_json(evidence / "identity-gate.json")
    if gate.get("status") != "PASS" or gate.get("identity") != EXPECTED_IDENTITY:
        raise RuntimeError("Runtime Identity v2 gate mismatch")
    if gate.get("manifest_byte_identical") is not True:
        raise RuntimeError("candidate manifest is not byte-identical to R1D")
    supply = gate.get("supply_chain", {})
    expected_checks = {
        "audit_absent": True,
        "browser_manifest": True,
        "browser_path": True,
        "browser_sha256": True,
        "browser_version": True,
        "debian_inventory": True,
        "debian_lock": True,
        "license_inventory": True,
        "runtime_allowlist": True,
        "sbom": True,
    }
    if supply.get("checks") != expected_checks:
        raise RuntimeError("browser/SBOM/license/final allowlist gate mismatch")
    if supply.get("project_files") != [
        "/opt/flowtracer-r1d/runtime/entrypoint.py",
        "/opt/flowtracer-r1d/runtime/runtime_probe.py",
    ]:
        raise RuntimeError("final project script allowlist mismatch")
    if supply.get("audit_files") != []:
        raise RuntimeError("audit tooling entered final filesystem")
    if (
        supply.get("browser_tree_entries") != 619
        or supply.get("debian_inventory_components") != 206
        or supply.get("debian_license_notice_records") != 206
        or supply.get("sbom_components") != 231
        or supply.get("license_archive_validation")
        != {"files": 208, "members_match_inventory": True}
    ):
        raise RuntimeError("619/206/231/license count gate mismatch")
    return gate


def validate_runtime(evidence: Path) -> dict[str, Any]:
    browser = load_json(evidence / "browser-result.json")
    control = load_json(evidence / "control-client.json")
    topology = load_json(evidence / "topology.json")
    if browser.get("uid") != 10001 or browser.get("read_only_rootfs") is not True:
        raise RuntimeError("browser runtime identity mismatch")
    if browser.get("system_dns") != "authoritative_nxdomain_a_aaaa":
        raise RuntimeError("system DNS isolation evidence missing")
    if browser.get("docker_socket") != "absent" or browser.get("declared_redis") != "PONG":
        raise RuntimeError("socket/Redis boundary evidence mismatch")
    if browser.get("runtime_environment") != {
        "HOME": "/tmp/flowtracer-r2c-home",  # noqa: S108 - dedicated tmpfs
        "XDG_CACHE_HOME": "/tmp/flowtracer-r2c-cache",  # noqa: S108
        "XDG_CONFIG_HOME": "/tmp/flowtracer-r2c-config",  # noqa: S108
    }:
        raise RuntimeError("controlled HOME/XDG runtime environment mismatch")
    direct = browser.get("direct_network_results")
    if not isinstance(direct, list) or len(direct) != 4:
        raise RuntimeError("direct network denial matrix incomplete")
    if any(item.get("outcome") != "unreachable" or item.get("errno") != 101 for item in direct):
        raise RuntimeError("direct network denial is not exact ENETUNREACH")
    endpoint = browser.get("host_gateway_endpoint")
    if (
        control.get("uid") != 10001
        or control.get("response") != "R2C_HOST_CANARY"
        or control.get("endpoint_ip") != endpoint.get("address")
        or control.get("port") != endpoint.get("port")
    ):
        raise RuntimeError("same-endpoint control client proof mismatch")
    if not any(
        item.get("address") == control.get("endpoint_ip")
        and item.get("port") == control.get("port")
        for item in direct
    ):
        raise RuntimeError("browser host-gateway denial does not match control endpoint")

    if topology.get("internal_networks") != ["r2c_browser", "r2c_fixture"]:
        raise RuntimeError("internal network boundary mismatch")
    if topology.get("privileged") != [] or topology.get("docker_socket_mounts") != []:
        raise RuntimeError("privilege or Docker socket exposure detected")
    expected_networks = {
        "browser": ["r2c_browser"],
        "control_client": ["r2c_control"],
        "decoy": ["r2c_fixture"],
        "dns_canary": ["r2c_browser"],
        "fixture": ["r2c_fixture"],
        "host_canary": ["r2c_host_canary"],
        "proxy": ["r2c_browser", "r2c_fixture"],
        "redis": ["r2c_browser"],
    }
    if topology.get("networks") != expected_networks:
        raise RuntimeError("runtime network graph mismatch")
    runtime = topology.get("runtime", {})
    if set(runtime) != set(expected_networks):
        raise RuntimeError("runtime inspect set incomplete")
    for role, facts in runtime.items():
        if (
            facts.get("user") != "10001:10001"
            or facts.get("read_only_rootfs") is not True
            or facts.get("cap_drop") != ["ALL"]
            or facts.get("security_opt") != ["no-new-privileges:true"]
            or facts.get("privileged") is not False
            or facts.get("docker_socket") is not False
            or facts.get("network_mode") == "host"
        ):
            raise RuntimeError(f"runtime hardening mismatch: {role}")
        expected_dns = ["198.51.100.40"] if role == "browser" else ["127.0.0.1"]
        if facts.get("dns") != expected_dns:
            raise RuntimeError(f"unexpected DNS executor for {role}")
        expected_ports = (
            {"49263/tcp": [{"HostIp": "127.0.0.1", "HostPort": "49263"}]}
            if role == "host_canary"
            else {}
        )
        if facts.get("port_bindings") != expected_ports:
            raise RuntimeError(f"unexpected host port binding for {role}")
    host_control = topology.get("host_canary_control", {})
    if (
        host_control.get("address") != "127.0.0.1"
        or host_control.get("port") != 49263
        or host_control.get("response") != "R2C_HOST_CANARY"
        or not isinstance(host_control.get("attempts"), int)
    ):
        raise RuntimeError("host loopback canary control evidence mismatch")
    browser_security = runtime["browser"]
    if (
        browser_security.get("memory") != 805306368
        or browser_security.get("nano_cpus") != 1_000_000_000
        or browser_security.get("pids_limit") != 128
        or browser_security.get("tmpfs")
        != {"/tmp": "rw,nosuid,noexec,size=256m"}  # noqa: S108 - dedicated tmpfs
    ):
        raise RuntimeError("browser frozen resource limits mismatch")

    expected_renders = {
        "dynamic_fetcher": "dynamic-rendered",
        "redirect": "redirect-rendered",
    }
    for name, expected_render in expected_renders.items():
        value = browser.get(name, {})
        if (
            value.get("rendered") != expected_render
            or value.get("elapsed_ms", 60_000) >= 30_000
            or value.get("terminal_browser_processes") != []
            or not all(value.get("runtime_directories_absent_before", {}).values())
            or not all(value.get("runtime_directories_absent_after", {}).values())
        ):
            raise RuntimeError(f"DynamicFetcher runtime evidence incomplete: {name}")
        crashpad = value.get("crashpad_database", {})
        if (
            crashpad.get("uid") != 10001
            or crashpad.get("gid") != 10001
            or crashpad.get("mode") != "0700"
            or not crashpad.get("path", "").startswith(
                "/tmp/flowtracer-r2c-config/"  # noqa: S108 - dedicated tmpfs
            )
            or not crashpad.get("path", "").endswith("/Crash Reports")
        ):
            raise RuntimeError(f"Crashpad evidence mismatch: {name}")
    failure = browser.get("failure", {})
    if (
        not failure.get("failure_type")
        or failure.get("elapsed_ms", 30_000) >= 20_000
        or failure.get("terminal_browser_processes") != []
        or not all(failure.get("runtime_directories_absent_before", {}).values())
        or not all(failure.get("runtime_directories_absent_after", {}).values())
    ):
        raise RuntimeError("DynamicFetcher safe-failure evidence incomplete")
    failure_crashpad = failure.get("crashpad_database", {})
    if (
        failure_crashpad.get("uid") != 10001
        or failure_crashpad.get("gid") != 10001
        or failure_crashpad.get("mode") != "0700"
        or not failure_crashpad.get("path", "").startswith(
            "/tmp/flowtracer-r2c-config/"  # noqa: S108 - dedicated tmpfs
        )
        or not failure_crashpad.get("path", "").endswith("/Crash Reports")
    ):
        raise RuntimeError("safe-failure Crashpad evidence mismatch")
    contract = browser.get("call_contract", {})
    if (
        contract.get("executable_path")
        != "/opt/browser-r1c/chromium-1234/chrome-linux64/chrome"
        or contract.get("proxy") != "http://198.51.100.20:18080"
        or contract.get("retries") != 1
    ):
        raise RuntimeError("DynamicFetcher explicit call contract mismatch")
    if browser.get("terminal_browser_processes") != []:
        raise RuntimeError("browser processes remained at terminal state")
    denials = browser.get("proxy_denials", {})
    expected_application_denials = {
        "absolute_form": 405,
        "dangerous_port": 403,
        "direct_ip": 403,
        "unknown_host": 403,
    }
    expected_application_denials.update(
        {
            host: 403
            for host in (
                "rebind-r2c.test",
                "mixed-r2c.test",
                "loopback-r2c.test",
                "private-r2c.test",
                "linklocal-r2c.test",
                "metadata-r2c.test",
                "multicast-r2c.test",
                "reserved-r2c.test",
                "unspecified-r2c.test",
                "undeclared-r2c.test",
            )
        }
    )
    if denials != expected_application_denials:
        raise RuntimeError("browser application denial matrix mismatch")
    return browser


def validate_events(evidence: Path) -> dict[str, int]:
    proxy = load_jsonl(evidence / "proxy-events.jsonl")
    dns = load_jsonl(evidence / "dns-events.jsonl")
    fixture = load_jsonl(evidence / "fixture-events.jsonl")
    decisions = Counter((event.get("decision"), event.get("reason")) for event in proxy)
    actual_denials = {
        reason for (decision, reason), count in decisions.items() if decision == "deny" and count
    }
    if not EXPECTED_DENIALS <= actual_denials:
        raise RuntimeError(f"missing proxy denials: {sorted(EXPECTED_DENIALS - actual_denials)}")
    allowed = [event for event in proxy if event.get("decision") == "allow"]
    allowed_hosts = {event.get("host") for event in allowed}
    if not EXPECTED_ALLOWED_HOSTS <= allowed_hosts:
        missing = EXPECTED_ALLOWED_HOSTS - allowed_hosts
        raise RuntimeError(f"missing allowed CONNECT hosts: {missing}")
    for event in allowed:
        passes = event.get("resolution_passes")
        if (
            event.get("reason") != "validated"
            or event.get("peer_ip") != "192.0.2.10"
            or not isinstance(passes, list)
            or len(passes) != 2
            or any(set(value) != {"A", "AAAA"} for value in passes)
            or any(value.get("A") != ["192.0.2.10"] or value.get("AAAA") != [] for value in passes)
        ):
            raise RuntimeError(
                "allowed CONNECT omitted A/AAAA, re-resolution, or peer verification"
            )
    dns_pairs = {(event.get("name"), event.get("qtype")) for event in dns}
    if not {
        ("fixture-r2c.test", "A"),
        ("fixture-r2c.test", "AAAA"),
    } <= dns_pairs:
        raise RuntimeError("system DNS A/AAAA canary evidence incomplete")
    if any(
        event.get("decision") != "nxdomain"
        or event.get("authoritative") is not True
        or event.get("recursion_available") is not False
        or event.get("upstream_queries") != 0
        for event in dns
    ):
        raise RuntimeError("DNS canary was not authoritative no-forward NXDOMAIN")
    fixture_hosts = {event.get("host") for event in fixture}
    if not EXPECTED_ALLOWED_HOSTS <= fixture_hosts:
        raise RuntimeError("fixture did not observe DynamicFetcher and redirect chain")
    return {
        "dns_events": len(dns),
        "fixture_events": len(fixture),
        "proxy_allow_events": len(allowed),
        "proxy_deny_events": sum(
            count for (decision, _reason), count in decisions.items() if decision == "deny"
        ),
    }


def validate_cleanup(evidence: Path) -> dict[str, Any]:
    cleanup = load_json(evidence / "cleanup.json")
    if (
        cleanup.get("builder_absent") is not True
        or cleanup.get("image_absent") is not True
        or cleanup.get("containers_remaining") != []
        or cleanup.get("networks_remaining") != []
        or cleanup.get("volumes_remaining") != []
        or cleanup.get("host_port_available") is not True
    ):
        raise RuntimeError("attributable object cleanup incomplete")
    if cleanup.get("docker_snapshot_unchanged") is not True:
        raise RuntimeError("protected Docker snapshot changed")
    return cleanup


def main() -> None:
    evidence = Path(sys.argv[1] if len(sys.argv) > 1 else "evidence/r2c-a2")
    validate_identity(evidence)
    validate_runtime(evidence)
    counts = validate_events(evidence)
    validate_cleanup(evidence)
    result = load_json(evidence / "result.json")
    if (
        result.get("status") != "PASS"
        or result.get("public_network_or_target") is not False
        or result.get("prior_failure_unchanged") is not True
        or result.get("protected_files_unchanged") is not True
    ):
        raise RuntimeError("terminal R2C result mismatch")
    print(json.dumps({"result": "R2C_PASS", **counts}, sort_keys=True))


if __name__ == "__main__":
    main()
