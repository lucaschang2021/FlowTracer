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
R1E = ROOT.parent / "browser-r1e"
HARNESS = ROOT / "r2c_a4"
EVIDENCE = ROOT / "evidence" / "r2c-a4"
RUN_ID = "flowtracer-r2c-a4-20260920-final-a"
PROJECT = RUN_ID
BUILDERS = (f"{RUN_ID}-build1-builder", f"{RUN_ID}-build2-builder")
IMAGES = (
    f"flowtracer-browser-r2c:{RUN_ID}-build1",
    f"flowtracer-browser-r2c:{RUN_ID}-build2",
)
IMAGE = IMAGES[0]
PROBE_CONTAINER = f"{PROJECT}-browser-probe"
CONTROL_CONTAINER = f"{PROJECT}-control-client"
CANARY_PORT = 49274
BUILDKIT_IMAGE = (
    "moby/buildkit@sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8"
)
EXPECTED_IDENTITY = {
    "entry_count": 10340,
    "manifest_sha256": "f8d8bd0b64dfac53e244b00f29fbc9f18ed44b94491323b3f49ba2af191912e8",
    "payload_bytes": 1750557,
    "payload_sha256": "5f4cf5acdf06a86f9b8907375f6f8f239ecf18152762b889f1e254b01e447e3b",
}
EXPECTED_BROWSER_SHA = "0b20b130e7edd9dd51873be867761295fe0cfad490c2b9a64f95bd3cfc08fa71"
EXPECTED_BROWSER_TREE_SHA = "197d911b97e67180aef120d7cffb974436dcbcbe4acce566809b6d0e1363390a"
EXPECTED_DEBIAN_LOCK_SHA = "299a341b239c284c385ecacd9d3882bdf29472b28421075b369009f998b54b83"
EXPECTED_SBOM_SHA = "a8d6ae5e450b10bd40d90f6d56a0e69742479cfaff79398c0d2fb0696cfcf774"
EXPECTED_INVENTORY_SHA = "bee9c30ae016be592521c383b9bb0be74f39892415ed28f9122d5b7ccced81da"
EXPECTED_LICENSE_ARCHIVE_SHA = "4c89ab4aaca629a09009ef0a00b14dcbbc9e2418c32ffb40987a4f4ff621c780"
EXPECTED_REDIS_DIGEST = (
    "redis@sha256:520775a41a63e77e06c73e35d2fd9cc15921a609516818796b4ecbb813078bc7"
)
EXPECTED_R2C_HISTORY = {
    "files": 157,
    "payload_bytes": 15768,
    "sha256": "7a9d72235d19e298d8eff149d0ec1f70d23224ad8f65a6fa1efd3db98dac971f",
}
PROTECTED = (
    "browser-r1",
    "browser-r2",
    "browser-r1c",
    "browser-r1d",
    "browser-r1e",
    "browser-r3",
)
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


def historical_r2c_hashes() -> dict[str, str]:
    result: dict[str, str] = {}
    runner = Path(__file__).resolve()
    for path in ROOT.rglob("*"):
        if path == runner or HARNESS in path.parents or EVIDENCE in path.parents:
            continue
        if path.is_symlink():
            raise RuntimeError(f"R2C history contains symlink: {path}")
        if path.is_file():
            result[path.relative_to(ROOT).as_posix()] = sha256_file(path)
        elif not path.is_dir():
            raise RuntimeError(f"R2C history contains unsupported entry: {path}")
    return dict(sorted(result.items()))


def hashes_identity(entries: dict[str, str]) -> dict[str, int | str]:
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
        {line.strip() for line in raw.decode(errors="replace").splitlines() if line.strip()}
    )


