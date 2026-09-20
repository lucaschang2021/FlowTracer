from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
EVIDENCE = ROOT / "evidence" / "r1e-a2"
HISTORICAL_EVIDENCE_ROOTS = {
    "r1e-first-session": ROOT / "evidence",
    "r2c-a2-blocked": ROOT.parent / "browser-r2c" / "evidence" / "r2c-a2",
}
RUN_ID = "flowtracer-r1e-a2-20260920-final-a"
BUILDER = f"{RUN_ID}-builder"
IMAGES = {name: f"flowtracer-browser-r1e:{RUN_ID}-{name}" for name in ("build1", "build2")}
CONTAINERS = {name: f"{RUN_ID}-runtime-{name}" for name in IMAGES}
BUILDKIT_IMAGE = (
    "moby/buildkit@sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8"
)
EXPECTED_BROWSER_SHA = "0b20b130e7edd9dd51873be867761295fe0cfad490c2b9a64f95bd3cfc08fa71"
EXPECTED_BROWSER_TREE_SHA = "197d911b97e67180aef120d7cffb974436dcbcbe4acce566809b6d0e1363390a"
EXPECTED_REQUIREMENTS_SHA = "93ecf377d3a0dba3abb0a6dbb818ffb566a496df528de70435fd9366da3c488b"
EXPECTED_SBOM_SHA = "a8d6ae5e450b10bd40d90f6d56a0e69742479cfaff79398c0d2fb0696cfcf774"
EXPECTED_INVENTORY_SHA = "bee9c30ae016be592521c383b9bb0be74f39892415ed28f9122d5b7ccced81da"
PROTECTED = (
    "browser-r1",
    "browser-r2",
    "browser-r1c",
    "browser-r1d",
    "browser-r2c",
    "browser-r3",
)
PROTECTED_EXPECTED = {
    "browser-r1d": {
        "files": 170,
        "payload_bytes": 16889,
        "sha256": "4d62e46320a9f691e9dc84a6cf89e04bcd02f110c073c9da63f280b29ad0814e",
    },
    "browser-r2c": {
        "files": 124,
        "payload_bytes": 12485,
        "sha256": "963317fca6327f9767db69940a790a9d71ae27df8d6d70656a264ad8d732b2b7",
    },
    "browser-r3": {
        "files": 12,
        "payload_bytes": 1027,
        "sha256": "58efd172a2e4b7e0ff665ba01b2dcd679b6e65587e2c4fcbbb6b17c4e427e708",
    },
}
AUDIT_BASENAMES = {
    "account_metadata.py",
    "browser_tree_manifest.py",
    "export_notices.py",
    "generate_sbom.py",
    "identity_manifest.py",
    "license_policy.py",
    "package_tree.py",
    "validate_identity.py",
}
RUNTIME_ENV = {
    "HOME": "/tmp/flowtracer-r1c-home",  # noqa: S108 - controlled container tmpfs
    "XDG_CONFIG_HOME": "/tmp/flowtracer-r1c-config",  # noqa: S108
    "XDG_CACHE_HOME": "/tmp/flowtracer-r1c-cache",  # noqa: S108
}
commands: list[dict[str, Any]] = []


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
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"), key=lambda value: value.as_posix())
        if path.is_file()
    }


