from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
COMPOSE = ROOT / "compose.yaml"
EVIDENCE = ROOT / "evidence"
PROJECT = os.environ.get("R2_PROJECT_NAME", "flowtracer-r2-20260909")
BROWSER_IMAGE = os.environ.get("R2_BROWSER_IMAGE", "flowtracer-browser-r1:r1-r2")
PROBE_CONTAINER = f"{PROJECT}-browser-probe"
CONTROL_CONTAINER = f"{PROJECT}-control-client"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    # Every caller supplies fixed local Docker/Python argv; shell expansion is disabled.
    result = subprocess.run(  # noqa: S603
        args,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(args[:4])}\n{result.stderr}"
        )
    return result


def compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(
        "docker",
        "compose",
        "--project-name",
        PROJECT,
        "-f",
        str(COMPOSE),
        *args,
        check=check,
    )


def json_output(*args: str) -> Any:
    return json.loads(run(*args).stdout)


def wait_for_host_canary() -> dict[str, object]:
    deadline = time.monotonic() + 5
    attempts = 0
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        attempts += 1
        try:
            with socket.create_connection(("127.0.0.1", 49175), timeout=0.5) as canary:
                response = canary.recv(32)
        except OSError as error:
            last_error = error
            time.sleep(0.2)
            continue
        if not response.startswith(b"R2_HOST_CANARY"):
            raise RuntimeError("host canary control path returned an unexpected response")
        return {
            "address": "127.0.0.1",
            "attempts": attempts,
            "port": 49175,
            "response": "R2_HOST_CANARY",
        }
    raise RuntimeError(f"host canary control path was not ready: {last_error}")


def ensure_clean_start() -> None:
    containers = run(
        "docker",
        "ps",
        "-aq",
        "--filter",
        f"label=com.docker.compose.project={PROJECT}",
    ).stdout.strip()
    networks = run(
        "docker",
        "network",
        "ls",
        "-q",
        "--filter",
        f"label=com.docker.compose.project={PROJECT}",
    ).stdout.strip()
    named_probe = run("docker", "container", "inspect", PROBE_CONTAINER, check=False)
    named_control = run("docker", "container", "inspect", CONTROL_CONTAINER, check=False)
    if containers or networks or named_probe.returncode == 0 or named_control.returncode == 0:
        raise RuntimeError("R2 project objects already exist; refusing to reuse or overwrite them")


def sanitized_topology(container_names: dict[str, str]) -> dict[str, object]:
    topology: dict[str, list[str]] = {}
    runtime: dict[str, dict[str, object]] = {}
    privileged: list[str] = []
    socket_mounts: list[str] = []
    for role, name in container_names.items():
        inspect = json_output("docker", "container", "inspect", name)[0]
        host_config = inspect["HostConfig"]
        runtime[role] = {
            "cap_drop": sorted(host_config.get("CapDrop") or []),
            "network_mode": host_config["NetworkMode"],
            "port_bindings": host_config.get("PortBindings") or {},
            "read_only_rootfs": host_config["ReadonlyRootfs"],
            "security_opt": sorted(host_config.get("SecurityOpt") or []),
            "user": inspect["Config"]["User"],
        }
        topology[role] = sorted(
            network.removeprefix(f"{PROJECT}_")
            for network in inspect["NetworkSettings"]["Networks"]
        )
        if host_config["Privileged"] or host_config["NetworkMode"] == "host":
            privileged.append(role)
        if any(mount["Destination"] == "/var/run/docker.sock" for mount in inspect["Mounts"]):
            socket_mounts.append(role)
        if not host_config["ReadonlyRootfs"]:
            raise RuntimeError(f"{role} root filesystem is writable")
        if "ALL" not in (host_config.get("CapDrop") or []):
            raise RuntimeError(f"{role} does not drop all capabilities")
        expected_dns = ["198.51.100.40"] if role == "browser" else ["127.0.0.1"]
        if host_config.get("Dns") != expected_dns:
            raise RuntimeError(f"{role} has an unexpected DNS resolver")
    internal_networks: list[str] = []
    for short_name in ("r2_browser", "r2_fixture"):
        network = json_output("docker", "network", "inspect", f"{PROJECT}_{short_name}")[0]
        if network["Internal"]:
            internal_networks.append(short_name)
    return {
        "docker_socket_mounts": sorted(socket_mounts),
        "internal_networks": sorted(internal_networks),
        "networks": topology,
        "privileged": sorted(privileged),
        "project": PROJECT,
        "runtime": runtime,
    }