def parse_builder_snapshot(raw: bytes, *, exit_code: int = 0) -> list[dict[str, Any]]:
    if exit_code != 0:
        raise RuntimeError(f"buildx snapshot failed with exit code {exit_code}")
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
        stable_nodes = []
        for node in nodes:
            if not isinstance(node, dict):
                raise RuntimeError(f"invalid buildx node at line {index}")
            stable = {
                "endpoint": node.get("Endpoint"),
                "name": node.get("Name"),
                "status": node.get("Status"),
                "version": node.get("Version"),
            }
            if not all(isinstance(item, str) and item for item in stable.values()):
                raise RuntimeError(f"incomplete buildx node at line {index}")
            stable_nodes.append(stable)
        stable_builder = {
            "driver": driver,
            "dynamic": dynamic,
            "name": name,
            "nodes": sorted(stable_nodes, key=lambda item: (item["name"], item["endpoint"])),
        }
        previous = records.get(name)
        if previous is not None and previous != stable_builder:
            raise RuntimeError(f"conflicting duplicate buildx builder: {name}")
        records[name] = stable_builder
    if not records:
        raise RuntimeError("buildx builder snapshot is unexpectedly empty")
    return sorted(records.values(), key=lambda item: item["name"])


def docker_snapshot() -> dict[str, Any]:
    builder_result = run(["docker", "buildx", "ls", "--format", "json"])
    images = canonical_lines(
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
    networks = canonical_lines(
        run(["docker", "network", "ls", "--no-trunc", "--format", "{{.ID}} {{.Name}}"]).stdout
    )
    if not images or not networks:
        raise RuntimeError("Docker snapshot image/network set is unexpectedly empty")
    return {
        "builders": parse_builder_snapshot(
            builder_result.stdout, exit_code=builder_result.returncode
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
            ).stdout
        ),
        "images": images,
        "networks": networks,
        "volumes": canonical_lines(run(["docker", "volume", "ls", "--format", "{{.Name}}"]).stdout),
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
    mount = f"type=bind,src={R1E / 'audit'},dst=/audit,readonly"
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
        (R1E / "evidence" / "r1e-a2" / "protected-files-before.json").read_text(encoding="utf-8")
    )
    expected = document.get("browser-r2c")
    if not isinstance(expected, dict) or len(expected) != 124:
        raise RuntimeError("R1E did not preserve the authoritative 124-file R2C history")
    return dict(sorted(expected.items()))


def prior_failure_actual(expected: dict[str, str]) -> dict[str, str]:
    actual: dict[str, str] = {}
    for relative in expected:
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"R2C prior failure file missing or abnormal: {relative}")
        actual[relative] = sha256_file(path)
    return actual


def self_check() -> dict[str, Any]:
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
        "Nodes": [{"Endpoint": "b", "Name": "b0", "Status": "running", "Version": "v1"}],
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
        (encoded(builder_a) + encoded({**builder_a, "Driver": "docker-container"}), 0),
    )
    for raw, exit_code in invalid_builder_cases:
        try:
            parse_builder_snapshot(raw, exit_code=exit_code)
        except RuntimeError:
            continue
        raise RuntimeError("invalid buildx builder snapshot accepted")

    authority = R1E / "evidence" / "r1e-a2" / "identity-build1.json"
    authority_validation = json.loads(
        subprocess.check_output(  # noqa: S603 - frozen local validator and authority
            [sys.executable, str(R1E / "audit" / "validate_identity.py"), str(authority)],
            cwd=REPO,
        )
    )
    authority_identity = {
        "entry_count": authority_validation["entry_count"],
        "manifest_sha256": sha256_file(authority),
        "payload_bytes": authority_validation["payload_bytes"],
        "payload_sha256": authority_validation["payload_sha256"],
    }
    if authority_identity != EXPECTED_IDENTITY:
        raise RuntimeError("R1E Runtime Identity v2 authority mismatch")
    if not any(
        entry.get("path") == "/etc/shadow" and entry.get("type") == "file"
        for entry in json.loads(authority.read_bytes())["entries"]
    ):
        raise RuntimeError("R1E authority excludes /etc/shadow")

    prior_expected = prior_failure_expected()
    if prior_failure_actual(prior_expected) != prior_expected:
        raise RuntimeError("R2C prior BLOCKED evidence differs from preserved authority")
    history = historical_r2c_hashes()
    if hashes_identity(history) != EXPECTED_R2C_HISTORY:
        raise RuntimeError("R2C-A3 and earlier history differs from frozen authority")
    return {
        "authority": authority_identity,
        "builder_snapshot_negative_cases": len(invalid_builder_cases),
        "builder_snapshot_records": len(left),
        "historical_r2c": hashes_identity(history),
        "prior_failure_files": len(prior_expected),
        "shadow_in_identity": True,
        "snapshot_set_canonicalization": "PASS",
    }


