from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import os
import re
import socket
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
R1D = ROOT.parent / "browser-r1d"
HARNESS = ROOT / "r2c_a2"
EVIDENCE = ROOT / "evidence" / "r2c-a2"
RUN_ID = "flowtracer-r2c-a2-20260920-final-a"
PROJECT = RUN_ID
BUILDER = f"{RUN_ID}-builder"
IMAGE = f"flowtracer-browser-r2c:{RUN_ID}"
PROBE_CONTAINER = f"{PROJECT}-browser-probe"
CONTROL_CONTAINER = f"{PROJECT}-control-client"
CANARY_PORT = 49263
BUILDKIT_IMAGE = (
    "moby/buildkit@sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8"
)
EXPECTED_IDENTITY = {
    "entry_count": 10340,
    "manifest_sha256": "8428859de54769e2faa0470f92c8ae8e0f94464b2003b98f0497b7fcc4bdd49a",
    "payload_bytes": 1750557,
    "payload_sha256": "06e891370ef3af86bda0bcf5539bb292e42ffdd3c6db3a55abc3023fc1e4761e",
}
EXPECTED_BROWSER_SHA = "0b20b130e7edd9dd51873be867761295fe0cfad490c2b9a64f95bd3cfc08fa71"
EXPECTED_BROWSER_TREE_SHA = "197d911b97e67180aef120d7cffb974436dcbcbe4acce566809b6d0e1363390a"
EXPECTED_DEBIAN_LOCK_SHA = "299a341b239c284c385ecacd9d3882bdf29472b28421075b369009f998b54b83"
EXPECTED_SBOM_SHA = "a8d6ae5e450b10bd40d90f6d56a0e69742479cfaff79398c0d2fb0696cfcf774"
EXPECTED_INVENTORY_SHA = "bee9c30ae016be592521c383b9bb0be74f39892415ed28f9122d5b7ccced81da"
EXPECTED_LICENSE_ARCHIVE_SHA = (
    "4c89ab4aaca629a09009ef0a00b14dcbbc9e2418c32ffb40987a4f4ff621c780"
)
PROTECTED = ("browser-r1", "browser-r2", "browser-r1c", "browser-r1d", "browser-r3")
RUNTIME_ENV = {
    "HOME": "/tmp/flowtracer-r2c-home",  # noqa: S108 - dedicated container tmpfs
    "XDG_CONFIG_HOME": "/tmp/flowtracer-r2c-config",  # noqa: S108
    "XDG_CACHE_HOME": "/tmp/flowtracer-r2c-cache",  # noqa: S108
}

ledger: list[dict[str, Any]] = []


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_hashes(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"protected tree contains symlink: {path}")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha256_file(path)
        elif not path.is_dir():
            raise RuntimeError(f"protected tree contains unsupported entry: {path}")
    return dict(sorted(result.items()))