def cleanup() -> dict[str, object]:
    run("docker", "container", "rm", "-f", PROBE_CONTAINER, CONTROL_CONTAINER, check=False)
    compose("down", "--remove-orphans", check=False)
    containers = run(
        "docker",
        "ps",
        "-aq",
        "--filter",
        f"label=com.docker.compose.project={PROJECT}",
    ).stdout.split()
    networks = run(
        "docker",
        "network",
        "ls",
        "-q",
        "--filter",
        f"label=com.docker.compose.project={PROJECT}",
    ).stdout.split()
    port_deadline = time.monotonic() + 5
    port_attempts = 0
    while True:
        port_attempts += 1
        try:
            with socket.socket() as verifier:
                if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    verifier.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                verifier.bind(("127.0.0.1", 49175))
            break
        except OSError as error:
            if time.monotonic() >= port_deadline:
                raise RuntimeError("host canary loopback port was not released") from error
            time.sleep(0.2)
    image = json_output("docker", "image", "inspect", BROWSER_IMAGE)[0]
    return {
        "containers_remaining": containers,
        "host_port": {
            "address": "127.0.0.1",
            "available_for_exclusive_bind": True,
            "attempts": port_attempts,
            "port": 49175,
        },
        "networks_remaining": networks,
        "project": PROJECT,
        "r1_image": {"id": image["Id"], "tag": BROWSER_IMAGE},
        "volumes_created": 0,
    }


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for name in (
        "browser-probe.json",
        "cleanup.json",
        "control-client.json",
        "dns-events.jsonl",
        "proxy-events.jsonl",
        "topology.json",
    ):
        (EVIDENCE / name).unlink(missing_ok=True)
    ensure_clean_start()
    try:
        compose("config", "--quiet")
        compose(
            "up",
            "-d",
            "--wait",
            "fixture",
            "decoy",
            "proxy",
            "redis",
            "dns-canary",
            "host-canary",
        )
        host_canary_control = wait_for_host_canary()
        control = compose(
            "run",
            "--name",
            CONTROL_CONTAINER,
            "--no-deps",
            "control-client",
            check=False,
        )
        if control.returncode:
            raise RuntimeError(
                f"host gateway control client failed ({control.returncode}): {control.stderr}"
            )
        control_lines = [line for line in control.stdout.splitlines() if line.startswith("{")]
        if not control_lines:
            raise RuntimeError("host gateway control client emitted no JSON evidence")
        control_evidence = json.loads(control_lines[-1])
        (EVIDENCE / "control-client.json").write_text(
            json.dumps(control_evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        probe = compose(
            "run",
            "--name",
            PROBE_CONTAINER,
            "--no-deps",
            "browser",
            check=False,
        )
        if probe.returncode:
            raise RuntimeError(
                f"browser namespace probe failed ({probe.returncode}): {probe.stderr}"
            )
        probe_lines = [line for line in probe.stdout.splitlines() if line.startswith("{")]
        if not probe_lines:
            raise RuntimeError("browser namespace probe emitted no JSON evidence")
        probe_evidence = json.loads(probe_lines[-1])
        (EVIDENCE / "browser-probe.json").write_text(
            json.dumps(probe_evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        names = {
            "browser": PROBE_CONTAINER,
            "control_client": CONTROL_CONTAINER,
            "decoy": f"{PROJECT}-decoy-1",
            "dns_canary": f"{PROJECT}-dns-canary-1",
            "fixture": f"{PROJECT}-fixture-1",
            "host_canary": f"{PROJECT}-host-canary-1",
            "proxy": f"{PROJECT}-proxy-1",
            "redis": f"{PROJECT}-redis-1",
        }
        topology_evidence = sanitized_topology(names)
        topology_evidence["host_canary_control"] = host_canary_control
        (EVIDENCE / "topology.json").write_text(
            json.dumps(topology_evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    finally:
        cleanup_result = cleanup()
        (EVIDENCE / "cleanup.json").write_text(
            json.dumps(cleanup_result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if cleanup_result["containers_remaining"] or cleanup_result["networks_remaining"]:
        raise RuntimeError("R2 cleanup left attributable Docker objects")
    validation = run(sys.executable, str(ROOT / "validate_evidence.py"), str(EVIDENCE))
    print(validation.stdout.strip())


if __name__ == "__main__":
    main()