def project_objects() -> tuple[list[str], list[str]]:
    containers = (
        run(
            ["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={PROJECT}"],
            check=False,
        )
        .stdout.decode()
        .split()
    )
    networks = (
        run(
            [
                "docker",
                "network",
                "ls",
                "-q",
                "--filter",
                f"label=com.docker.compose.project={PROJECT}",
            ],
            check=False,
        )
        .stdout.decode()
        .split()
    )
    return containers, networks


def ensure_clean_start() -> None:
    if not re.fullmatch(r"flowtracer-r2c-a4-[a-z0-9][a-z0-9-]{7,80}", RUN_ID):
        raise RuntimeError("invalid explicit R2C run identity")
    containers, networks = project_objects()
    checks = [
        *(
            run(["docker", "buildx", "inspect", value], check=False).returncode != 0
            for value in BUILDERS
        ),
        *(
            run(["docker", "image", "inspect", value], check=False).returncode != 0
            for value in IMAGES
        ),
        run(["docker", "container", "inspect", PROBE_CONTAINER], check=False).returncode != 0,
        run(["docker", "container", "inspect", CONTROL_CONTAINER], check=False).returncode != 0,
    ]
    if containers or networks or not all(checks):
        raise RuntimeError("R2C attributable object already exists; refusing reuse")
    redis = run(["docker", "image", "inspect", "redis:7.4.11-alpine3.21"], check=False)
    if redis.returncode:
        raise RuntimeError("frozen Redis image is not locally available; refusing pull")
    redis_facts = json.loads(redis.stdout)[0]
    if (
        EXPECTED_REDIS_DIGEST not in redis_facts.get("RepoDigests", [])
        or redis_facts.get("Os") != "linux"
        or redis_facts.get("Architecture") != "amd64"
    ):
        raise RuntimeError("frozen Redis image digest/platform mismatch")
    with socket.socket() as verifier:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            verifier.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        verifier.bind(("127.0.0.1", CANARY_PORT))