def package_tree_identity(root: Path) -> dict[str, int | str]:
    entries = tree_hashes(root)
    payload = b"".join(
        path.encode("utf-8") + b" " + digest.encode("ascii") + b"\n"
        for path, digest in entries.items()
    )
    return {
        "files": len(entries),
        "payload_bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run(
    argv: list[str],
    *,
    check: bool = True,
    timeout: int = 120,
    input_bytes: bytes | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    started = now()
    try:
        result = subprocess.run(  # noqa: S603 - fixed local Docker/Python argv
            argv,
            cwd=REPO,
            check=False,
            capture_output=True,
            input=input_bytes,
            timeout=timeout,
            env=env,
        )
        stdout = result.stdout
        stderr = result.stderr
        returncode = result.returncode
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        returncode = 124
        result = subprocess.CompletedProcess(argv, returncode, stdout, stderr)
    command_id = len(ledger) + 1
    commands = EVIDENCE / "commands"
    commands.mkdir(parents=True, exist_ok=True)
    stdout_path = commands / f"{command_id:03d}.stdout.txt"
    stderr_path = commands / f"{command_id:03d}.stderr.txt"
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    ledger.append(
        {
            "argv": argv,
            "ended_at": now(),
            "exit_code": returncode,
            "input_sha256": sha256_bytes(input_bytes) if input_bytes is not None else None,
            "started_at": started,
            "stderr_bytes": len(stderr),
            "stderr_path": stderr_path.relative_to(ROOT).as_posix(),
            "stderr_sha256": sha256_bytes(stderr),
            "stdout_bytes": len(stdout),
            "stdout_path": stdout_path.relative_to(ROOT).as_posix(),
            "stdout_sha256": sha256_bytes(stdout),
        }
    )
    if check and returncode:
        raise RuntimeError(
            f"command failed ({returncode}): {argv!r}\n{stderr[-2000:].decode(errors='replace')}"
        )
    return result


def compose_env() -> dict[str, str]:
    return {
        **os.environ,
        "R2C_BROWSER_IMAGE": IMAGE,
        "R2C_EVIDENCE_DIR": str(EVIDENCE),
        "R2C_PROJECT_NAME": PROJECT,
    }


def compose(
    *arguments: str, check: bool = True, timeout: int = 120
) -> subprocess.CompletedProcess[bytes]:
    return run(
        [
            "docker",
            "compose",
            "--project-name",
            PROJECT,
            "-f",
            str(HARNESS / "compose.yaml"),
            *arguments,
        ],
        check=check,
        timeout=timeout,
        env=compose_env(),
    )


def json_output(argv: list[str], *, timeout: int = 120) -> Any:
    return json.loads(run(argv, timeout=timeout).stdout)


def canonical_lines(raw: bytes) -> list[str]:
    return sorted(
        {
            line.strip()
            for line in raw.decode(errors="replace").splitlines()
            if line.strip()
        }
    )


def docker_snapshot() -> dict[str, list[str]]:
    return {
        "builders": canonical_lines(
            run(["docker", "buildx", "ls", "--format", "{{.Name}}"], check=False).stdout
        ),
        "containers": canonical_lines(
            run(
                [
                    "docker",
                    "ps",
                    "-a",
                    "--no-trunc",
                    "--format",
                    "{{.ID}} {{.Image}} {{.Names}}",
                ],
                check=False,
            ).stdout
        ),
        "images": canonical_lines(
            run(
                [
                    "docker",
                    "image",
                    "ls",
                    "--no-trunc",
                    "--format",
                    "{{.Repository}}:{{.Tag}} {{.ID}}",
                ],
                check=False,
            ).stdout
        ),
        "networks": canonical_lines(
            run(
                ["docker", "network", "ls", "--no-trunc", "--format", "{{.ID}} {{.Name}}"],
                check=False,
            ).stdout
        ),
        "volumes": canonical_lines(
            run(["docker", "volume", "ls", "--format", "{{.Name}}"], check=False).stdout
        ),
    }


def hardened_prefix(user: str = "0:0") -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--user",
        user,
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "128",
        "--memory",
        "768m",
        "--cpus",
        "1",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,noexec,size=256m",  # noqa: S108
    ]


def audit(script: str, *arguments: str, timeout: int = 600) -> bytes:
    mount = f"type=bind,src={R1D / 'audit'},dst=/audit,readonly"
    return run(
        [
            *hardened_prefix(),
            "--mount",
            mount,
            "--env",
            "PYTHONPATH=/audit",
            "--entrypoint",
            "python",
            IMAGE,
            f"/audit/{script}",
            *arguments,
        ],
        timeout=timeout,
    ).stdout


def prior_failure_expected() -> dict[str, str]:
    document = json.loads(
        (R1D / "evidence" / "r1d-a2" / "protected-files-before.json").read_text(
            encoding="utf-8"
        )
    )
    expected = document.get("browser-r2c")
    if not isinstance(expected, dict) or len(expected) != 23:
        raise RuntimeError("R1D did not preserve the authoritative 23-file R2C failure set")
    return dict(sorted(expected.items()))


def prior_failure_actual(expected: dict[str, str]) -> dict[str, str]:
    actual: dict[str, str] = {}
    for relative in expected:
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"R2C prior failure file missing or abnormal: {relative}")
        actual[relative] = sha256_file(path)
    return actual