def tree_identity(root: Path) -> dict[str, int | str]:
    hashes = tree_hashes(root)
    payload = b"".join(
        relative.encode("utf-8") + b" " + hashes[relative].encode("ascii") + b"\n"
        for relative in sorted(hashes)
    )
    return {
        "files": len(hashes),
        "payload_bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }


def validate_inputs() -> dict[str, str]:
    authoritative_debian_lock = ROOT.parent / "browser-r1d" / "debian-packages.lock"
    expected = {
        "browser-tree.manifest.json": EXPECTED_BROWSER_TREE_SHA,
        "debian-packages.lock": sha256_file(authoritative_debian_lock),
        "requirements.lock": EXPECTED_REQUIREMENTS_SHA,
    }
    actual = {name: sha256_file(ROOT / name) for name in expected}
    if actual != expected:
        raise RuntimeError(f"R1D locked inputs changed: {actual} != {expected}")
    return actual


def canonical_snapshot_lines(raw: bytes) -> list[str]:
    return sorted(set(raw.decode("utf-8").splitlines()))


def parse_builder_snapshot(raw: bytes, *, exit_code: int = 0) -> list[dict[str, Any]]:
    if exit_code != 0:
        raise RuntimeError(f"buildx builder snapshot failed with exit code {exit_code}")
    records: dict[str, dict[str, Any]] = {}
    for index, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"invalid buildx JSON record at line {index}") from error
        if not isinstance(value, dict):
            raise RuntimeError(f"buildx JSON record {index} is not an object")
        name = value.get("Name")
        driver = value.get("Driver")
        dynamic = value.get("Dynamic")
        nodes = value.get("Nodes")
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(driver, str)
            or not driver
            or not isinstance(dynamic, bool)
            or not isinstance(nodes, list)
            or not nodes
        ):
            raise RuntimeError(f"incomplete buildx JSON record at line {index}")
        stable_nodes: list[dict[str, Any]] = []
        for node in nodes:
            if not isinstance(node, dict):
                raise RuntimeError(f"invalid node in buildx JSON record {index}")
            node_name = node.get("Name")
            endpoint = node.get("Endpoint")
            status = node.get("Status")
            version = node.get("Version")
            driver_opts = node.get("DriverOpts", {})
            ids = node.get("IDs", [])
            flags = node.get("Flags", [])
            if (
                not isinstance(node_name, str)
                or not node_name
                or not isinstance(endpoint, str)
                or not endpoint
                or not isinstance(status, str)
                or not status
                or not isinstance(version, str)
                or not version
                or not isinstance(driver_opts, dict)
                or not isinstance(ids, list)
                or not all(isinstance(item, str) and item for item in ids)
                or not isinstance(flags, list)
                or not all(isinstance(item, str) and item for item in flags)
            ):
                raise RuntimeError(f"incomplete node in buildx JSON record {index}")
            stable_nodes.append(
                {
                    "driver_opts": driver_opts,
                    "endpoint": endpoint,
                    "flags": sorted(set(flags)),
                    "ids": sorted(set(ids)),
                    "name": node_name,
                    "status": status,
                    "version": version,
                }
            )
        stable = {
            "driver": driver,
            "dynamic": dynamic,
            "name": name,
            "nodes": sorted(
                stable_nodes,
                key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
            ),
        }
        previous = records.get(name)
        if previous is not None and previous != stable:
            raise RuntimeError(f"conflicting duplicate buildx builder: {name}")
        records[name] = stable
    if not records:
        raise RuntimeError("buildx builder snapshot is unexpectedly empty")
    return sorted(records.values(), key=lambda item: item["name"])


def historical_evidence_hashes() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for label, root in HISTORICAL_EVIDENCE_ROOTS.items():
        for path in sorted(root.rglob("*"), key=lambda value: value.as_posix()):
            if not path.is_file() or path == EVIDENCE or EVIDENCE in path.parents:
                continue
            hashes[f"{label}/{path.relative_to(root).as_posix()}"] = sha256_file(path)
    return hashes