def build_candidate(build_number: int) -> None:
    builder = BUILDERS[build_number - 1]
    image = IMAGES[build_number - 1]
    run(
        [
            "docker",
            "buildx",
            "create",
            "--name",
            builder,
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
            builder,
            "--platform=linux/amd64",
            "--no-cache",
            "--pull=false",
            "--progress=plain",
            "--load",
            "--target",
            "final",
            "-f",
            str(R1E / "Dockerfile"),
            "-t",
            image,
            str(R1E),
        ],
        check=False,
        timeout=3600,
    )
    (EVIDENCE / f"build{build_number}.txt").write_bytes(build.stdout + build.stderr)
    if build.returncode:
        raise RuntimeError(f"candidate build {build_number} failed ({build.returncode})")


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
    manifests: list[bytes] = []
    identities: list[dict[str, Any]] = []
    for build_number, image in enumerate(IMAGES, start=1):
        identity_raw = run(
            [*hardened_prefix(), "-i", "--entrypoint", "python", image, "-"],
            input_bytes=(R1E / "audit" / "identity_manifest.py").read_bytes(),
            timeout=600,
        ).stdout
        identity_path = EVIDENCE / f"identity-build{build_number}.json"
        identity_path.write_bytes(identity_raw)
        validation = run(
            [sys.executable, str(R1E / "audit" / "validate_identity.py"), str(identity_path)]
        )
        identity_validation = json.loads(validation.stdout)
        manifests.append(identity_raw)
        identities.append(
            {
                "entry_count": identity_validation["entry_count"],
                "manifest_sha256": sha256_bytes(identity_raw),
                "payload_bytes": identity_validation["payload_bytes"],
                "payload_sha256": identity_validation["payload_sha256"],
            }
        )
    authority = R1E / "evidence" / "r1e-a2" / "identity-build1.json"
    authority_raw = authority.read_bytes()
    identity = identities[0]
    byte_identical = all(value == authority_raw for value in manifests)
    builds_byte_identical = manifests[0] == manifests[1]

    facts_program = b"""import hashlib,json,pathlib,subprocess
p=pathlib.Path('/opt/browser-r1c/chromium-1234/chrome-linux64/chrome')
root=pathlib.Path('/opt/flowtracer-r1e')
project=sorted(str(v) for v in root.rglob('*') if v.is_file())
audit_names={
 'account_metadata.py','browser_tree_manifest.py','export_notices.py','generate_sbom.py',
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
    account = json.loads(audit("account_metadata.py"))
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
        "/opt/flowtracer-r1e/runtime/entrypoint.py",
        "/opt/flowtracer-r1e/runtime/runtime_probe.py",
    ]
    checks = {
        "account_metadata": account
        == {
            "account_name": "flowtracer",
            "field_count": 9,
            "password_locked": True,
            "record_count": 1,
            "sp_lstchg": "0",
        },
        "audit_absent": facts["audit_files"] == [],
        "browser_manifest": (
            browser_tree_raw == (R1E / "browser-tree.manifest.json").read_bytes()
            and len(json.loads(browser_tree_raw)["entries"]) == 619
            and sha256_bytes(browser_tree_raw) == EXPECTED_BROWSER_TREE_SHA
        ),
        "browser_path": facts["path"] == "/opt/browser-r1c/chromium-1234/chrome-linux64/chrome",
        "browser_sha256": facts["sha256"] == EXPECTED_BROWSER_SHA,
        "browser_version": facts["version"] == "Google Chrome for Testing 151.0.7922.34",
        "debian_inventory": len(inventory["components"]) == 206,
        "debian_lock": (
            debian_actual == (R1E / "debian-packages.lock").read_bytes()
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
        "shadow_in_identity": any(
            entry["path"] == "/etc/shadow" and entry["type"] == "file"
            for manifest in manifests
            for entry in json.loads(manifest)["entries"]
        ),
    }
    gate = {
        "build2_identity": identities[1],
        "builds_byte_identical": builds_byte_identical,
        "identity": identity,
        "manifest_byte_identical": byte_identical,
        "status": "PASS"
        if (
            identities == [EXPECTED_IDENTITY, EXPECTED_IDENTITY]
            and byte_identical
            and builds_byte_identical
            and all(checks.values())
        )
        else "BLOCKED",
        "supply_chain": {
            "account_metadata": account,
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
            value.removeprefix(f"{PROJECT}_") for value in inspected["NetworkSettings"]["Networks"]
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
        inspected = json_output(["docker", "network", "inspect", f"{PROJECT}_{short_name}"])[0]
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
        raise RuntimeError(f"control client failed ({control.returncode}): {failure}")
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
        raise RuntimeError(f"browser matrix failed ({probe.returncode}): {failure}")
    browser_result = json.loads(probe_lines[-1])
    write_json(EVIDENCE / "browser-result.json", browser_result)
    topology_result = topology()
    topology_result["host_canary_control"] = host_control
    write_json(EVIDENCE / "topology.json", topology_result)
    return {"browser": browser_result, "control": control_result, "topology": topology_result}


def cleanup(docker_before: dict[str, Any]) -> dict[str, Any]:
    run(
        ["docker", "container", "rm", "-f", PROBE_CONTAINER, CONTROL_CONTAINER],
        check=False,
        timeout=60,
    )
    compose("down", "--remove-orphans", check=False, timeout=60)
    run(["docker", "image", "rm", "-f", *IMAGES], check=False, timeout=300)
    for builder in BUILDERS:
        run(["docker", "buildx", "rm", "-f", builder], check=False, timeout=300)
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
    volumes = sorted(
        {
            volume
            for builder in BUILDERS
            for volume in run(
                ["docker", "volume", "ls", "-q", "--filter", f"name={builder}"],
                check=False,
            )
            .stdout.decode()
            .splitlines()
            if volume
        }
    )
    builders_absent = {
        value: run(["docker", "buildx", "inspect", value], check=False).returncode != 0
        for value in BUILDERS
    }
    images_absent = {
        value: run(["docker", "image", "inspect", value], check=False).returncode != 0
        for value in IMAGES
    }
    result = {
        "builder_absent": all(builders_absent.values()),
        "builders_absent": builders_absent,
        "containers_remaining": containers,
        "host_port_attempts": port_attempts,
        "host_port_available": port_available,
        "image_absent": all(images_absent.values()),
        "images_absent": images_absent,
        "networks_remaining": networks,
        "volumes_remaining": volumes,
    }
    docker_after = docker_snapshot()
    write_json(EVIDENCE / "protected-docker-after.json", docker_after)
    result["docker_snapshot_unchanged"] = docker_after == docker_before
    return result


def write_evidence_manifest() -> None:
    manifest_path = EVIDENCE / "evidence-manifest.json"
    entries = []
    for path in sorted(EVIDENCE.rglob("*"), key=lambda value: value.as_posix()):
        if path == manifest_path:
            continue
        if path.is_symlink():
            raise RuntimeError(f"evidence contains symlink: {path}")
        if path.is_file():
            entries.append(
                {
                    "bytes": path.stat().st_size,
                    "path": path.relative_to(EVIDENCE).as_posix(),
                    "sha256": sha256_file(path),
                }
            )
        elif not path.is_dir():
            raise RuntimeError(f"evidence contains unsupported entry: {path}")
    payload = b"".join(
        entry["path"].encode("utf-8")
        + b"\0"
        + str(entry["bytes"]).encode("ascii")
        + b"\0"
        + entry["sha256"].encode("ascii")
        + b"\n"
        for entry in entries
    )
    write_json(
        manifest_path,
        {
            "entry_count": len(entries),
            "entries": entries,
            "format": "flowtracer-evidence-tree-v1",
            "payload_bytes": len(payload),
            "payload_sha256": sha256_bytes(payload),
        },
    )


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
    protected_before = {name: tree_hashes(ROOT.parent / name) for name in PROTECTED}
    historical_before = historical_r2c_hashes()
    prior_expected = prior_failure_expected()
    prior_before = prior_failure_actual(prior_expected)
    write_json(EVIDENCE / "protected-files-before.json", protected_before)
    write_json(EVIDENCE / "historical-r2c-before.json", historical_before)
    write_json(EVIDENCE / "prior-failure-files-before.json", prior_before)
    docker_before: dict[str, Any] = {}
    severity = "P1"
    try:
        if prior_before != prior_expected:
            raise RuntimeError("R2C prior BLOCKED evidence does not match R1E-preserved authority")
        if hashes_identity(historical_before) != EXPECTED_R2C_HISTORY:
            raise RuntimeError("R2C-A3 and earlier history differs from frozen authority")
        ensure_clean_start()
        docker_before = docker_snapshot()
        write_json(EVIDENCE / "protected-docker-before.json", docker_before)
        build_candidate(1)
        build_candidate(2)
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
                "builders_absent": {value: True for value in BUILDERS},
                "containers_remaining": [],
                "docker_snapshot_unchanged": True,
                "host_port_attempts": 0,
                "host_port_available": True,
                "image_absent": True,
                "images_absent": {value: True for value in IMAGES},
                "networks_remaining": [],
                "volumes_remaining": [],
            }
        write_json(EVIDENCE / "cleanup.json", cleanup_result)
        protected_after = {name: tree_hashes(ROOT.parent / name) for name in PROTECTED}
        historical_after = historical_r2c_hashes()
        prior_after = prior_failure_actual(prior_expected)
        write_json(EVIDENCE / "protected-files-after.json", protected_after)
        write_json(EVIDENCE / "historical-r2c-after.json", historical_after)
        write_json(EVIDENCE / "prior-failure-files-after.json", prior_after)
        result["cleanup"] = cleanup_result
        result["protected_files_unchanged"] = protected_after == protected_before
        result["historical_r2c_unchanged"] = historical_after == historical_before
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
            or not result["historical_r2c_unchanged"]
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

    write_evidence_manifest()

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 78


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-check"]:
        print(json.dumps(self_check(), ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(0)
    if sys.argv[1:]:
        raise SystemExit(f"unexpected arguments: {sys.argv[1:]!r}")
    raise SystemExit(main())