def project_objects() -> tuple[list[str], list[str]]:
    containers = run(
        ["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={PROJECT}"],
        check=False,
    ).stdout.decode().split()
    networks = run(
        [
            "docker",
            "network",
            "ls",
            "-q",
            "--filter",
            f"label=com.docker.compose.project={PROJECT}",
        ],
        check=False,
    ).stdout.decode().split()
    return containers, networks


def ensure_clean_start() -> None:
    if not re.fullmatch(r"flowtracer-r2c-a2-[a-z0-9][a-z0-9-]{7,80}", RUN_ID):
        raise RuntimeError("invalid explicit R2C run identity")
    containers, networks = project_objects()
    checks = [
        run(["docker", "buildx", "inspect", BUILDER], check=False).returncode != 0,
        run(["docker", "image", "inspect", IMAGE], check=False).returncode != 0,
        run(["docker", "container", "inspect", PROBE_CONTAINER], check=False).returncode != 0,
        run(["docker", "container", "inspect", CONTROL_CONTAINER], check=False).returncode != 0,
    ]
    if containers or networks or not all(checks):
        raise RuntimeError("R2C attributable object already exists; refusing reuse")
    if run(["docker", "image", "inspect", "redis:7.4.11-alpine3.21"], check=False).returncode:
        raise RuntimeError("frozen Redis image is not locally available; refusing pull")
    with socket.socket() as verifier:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            verifier.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        verifier.bind(("127.0.0.1", CANARY_PORT))


def build_candidate() -> None:
    run(
        [
            "docker",
            "buildx",
            "create",
            "--name",
            BUILDER,
            "--driver",
            "docker-container",
            "--driver-opt",
            f"image={BUILDKIT_IMAGE}",
            "--bootstrap",
        ],
        timeout=300,
    )
    build = run(
        [
            "docker",
            "buildx",
            "build",
            "--builder",
            BUILDER,
            "--platform=linux/amd64",
            "--no-cache",
            "--pull=false",
            "--progress=plain",
            "--load",
            "--target",
            "final",
            "-f",
            str(R1D / "Dockerfile"),
            "-t",
            IMAGE,
            str(R1D),
        ],
        check=False,
        timeout=3600,
    )
    (EVIDENCE / "build.txt").write_bytes(build.stdout + build.stderr)
    if build.returncode:
        raise RuntimeError(f"candidate build failed ({build.returncode})")


def validate_notice_archive(
    raw: bytes, inventory: dict[str, Any], sbom: dict[str, Any]
) -> dict[str, Any]:
    expected: dict[str, str] = {
        component["license_notice_file"]: component["license_notice_sha256"]
        for component in inventory["components"]
    }
    for component in sbom["components"]:
        properties = {item["name"]: item["value"] for item in component.get("properties", [])}
        notice = properties.get("flowtracer:persistent-notice")
        notice_hash = properties.get("flowtracer:notice-sha256")
        if notice is not None and notice_hash is not None:
            expected[notice] = notice_hash
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if (
            len(members) != 208
            or len(names) != len(set(names))
            or set(names) != set(expected)
            or not all(member.isfile() for member in members)
        ):
            raise RuntimeError("license archive members mismatch")
        actual = {
            member.name: sha256_bytes(archive.extractfile(member).read()) for member in members
        }
    if actual != expected:
        raise RuntimeError("license archive notice hashes mismatch")
    return {"files": len(actual), "members_match_inventory": True}