def self_check() -> dict[str, Any]:
    authoritative = sha256_file(ROOT.parent / "browser-r1d" / "debian-packages.lock")
    candidate = sha256_file(ROOT / "debian-packages.lock")
    if candidate != authoritative:
        raise RuntimeError("R1E Debian lock differs from authoritative R1D input")
    builder_a = {
        "Driver": "docker",
        "Dynamic": False,
        "Name": "a",
        "Nodes": [{"Endpoint": "a", "Name": "a0", "Status": "running", "Version": "v1"}],
    }
    builder_b = {
        "Driver": "docker-container",
        "Dynamic": False,
        "Name": "b",
        "Nodes": [
            {
                "DriverOpts": {"image": "locked"},
                "Endpoint": "b",
                "Flags": ["z", "a", "z"],
                "IDs": ["2", "1", "2"],
                "Name": "b0",
                "Status": "running",
                "Version": "v1",
            }
        ],
    }

    def encoded(value: object) -> bytes:
        return json.dumps(value, separators=(",", ":")).encode() + b"\n"

    left = parse_builder_snapshot(encoded(builder_b) + encoded(builder_a) + encoded(builder_a))
    right = parse_builder_snapshot(encoded(builder_a) + encoded(builder_b))
    if left != right or [item["name"] for item in left] != ["a", "b"]:
        raise RuntimeError("buildx JSON stable set canonicalization regression")
    invalid_builder_cases = (
        (b"", 1),
        (b"", 0),
        (b"not-json\n", 0),
        (encoded({"Name": "a", "Driver": "docker", "Dynamic": False, "Nodes": []}), 0),
        (
            encoded(builder_a) + encoded({**builder_a, "Driver": "docker-container"}),
            0,
        ),
    )
    for raw, exit_code in invalid_builder_cases:
        try:
            parse_builder_snapshot(raw, exit_code=exit_code)
        except RuntimeError:
            continue
        raise RuntimeError("invalid buildx builder snapshot accepted")
    first_result = json.loads((ROOT / "evidence" / "result.json").read_text(encoding="utf-8"))
    r2c_result = json.loads(
        (ROOT.parent / "browser-r2c" / "evidence" / "r2c-a2" / "result.json").read_text(
            encoding="utf-8"
        )
    )
    historical_files = historical_evidence_hashes()
    if (
        first_result.get("status") != "PASS"
        or r2c_result.get("status") != "BLOCKED"
        or not historical_files
    ):
        raise RuntimeError("historical R1E/R2C-A2 evidence is missing")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    required = (
        "chage --lastday 0 flowtracer",
        "cp --preserve=mode,ownership /etc/shadow /etc/shadow-",
        'NF != 9 || $2 !~ /^!/ || $3 != "0"',
    )
    if not all(value in dockerfile for value in required):
        raise RuntimeError("deterministic account build assertions are incomplete")
    identity_source = (ROOT / "audit" / "identity_manifest.py").read_text(encoding="utf-8")
    if '"/etc/shadow"' in identity_source:
        raise RuntimeError("identity implementation must not special-case /etc/shadow")
    account_check = json.loads(
        subprocess.check_output(  # noqa: S603 - frozen local validation script
            [sys.executable, str(ROOT / "audit" / "account_metadata.py"), "--self-check"],
            cwd=REPO,
        )
    )
    return {
        "account_metadata": account_check,
        "builder_snapshot_negative_cases": len(invalid_builder_cases),
        "builder_snapshot_records": len(left),
        "debian_lock_sha256": authoritative,
        "historical_evidence_files": len(historical_files),
        "shadow_identity_special_case_absent": True,
        "snapshot_set_canonicalization": "PASS",
    }