def identity_and_supply_chain() -> dict[str, Any]:
    identity_raw = run(
        [*hardened_prefix(), "-i", "--entrypoint", "python", IMAGE, "-"],
        input_bytes=(R1D / "audit" / "identity_manifest.py").read_bytes(),
        timeout=600,
    ).stdout
    identity_path = EVIDENCE / "identity-candidate.json"
    identity_path.write_bytes(identity_raw)
    validation = run(
        [sys.executable, str(R1D / "audit" / "validate_identity.py"), str(identity_path)]
    )
    identity_validation = json.loads(validation.stdout)
    authority = R1D / "evidence" / "r1d-a2" / "identity-build1.json"
    authority_raw = authority.read_bytes()
    identity = {
        "entry_count": identity_validation["entry_count"],
        "manifest_sha256": sha256_bytes(identity_raw),
        "payload_bytes": identity_validation["payload_bytes"],
        "payload_sha256": identity_validation["payload_sha256"],
    }
    byte_identical = identity_raw == authority_raw

    facts_program = b"""import hashlib,json,pathlib,subprocess
p=pathlib.Path('/opt/browser-r1c/chromium-1234/chrome-linux64/chrome')
root=pathlib.Path('/opt/flowtracer-r1d')
project=sorted(str(v) for v in root.rglob('*') if v.is_file())
audit_names={
 'browser_tree_manifest.py','export_notices.py','generate_sbom.py',
 'identity_manifest.py','license_policy.py','package_tree.py','validate_identity.py'
}
audit=sorted(
 str(v) for v in pathlib.Path('/opt').rglob('*')
 if v.is_file() and v.name in audit_names
)
print(json.dumps({
 'audit_files':audit,
 'path':str(p),
 'project_files':project,
 'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
 'version':subprocess.check_output([str(p),'--version'],text=True).strip(),
}))
"""
    facts = json.loads(
        run(
            [*hardened_prefix(), "-i", "--entrypoint", "python", IMAGE, "-"],
            input_bytes=facts_program,
            timeout=600,
        ).stdout
    )
    browser_tree_raw = audit("browser_tree_manifest.py")
    (EVIDENCE / "browser-tree.actual.json").write_bytes(browser_tree_raw)
    sbom_raw = audit("generate_sbom.py")
    inventory_raw = audit("generate_sbom.py", "--debian-license-inventory")
    license_raw = audit("export_notices.py")
    (EVIDENCE / "sbom.cdx.json").write_bytes(sbom_raw)
    (EVIDENCE / "debian-license-inventory.json").write_bytes(inventory_raw)
    (EVIDENCE / "licenses.tar").write_bytes(license_raw)
    sbom = json.loads(sbom_raw)
    inventory = json.loads(inventory_raw)
    license_validation = validate_notice_archive(license_raw, inventory, sbom)

    debian_program = b"""import subprocess
raw=subprocess.check_output(['dpkg-query','-W'],text=True)
lines=sorted(line.rstrip('\\n').replace('\\t','=') for line in raw.splitlines())
print('\\n'.join(lines))
"""
    debian_actual = run(
        [*hardened_prefix(), "-i", "--entrypoint", "python", IMAGE, "-"],
        input_bytes=debian_program,
        timeout=300,
    ).stdout
    (EVIDENCE / "debian-packages.actual.lock").write_bytes(debian_actual)
    expected_runtime_files = [
        "/opt/flowtracer-r1d/runtime/entrypoint.py",
        "/opt/flowtracer-r1d/runtime/runtime_probe.py",
    ]
    checks = {
        "audit_absent": facts["audit_files"] == [],
        "browser_manifest": (
            browser_tree_raw == (R1D / "browser-tree.manifest.json").read_bytes()
            and len(json.loads(browser_tree_raw)["entries"]) == 619
            and sha256_bytes(browser_tree_raw) == EXPECTED_BROWSER_TREE_SHA
        ),
        "browser_path": facts["path"]
        == "/opt/browser-r1c/chromium-1234/chrome-linux64/chrome",
        "browser_sha256": facts["sha256"] == EXPECTED_BROWSER_SHA,
        "browser_version": facts["version"] == "Google Chrome for Testing 151.0.7922.34",
        "debian_inventory": len(inventory["components"]) == 206,
        "debian_lock": (
            debian_actual == (R1D / "debian-packages.lock").read_bytes()
            and len(debian_actual.splitlines()) == 206
            and sha256_bytes(debian_actual) == EXPECTED_DEBIAN_LOCK_SHA
        ),
        "license_inventory": (
            sha256_bytes(inventory_raw) == EXPECTED_INVENTORY_SHA
            and sha256_bytes(license_raw) == EXPECTED_LICENSE_ARCHIVE_SHA
            and license_validation == {"files": 208, "members_match_inventory": True}
        ),
        "runtime_allowlist": facts["project_files"] == expected_runtime_files,
        "sbom": len(sbom["components"]) == 231 and sha256_bytes(sbom_raw) == EXPECTED_SBOM_SHA,
    }
    gate = {
        "identity": identity,
        "manifest_byte_identical": byte_identical,
        "status": "PASS"
        if identity == EXPECTED_IDENTITY and byte_identical and all(checks.values())
        else "BLOCKED",
        "supply_chain": {
            "audit_files": facts["audit_files"],
            "browser": {
                "path": facts["path"],
                "sha256": facts["sha256"],
                "version": facts["version"],
            },
            "checks": checks,
            "browser_tree_entries": len(json.loads(browser_tree_raw)["entries"]),
            "debian_inventory_components": len(inventory["components"]),
            "debian_license_notice_records": sum(
                bool(component.get("license_notice_file"))
                and bool(component.get("license_notice_sha256"))
                for component in inventory["components"]
            ),
            "debian_inventory_sha256": sha256_bytes(inventory_raw),
            "debian_lock_sha256": sha256_bytes(debian_actual),
            "license_archive_sha256": sha256_bytes(license_raw),
            "license_archive_validation": license_validation,
            "project_files": facts["project_files"],
            "sbom_components": len(sbom["components"]),
            "sbom_sha256": sha256_bytes(sbom_raw),
        },
    }
    write_json(EVIDENCE / "identity-gate.json", gate)
    if gate["status"] != "PASS":
        raise RuntimeError("Runtime Identity v2 or supply-chain hard gate failed")
    return gate


def wait_for_host_canary() -> dict[str, Any]:
    deadline = time.monotonic() + 10
    attempts = 0
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        attempts += 1
        try:
            with socket.create_connection(("127.0.0.1", CANARY_PORT), timeout=0.5) as canary:
                response = canary.recv(32)
        except OSError as error:
            last_error = error
            time.sleep(0.2)
            continue
        if not response.startswith(b"R2C_HOST_CANARY"):
            raise RuntimeError("host canary returned an unexpected response")
        return {
            "address": "127.0.0.1",
            "attempts": attempts,
            "port": CANARY_PORT,
            "response": "R2C_HOST_CANARY",
        }
    raise RuntimeError(f"host canary was not ready: {last_error}")


def topology() -> dict[str, Any]:
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
    networks: dict[str, list[str]] = {}
    runtime: dict[str, dict[str, Any]] = {}
    privileged: list[str] = []
    socket_mounts: list[str] = []
    for role, name in names.items():
        inspected = json_output(["docker", "container", "inspect", name])[0]
        host = inspected["HostConfig"]
        networks[role] = sorted(
            value.removeprefix(f"{PROJECT}_")
            for value in inspected["NetworkSettings"]["Networks"]
        )
        has_socket = any(
            mount["Destination"] == "/var/run/docker.sock" for mount in inspected["Mounts"]
        )
        runtime[role] = {
            "cap_drop": sorted(host.get("CapDrop") or []),
            "dns": host.get("Dns") or [],
            "docker_socket": has_socket,
            "memory": host["Memory"],
            "nano_cpus": host["NanoCpus"],
            "network_mode": host["NetworkMode"],
            "pids_limit": host["PidsLimit"],
            "port_bindings": host.get("PortBindings") or {},
            "privileged": host["Privileged"],
            "read_only_rootfs": host["ReadonlyRootfs"],
            "security_opt": sorted(host.get("SecurityOpt") or []),
            "tmpfs": host.get("Tmpfs") or {},
            "user": inspected["Config"]["User"],
        }
        if host["Privileged"] or host["NetworkMode"] == "host":
            privileged.append(role)
        if has_socket:
            socket_mounts.append(role)
    internal = []
    for short_name in ("r2c_browser", "r2c_fixture"):
        inspected = json_output(
            ["docker", "network", "inspect", f"{PROJECT}_{short_name}"]
        )[0]
        if inspected["Internal"]:
            internal.append(short_name)
    return {
        "docker_socket_mounts": sorted(socket_mounts),
        "internal_networks": sorted(internal),
        "networks": networks,
        "privileged": sorted(privileged),
        "project": PROJECT,
        "runtime": runtime,
    }