def write_json(name: str, value: object) -> None:
    (EVIDENCE / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run(
    argv: list[str],
    *,
    input_bytes: bytes | None = None,
    timeout: int = 120,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    started = now()
    try:
        result = subprocess.run(  # noqa: S603 - frozen local argv only
            argv,
            cwd=REPO,
            input=input_bytes,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        if isinstance(stdout, str):
            stdout = stdout.encode("utf-8", errors="replace")
        if isinstance(stderr, str):
            stderr = stderr.encode("utf-8", errors="replace")
        record_command(argv, started, "TIMEOUT", input_bytes, stdout, stderr)
        raise RuntimeError(f"command timed out after {timeout}s: {argv!r}") from error
    record_command(argv, started, result.returncode, input_bytes, result.stdout, result.stderr)
    if check and result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {argv!r}\n"
            + result.stderr[-4000:].decode("utf-8", errors="replace")
        )
    return result


def record_command(
    argv: list[str],
    started: str,
    exit_code: int | str,
    input_bytes: bytes | None,
    stdout: bytes,
    stderr: bytes,
) -> None:
    index = len(commands) + 1
    command_root = EVIDENCE / "commands"
    command_root.mkdir(exist_ok=True)
    stdout_path = command_root / f"{index:03d}.stdout"
    stderr_path = command_root / f"{index:03d}.stderr"
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    commands.append(
        {
            "argv": argv,
            "ended_at": now(),
            "exit_code": exit_code,
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


def hardened_prefix(image: str, user: str) -> list[str]:
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
        "/tmp:rw,nosuid,noexec,size=256m",  # noqa: S108
    ]


def audit(image: str, script: str, *arguments: str, timeout: int = 600) -> bytes:
    mount = f"type=bind,src={ROOT / 'audit'},dst=/audit,readonly"
    return run(
        [
            *hardened_prefix(image, "0:0"),
            "--mount",
            mount,
            "--env",
            "PYTHONPATH=/audit",
            "--entrypoint",
            "python",
            image,
            f"/audit/{script}",
            *arguments,
        ],
        timeout=timeout,
    ).stdout


def docker_snapshot() -> dict[str, Any]:
    builder_result = run(["docker", "buildx", "ls", "--format", "json"])
    images = canonical_snapshot_lines(
        run(
            [
                "docker",
                "image",
                "ls",
                "--no-trunc",
                "--format",
                "{{.Repository}}:{{.Tag}} {{.ID}}",
            ]
        ).stdout
    )
    networks = canonical_snapshot_lines(
        run(["docker", "network", "ls", "--no-trunc", "--format", "{{.ID}} {{.Name}}"]).stdout
    )
    if not images or not networks:
        raise RuntimeError("Docker snapshot image/network set is unexpectedly empty")
    return {
        "builders": parse_builder_snapshot(
            builder_result.stdout, exit_code=builder_result.returncode
        ),
        "containers": canonical_snapshot_lines(
            run(
                ["docker", "ps", "-a", "--no-trunc", "--format", "{{.ID}} {{.Image}} {{.Names}}"]
            ).stdout
        ),
        "images": images,
        "networks": networks,
        "volumes": canonical_snapshot_lines(
            run(["docker", "volume", "ls", "--format", "{{.Name}}"]).stdout
        ),
    }


def ensure_clean_start() -> None:
    if run(["docker", "buildx", "inspect", BUILDER], check=False).returncode == 0:
        raise RuntimeError("R1E builder already exists")
    for value in (*IMAGES.values(), *CONTAINERS.values()):
        kind = "image" if value in IMAGES.values() else "container"
        if run(["docker", kind, "inspect", value], check=False).returncode == 0:
            raise RuntimeError(f"R1E object already exists: {value}")


def build(name: str) -> None:
    argv = [
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
        str(ROOT / "Dockerfile"),
        "-t",
        IMAGES[name],
        str(ROOT),
    ]
    result = run(argv, timeout=3600, check=False)
    (EVIDENCE / f"{name}.txt").write_bytes(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f"{name} failed ({result.returncode})")


def identity(image: str) -> tuple[dict[str, Any], bytes]:
    program = (ROOT / "audit" / "identity_manifest.py").read_bytes()
    output = run(
        [*hardened_prefix(image, "0:0"), "-i", "--entrypoint", "python", image, "-"],
        input_bytes=program,
        timeout=600,
    ).stdout
    return json.loads(output), output


def image_facts(image: str) -> dict[str, Any]:
    program = b"""import hashlib,json,pathlib,subprocess
p=pathlib.Path('/opt/browser-r1c/chromium-1234/chrome-linux64/chrome')
print(json.dumps({
    'path':str(p),
    'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
    'version':subprocess.check_output([str(p),'--version'],text=True).strip(),
}))
"""
    return json.loads(
        run(
            [*hardened_prefix(image, "0:0"), "-i", "--entrypoint", "python", image, "-"],
            input_bytes=program,
            timeout=300,
        ).stdout
    )


def account_metadata(image: str) -> dict[str, Any]:
    return json.loads(audit(image, "account_metadata.py", timeout=300))


def runtime_check(name: str) -> dict[str, Any]:
    image = IMAGES[name]
    container = CONTAINERS[name]
    argv = [
        "docker",
        "container",
        "create",
        "--name",
        container,
        "--network",
        "none",
        "--user",
        "10001:10001",
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
        "/tmp:rw,nosuid,noexec,size=256m",  # noqa: S108
    ]
    for key, value in RUNTIME_ENV.items():
        argv.extend(["--env", f"{key}={value}"])
    run([*argv, image])
    inspected = json.loads(run(["docker", "container", "inspect", container]).stdout)[0]
    started = run(["docker", "start", "-a", container], timeout=120, check=False)
    (EVIDENCE / f"runtime-{name}.txt").write_bytes(started.stdout + started.stderr)
    if started.returncode:
        raise RuntimeError(f"runtime probe failed: {name}")
    payload = json.loads(started.stdout.decode("utf-8").splitlines()[-1])
    run(["docker", "container", "rm", container])
    host = inspected["HostConfig"]
    security = {
        "cap_drop": sorted(host.get("CapDrop") or []),
        "memory": host["Memory"],
        "nano_cpus": host["NanoCpus"],
        "network_mode": host["NetworkMode"],
        "no_new_privileges": "no-new-privileges" in (host.get("SecurityOpt") or []),
        "pids_limit": host["PidsLimit"],
        "privileged": host["Privileged"],
        "read_only_rootfs": host["ReadonlyRootfs"],
        "tmpfs": host.get("Tmpfs") or {},
        "user": inspected["Config"]["User"],
    }
    expected = {
        "cap_drop": ["ALL"],
        "memory": 805306368,
        "nano_cpus": 1_000_000_000,
        "network_mode": "none",
        "no_new_privileges": True,
        "pids_limit": 128,
        "privileged": False,
        "read_only_rootfs": True,
        "tmpfs": {"/tmp": "rw,nosuid,noexec,size=256m"},  # noqa: S108
        "user": "10001:10001",
    }
    dynamic = payload.get("dynamic_fetcher", {})
    crashpad = dynamic.get("crashpad_databases", {})
    runtime_ok = (
        payload.get("uid") == 10001
        and payload.get("network") == "none"
        and payload.get("read_only_rootfs") is True
        and payload.get("engine_version") == "151.0.7922.34"
        and payload.get("executable") == "/opt/browser-r1c/chromium-1234/chrome-linux64/chrome"
        and dynamic.get("rendered") == "dynamic-rendered"
        and bool(dynamic.get("failure_type"))
        and dynamic.get("terminal_browser_processes") == []
        and dynamic.get("terminal_fixture_thread") == "stopped"
        and dynamic.get("runtime_environment") == RUNTIME_ENV
        and all(
            all(values.values())
            for values in dynamic.get("runtime_directories_absent_before", {}).values()
        )
        and all(
            all(values.values())
            for values in dynamic.get("runtime_directories_absent_after", {}).values()
        )
        and all(
            value.get("uid") == 10001
            and value.get("gid") == 10001
            and value.get("mode") == "0700"
            and value.get("path", "").startswith(f"{RUNTIME_ENV['XDG_CONFIG_HOME']}/")
            and value.get("path", "").endswith("/Crash Reports")
            for value in crashpad.values()
        )
        and set(crashpad) == {"failure", "render"}
        and dynamic.get("call_contract", {}).get("executable_path")
        == "/opt/browser-r1c/chromium-1234/chrome-linux64/chrome"
        and dynamic.get("call_contract", {}).get("render", {}).get("retries") == 1
        and dynamic.get("call_contract", {}).get("failure", {}).get("retries") == 1
    )
    if security != expected or not runtime_ok:
        raise RuntimeError(f"runtime boundary mismatch: {name}")
    return {"outer_deadline_seconds": 120, "probe": payload, "security": security}


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


def cleanup() -> dict[str, Any]:
    for container in CONTAINERS.values():
        run(["docker", "container", "rm", "-f", container], check=False)
    for image in IMAGES.values():
        run(["docker", "image", "rm", "-f", image], timeout=300, check=False)
    run(["docker", "buildx", "rm", "-f", BUILDER], timeout=300, check=False)
    return {
        "builder_absent": run(["docker", "buildx", "inspect", BUILDER], check=False).returncode
        != 0,
        "containers_absent": {
            name: run(["docker", "container", "inspect", value], check=False).returncode != 0
            for name, value in CONTAINERS.items()
        },
        "images_absent": {
            name: run(["docker", "image", "inspect", value], check=False).returncode != 0
            for name, value in IMAGES.items()
        },
        "volumes": run(["docker", "volume", "ls", "-q", "--filter", f"name={BUILDER}"], check=False)
        .stdout.decode()
        .splitlines(),
    }


def main() -> int:
    if EVIDENCE.is_symlink() or (EVIDENCE.exists() and not EVIDENCE.is_dir()):
        raise RuntimeError(f"invalid evidence path: {EVIDENCE}")
    if EVIDENCE.exists() and any(EVIDENCE.iterdir()):
        raise RuntimeError(f"refusing to reuse non-empty evidence directory: {EVIDENCE}")
    EVIDENCE.mkdir(exist_ok=True)
    historical_evidence_before = historical_evidence_hashes()
    protected_before = {name: tree_hashes(ROOT.parent / name) for name in PROTECTED}
    protected_identities_before = {name: tree_identity(ROOT.parent / name) for name in PROTECTED}
    for name, expected in PROTECTED_EXPECTED.items():
        if protected_identities_before[name] != expected:
            raise RuntimeError(
                f"protected package mismatch for {name}: "
                f"{protected_identities_before[name]} != {expected}"
            )
    docker_before = docker_snapshot()
    write_json("protected-files-before.json", protected_before)
    write_json("protected-identities-before.json", protected_identities_before)
    write_json("protected-docker-before.json", docker_before)
    write_json("historical-evidence-before.json", historical_evidence_before)
    result: dict[str, Any] = {"run_id": RUN_ID, "started_at": now(), "status": "RUNNING"}
    code = 78
    cleanup_authorized = False
    try:
        result["locked_inputs"] = validate_inputs()
        ensure_clean_start()
        cleanup_authorized = True
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
                "--use",
                "--bootstrap",
            ],
            timeout=300,
        )
        for name in IMAGES:
            build(name)

        manifests: dict[str, dict[str, Any]] = {}
        manifest_bytes: dict[str, bytes] = {}
        supply: dict[str, dict[str, Any]] = {}
        runtimes: dict[str, dict[str, Any]] = {}
        locked_browser = json.loads(
            (ROOT / "browser-tree.manifest.json").read_text(encoding="utf-8")
        )
        for name, image in IMAGES.items():
            manifests[name], manifest_bytes[name] = identity(image)
            (EVIDENCE / f"identity-{name}.json").write_bytes(manifest_bytes[name])
            browser_raw = audit(image, "browser_tree_manifest.py")
            browser = json.loads(browser_raw)
            sbom_raw = audit(image, "generate_sbom.py")
            inventory_raw = audit(image, "generate_sbom.py", "--debian-license-inventory")
            notices = audit(image, "export_notices.py")
            (EVIDENCE / f"browser-tree-{name}.json").write_bytes(browser_raw)
            (EVIDENCE / f"sbom-{name}.cdx.json").write_bytes(sbom_raw)
            (EVIDENCE / f"debian-license-inventory-{name}.json").write_bytes(inventory_raw)
            (EVIDENCE / f"licenses-{name}.tar").write_bytes(notices)
            sbom = json.loads(sbom_raw)
            inventory = json.loads(inventory_raw)
            facts = image_facts(image)
            account = account_metadata(image)
            identity_validation = json.loads(
                run(
                    [
                        sys.executable,
                        str(ROOT / "audit" / "validate_identity.py"),
                        str(EVIDENCE / f"identity-{name}.json"),
                    ]
                ).stdout
            )
            notice_validation = validate_notice_archive(notices, inventory, sbom)
            project_files = sorted(
                entry["path"]
                for entry in manifests[name]["entries"]
                if entry["type"] == "file" and entry["path"].startswith("/opt/flowtracer-r1e/")
            )
            expected_files = [
                "/opt/flowtracer-r1e/runtime/entrypoint.py",
                "/opt/flowtracer-r1e/runtime/runtime_probe.py",
            ]
            audit_files = sorted(
                entry["path"]
                for entry in manifests[name]["entries"]
                if entry["type"] == "file" and Path(entry["path"]).name in AUDIT_BASENAMES
            )
            checks = {
                "account_metadata": account
                == {
                    "account_name": "flowtracer",
                    "field_count": 9,
                    "password_locked": True,
                    "record_count": 1,
                    "sp_lstchg": "0",
                },
                "audit_absent": audit_files == [],
                "browser_manifest": (
                    browser == locked_browser
                    and len(browser["entries"]) == 619
                    and sha256_bytes(browser_raw) == EXPECTED_BROWSER_TREE_SHA
                ),
                "browser_path": facts["path"]
                == "/opt/browser-r1c/chromium-1234/chrome-linux64/chrome",
                "browser_sha256": facts["sha256"] == EXPECTED_BROWSER_SHA,
                "browser_version": facts["version"] == "Google Chrome for Testing 151.0.7922.34",
                "debian_inventory": len(inventory["components"]) == 206
                and sha256_bytes(inventory_raw) == EXPECTED_INVENTORY_SHA,
                "runtime_allowlist": project_files == expected_files,
                "sbom": len(sbom["components"]) == 231
                and sha256_bytes(sbom_raw) == EXPECTED_SBOM_SHA,
                "shadow_in_identity": any(
                    entry["path"] == "/etc/shadow" and entry["type"] == "file"
                    for entry in manifests[name]["entries"]
                ),
            }
            if not all(checks.values()):
                raise RuntimeError(f"identity/supply checks failed for {name}: {checks}")
            supply[name] = {
                "account_metadata": account,
                "audit_files": audit_files,
                "browser": facts,
                "checks": checks,
                "debian_inventory_sha256": sha256_bytes(inventory_raw),
                "identity_validation": identity_validation,
                "license_archive_sha256": sha256_bytes(notices),
                "license_archive_validation": notice_validation,
                "project_files": project_files,
                "sbom_sha256": sha256_bytes(sbom_raw),
            }
            runtimes[name] = runtime_check(name)

        if manifest_bytes["build1"] != manifest_bytes["build2"]:
            raise RuntimeError("Runtime Identity v2 manifests differ")
        if supply["build1"] != supply["build2"]:
            raise RuntimeError("supply-chain evidence differs")
        result.update(
            {
                "identity": {
                    "byte_identical": True,
                    "entry_count": manifests["build1"]["entry_count"],
                    "format": manifests["build1"]["format"],
                    "payload_bytes": manifests["build1"]["payload_bytes"],
                    "payload_sha256": manifests["build1"]["payload_sha256"],
                    "version": manifests["build1"]["version"],
                },
                "runtimes": runtimes,
                "status": "PASS",
                "supply_chain": supply,
            }
        )
        code = 0
    except Exception as error:
        result.update({"error": f"{type(error).__name__}: {error}", "status": "BLOCKED"})
    finally:
        result["cleanup"] = (
            cleanup()
            if cleanup_authorized
            else {
                "builder_absent": True,
                "containers_absent": {name: True for name in CONTAINERS},
                "images_absent": {name: True for name in IMAGES},
                "skipped": "pre-existing exact-name object detected; no cleanup authority",
                "volumes": [],
            }
        )
        protected_after = {name: tree_hashes(ROOT.parent / name) for name in PROTECTED}
        protected_identities_after = {name: tree_identity(ROOT.parent / name) for name in PROTECTED}
        historical_evidence_after = historical_evidence_hashes()
        docker_after = docker_snapshot()
        write_json("protected-files-after.json", protected_after)
        write_json("protected-identities-after.json", protected_identities_after)
        write_json("protected-docker-after.json", docker_after)
        write_json("historical-evidence-after.json", historical_evidence_after)
        result["protected_files_unchanged"] = protected_before == protected_after
        result["protected_identities_unchanged"] = (
            protected_identities_before == protected_identities_after
        )
        result["protected_docker_unchanged"] = docker_before == docker_after
        result["historical_evidence_unchanged"] = (
            historical_evidence_before == historical_evidence_after
        )
        clean = result["cleanup"]
        cleanup_ok = (
            clean["builder_absent"]
            and all(clean["containers_absent"].values())
            and all(clean["images_absent"].values())
            and not clean["volumes"]
        )
        if result.get("status") == "PASS" and (
            not cleanup_ok
            or not result["protected_files_unchanged"]
            or not result["protected_identities_unchanged"]
            or not result["protected_docker_unchanged"]
            or not result["historical_evidence_unchanged"]
        ):
            result["status"] = "BLOCKED"
            result["error"] = "post-run cleanup or protected-state mismatch"
            code = 78
        result["ended_at"] = now()
        write_json("result.json", result)
        write_json("execution-ledger.json", {"commands": commands, "run_id": RUN_ID})
    print(json.dumps(result, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-check"]:
        print(json.dumps(self_check(), indent=2, sort_keys=True))
        raise SystemExit(0)
    if sys.argv[1:]:
        raise SystemExit(f"unexpected arguments: {sys.argv[1:]!r}")
    raise SystemExit(main())