def run_network_matrix() -> dict[str, Any]:
    for name in ("proxy-events.jsonl", "dns-events.jsonl", "fixture-events.jsonl"):
        path = EVIDENCE / name
        if path.exists():
            raise RuntimeError(f"network evidence path already exists: {path}")
    compose("config", "--quiet", timeout=30)
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
        timeout=90,
    )
    host_control = wait_for_host_canary()
    control = compose(
        "run",
        "--name",
        CONTROL_CONTAINER,
        "--no-deps",
        "control-client",
        check=False,
        timeout=30,
    )
    control_lines = [line for line in control.stdout.decode().splitlines() if line.startswith("{")]
    if control.returncode or not control_lines:
        failure = control.stderr[-2000:].decode(errors="replace")
        raise RuntimeError(
            f"control client failed ({control.returncode}): {failure}"
        )
    control_result = json.loads(control_lines[-1])
    write_json(EVIDENCE / "control-client.json", control_result)

    probe = compose(
        "run",
        "--name",
        PROBE_CONTAINER,
        "--no-deps",
        "browser",
        check=False,
        timeout=180,
    )
    (EVIDENCE / "browser-runtime.txt").write_bytes(probe.stdout + probe.stderr)
    probe_lines = [line for line in probe.stdout.decode().splitlines() if line.startswith("{")]
    if probe.returncode or not probe_lines:
        failure = probe.stderr[-4000:].decode(errors="replace")
        raise RuntimeError(
            f"browser matrix failed ({probe.returncode}): {failure}"
        )
    browser_result = json.loads(probe_lines[-1])
    write_json(EVIDENCE / "browser-result.json", browser_result)
    topology_result = topology()
    topology_result["host_canary_control"] = host_control
    write_json(EVIDENCE / "topology.json", topology_result)
    return {"browser": browser_result, "control": control_result, "topology": topology_result}


def cleanup(docker_before: dict[str, list[str]]) -> dict[str, Any]:
    run(
        ["docker", "container", "rm", "-f", PROBE_CONTAINER, CONTROL_CONTAINER],
        check=False,
        timeout=60,
    )
    compose("down", "--remove-orphans", check=False, timeout=60)
    run(["docker", "image", "rm", "-f", IMAGE], check=False, timeout=300)
    run(["docker", "buildx", "rm", "-f", BUILDER], check=False, timeout=300)
    containers, networks = project_objects()
    port_deadline = time.monotonic() + 10
    port_attempts = 0
    port_available = False
    while time.monotonic() < port_deadline:
        port_attempts += 1
        try:
            with socket.socket() as verifier:
                if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    verifier.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                verifier.bind(("127.0.0.1", CANARY_PORT))
            port_available = True
            break
        except OSError:
            time.sleep(0.2)
    volumes = run(
        ["docker", "volume", "ls", "-q", "--filter", f"name={BUILDER}"],
        check=False,
    ).stdout.decode().splitlines()
    result = {
        "builder_absent": run(
            ["docker", "buildx", "inspect", BUILDER], check=False
        ).returncode
        != 0,
        "containers_remaining": containers,
        "host_port_attempts": port_attempts,
        "host_port_available": port_available,
        "image_absent": run(["docker", "image", "inspect", IMAGE], check=False).returncode
        != 0,
        "networks_remaining": networks,
        "volumes_remaining": volumes,
    }
    docker_after = docker_snapshot()
    write_json(EVIDENCE / "protected-docker-after.json", docker_after)
    result["docker_snapshot_unchanged"] = docker_after == docker_before
    return result


def main() -> int:
    if EVIDENCE.is_symlink() or (EVIDENCE.exists() and not EVIDENCE.is_dir()):
        raise RuntimeError(f"invalid evidence path: {EVIDENCE}")
    if EVIDENCE.exists() and any(EVIDENCE.iterdir()):
        raise RuntimeError(f"refusing to overwrite existing evidence: {EVIDENCE}")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    started_at = now()
    result: dict[str, Any] = {
        "network_matrix_started": False,
        "public_network_or_target": False,
        "run_id": RUN_ID,
        "started_at": started_at,
        "status": "RUNNING",
    }
    protected_before = {
        name: tree_hashes(ROOT.parent / name) for name in PROTECTED
    }
    prior_expected = prior_failure_expected()
    prior_before = prior_failure_actual(prior_expected)
    write_json(EVIDENCE / "protected-files-before.json", protected_before)
    write_json(EVIDENCE / "prior-failure-files-before.json", prior_before)
    docker_before: dict[str, list[str]] = {}
    severity = "P1"
    try:
        if prior_before != prior_expected:
            raise RuntimeError("R2C prior BLOCKED evidence does not match R1D-preserved authority")
        ensure_clean_start()
        docker_before = docker_snapshot()
        write_json(EVIDENCE / "protected-docker-before.json", docker_before)
        build_candidate()
        identity_gate = identity_and_supply_chain()
        result["identity_gate"] = identity_gate
        result["network_matrix_started"] = True
        severity = "P0"
        network = run_network_matrix()
        result["network"] = {
            "browser_uid": network["browser"]["uid"],
            "control_endpoint": network["control"],
            "internal_networks": network["topology"]["internal_networks"],
        }
        result["status"] = "PASS"
        result["severity"] = None
    except Exception as error:
        result.update(
            {
                "blocking_error": f"{type(error).__name__}: {error}",
                "severity": severity,
                "status": "BLOCKED",
            }
        )
    finally:
        if docker_before:
            cleanup_result = cleanup(docker_before)
        else:
            cleanup_result = {
                "builder_absent": True,
                "containers_remaining": [],
                "docker_snapshot_unchanged": True,
                "host_port_attempts": 0,
                "host_port_available": True,
                "image_absent": True,
                "networks_remaining": [],
                "volumes_remaining": [],
            }
        write_json(EVIDENCE / "cleanup.json", cleanup_result)
        protected_after = {
            name: tree_hashes(ROOT.parent / name) for name in PROTECTED
        }
        prior_after = prior_failure_actual(prior_expected)
        write_json(EVIDENCE / "protected-files-after.json", protected_after)
        write_json(EVIDENCE / "prior-failure-files-after.json", prior_after)
        result["cleanup"] = cleanup_result
        result["protected_files_unchanged"] = protected_after == protected_before
        result["prior_failure_unchanged"] = (
            prior_before == prior_expected and prior_after == prior_expected
        )
        cleanup_ok = (
            cleanup_result["builder_absent"]
            and cleanup_result["image_absent"]
            and cleanup_result["containers_remaining"] == []
            and cleanup_result["networks_remaining"] == []
            and cleanup_result["volumes_remaining"] == []
            and cleanup_result["host_port_available"]
            and cleanup_result["docker_snapshot_unchanged"]
        )
        if result["status"] == "PASS" and (
            not cleanup_ok
            or not result["protected_files_unchanged"]
            or not result["prior_failure_unchanged"]
        ):
            result.update(
                {
                    "blocking_error": "post-run protection or exact cleanup gate failed",
                    "severity": "P1",
                    "status": "BLOCKED",
                }
            )
        result["ended_at"] = now()
        result["duration_seconds"] = round(
            (
                dt.datetime.fromisoformat(result["ended_at"])
                - dt.datetime.fromisoformat(started_at)
            ).total_seconds(),
            3,
        )
        write_json(EVIDENCE / "execution-ledger.json", ledger)
        write_json(EVIDENCE / "result.json", result)

    if result["status"] == "PASS":
        try:
            validation = run(
                [sys.executable, str(HARNESS / "validate_evidence.py"), str(EVIDENCE)],
                timeout=30,
            )
            result["validation"] = json.loads(validation.stdout)
        except Exception as error:
            message = f"evidence validation failed: {type(error).__name__}: {error}"
            result.update(
                {
                    "blocking_error": message,
                    "severity": "P1",
                    "status": "BLOCKED",
                }
            )
        write_json(EVIDENCE / "execution-ledger.json", ledger)
        write_json(EVIDENCE / "result.json", result)

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 78


if __name__ == "__main__":
    raise SystemExit(main())
