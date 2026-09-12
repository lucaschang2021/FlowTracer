from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
EVIDENCE = ROOT / "evidence"
DOCKERFILE = ROOT / "Dockerfile"
RUN_ID = "flowtracer-r1c-20260913-p1-runtime-dirs"
BUILDER = f"{RUN_ID}-builder"
BOOTSTRAP_IMAGE = "flowtracer-browser-r1c:r1c-20260913-p1-runtime-dirs-lock-export"
BUILD1_IMAGE = "flowtracer-browser-r1c:r1c-20260913-p1-runtime-dirs-build1"
BUILD2_IMAGE = "flowtracer-browser-r1c:r1c-20260913-p1-runtime-dirs-build2"
RUNTIME_CONTAINERS = (
    f"{RUN_ID}-runtime-build1",
    f"{RUN_ID}-runtime-build2",
)
PROTECTED_BUILDER = "flowtracer-r1-final-builder"
PROTECTED_IMAGES = (
    "flowtracer-browser-r1:r1-final-build1",
    "flowtracer-browser-r1:r1-final-build2",
)
BUILDKIT_IMAGE = (
    "moby/buildkit@sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8"
)
PREVIOUS_ATTEMPT = ROOT / "attempts" / "attempt-1-blocked-20260912T114447Z"
ROOT_INSPECTION_ATTEMPT = ROOT / "attempts" / "attempt-2-blocked-root-inspection"
RETRIES_ATTEMPT = ROOT / "attempts" / "attempt-3-blocked-retries-contract"
CRASHPAD_ATTEMPT = ROOT / "attempts" / "attempt-4-blocked-crashpad-database"
RUNTIME_ENV = {
    "HOME": "/tmp/flowtracer-r1c-home",
    "XDG_CONFIG_HOME": "/tmp/flowtracer-r1c-config",
    "XDG_CACHE_HOME": "/tmp/flowtracer-r1c-cache",
}
EXPECTED_R3_FILES = {
    "README.md": "a05c0dc413f386a8f2ec06f12e0df5d0fe8ab1ab54d83c2f1a1aa7ca8b070642",
    "browser_harness.py": "8ff2a2dd7c14b6bbf4aedd0e412a613f45b7115468a88c64f1759e69c7603b61",
    "compose.yaml": "0f798148e5ef37b40d6d6badf4d681a826e11f0a39b493564f07b62fde80d24a",
    "evidence/cleanup.json": "af60c9e323d57828258e0a74a17e8f5566e72bf63420124c47ef79057f3a80ef",
    "evidence/completion.json": "d6779d987ae6674a16207b75eea3f8127a1a0f56b1186d5f08c0d62eaf14f221",
    "evidence/execution-ledger.json": "070f5f7345384db27fa0fe09f7da2d6170f3cddda83f4673fd67a11a7f6fa69f",  # noqa: E501
    "evidence/initial-objects.json": "2d6727c2151bc6aec19e12e1c1a232ebe9f241a1580b628c5dd54a9e82e582cd",  # noqa: E501
    "fixture/fixture_server.py": "cabac7609e7d600162506167ce85424b8014466bfe34b26ffbea558873d4a0f4",
    "negative_tests.py": "69b3755eae64504e49677514a0d41c8279724a659947c3393e79319cde104a4e",
    "proxy/egress_proxy.py": "0e0586db1918b8ccf4443268e491aee2b4fcb9a26590c881c087d9e5feaaaece",
    "run_r3.py": "75e81b3ebe81ca26219e623ebc1ed90d364c2eb9da76258e8005090493e0d813",
    "validate_evidence.py": "abad4b781fd5a75b9ad3eba44bc64b458adc6568508f8c0251d4ad6b61ec33c8",
}
COMMANDS: list[dict[str, object]] = []


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def run(
    *args: str,
    check: bool = True,
    timeout: int | None = None,
    record_output: str | None = None,
) -> subprocess.CompletedProcess[bytes]:
    started = datetime.now(UTC)
    result = subprocess.run(  # noqa: S603 - argv is frozen by this evidence runner
        args,
        cwd=ROOT,
        check=False,
        capture_output=True,
        timeout=timeout,
    )
    ended = datetime.now(UTC)
    COMMANDS.append(
        {
            "argv": list(args),
            "ended_at": ended.isoformat(),
            "exit_code": result.returncode,
            "started_at": started.isoformat(),
        }
    )
    if record_output:
        (EVIDENCE / record_output).write_bytes(
            result.stdout + b"\n--- STDERR ---\n" + result.stderr
        )
    if check and result.returncode:
        stderr = result.stderr.decode("utf-8", errors="replace")[-4000:]
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args[:5])}\n{stderr}")
    return result


def output(*args: str, timeout: int | None = None) -> str:
    return run(*args, timeout=timeout).stdout.decode("utf-8")


def json_output(*args: str) -> Any:
    return json.loads(output(*args))


def write_json(name: str, value: object) -> None:
    (EVIDENCE / name).write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def r3_hashes() -> dict[str, str]:
    root = REPO / "backend" / "experiments" / "browser-r3"
    actual = {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
    if actual != {name: value.lower() for name, value in EXPECTED_R3_FILES.items()}:
        raise RuntimeError("protected browser-r3 failure evidence hash mismatch")
    return actual


def exact_objects() -> dict[str, object]:
    return {
        "builder_exists": run("docker", "buildx", "inspect", BUILDER, check=False).returncode == 0,
        "containers": {
            name: run("docker", "container", "inspect", name, check=False).returncode == 0
            for name in RUNTIME_CONTAINERS
        },
        "images": {
            name: run("docker", "image", "inspect", name, check=False).returncode == 0
            for name in (BOOTSTRAP_IMAGE, BUILD1_IMAGE, BUILD2_IMAGE)
        },
        "volumes": output("docker", "volume", "ls", "-q", "--filter", f"name={BUILDER}").split(),
    }


def protected_docker_objects() -> dict[str, object]:
    builder = run("docker", "buildx", "inspect", PROTECTED_BUILDER, check=False)
    images: dict[str, str | None] = {}
    for name in PROTECTED_IMAGES:
        result = run(
            "docker", "image", "inspect", "--format", "{{.Id}}", name, check=False
        )
        images[name] = (
            result.stdout.decode("utf-8").strip() if result.returncode == 0 else None
        )
    buildkit = run(
        "docker", "image", "inspect", "--format", "{{.Id}}", BUILDKIT_IMAGE, check=False
    )
    return {
        "buildkit_image_id": (
            buildkit.stdout.decode("utf-8").strip() if buildkit.returncode == 0 else None
        ),
        "historical_r1_builder_exists": builder.returncode == 0,
        "historical_r1_images": images,
    }


def ensure_clean_start() -> None:
    objects = exact_objects()
    write_json("initial-objects.json", objects)
    if objects["builder_exists"] or any(objects["containers"].values()):
        raise RuntimeError("R1C named builder/container already exists")
    if any(objects["images"].values()) or objects["volumes"]:
        raise RuntimeError("R1C named image/volume already exists")


def build(tag: str, target: str, log_name: str) -> None:
    run(
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
        target,
        "-f",
        str(DOCKERFILE),
        "-t",
        tag,
        str(ROOT),
        timeout=1800,
        record_output=log_name,
    )


def docker_python(image: str, script: str, *arguments: str) -> bytes:
    return run(
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--entrypoint",
        "python",
        image,
        f"/opt/flowtracer-r1c/scripts/{script}",
        *arguments,
        timeout=180,
    ).stdout


def capture_locks() -> None:
    manifest = docker_python(BOOTSTRAP_IMAGE, "browser_tree_manifest.py")
    json.loads(manifest)
    (ROOT / "browser-tree.manifest.json").write_bytes(manifest)
    packages = run(
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--entrypoint",
        "/usr/bin/dpkg-query",
        BOOTSTRAP_IMAGE,
        "-W",
        "-f=${binary:Package}\t${Version}\n",
        timeout=60,
    ).stdout.decode("utf-8")
    normalized = "\n".join(sorted(line.replace("\t", "=") for line in packages.splitlines())) + "\n"
    (ROOT / "debian-packages.lock").write_bytes(normalized.encode("utf-8"))


def resume_provenance() -> dict[str, object]:
    ledger_path = PREVIOUS_ATTEMPT / "execution-ledger.json"
    manifest_path = PREVIOUS_ATTEMPT / "browser-tree.manifest.json"
    lock_path = PREVIOUS_ATTEMPT / "debian-packages.lock.crlf"
    for path in (ledger_path, manifest_path, lock_path):
        if not path.is_file():
            raise RuntimeError(f"missing archived continuation evidence: {path}")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    root_inspection_ledger = ROOT_INSPECTION_ATTEMPT / "execution-ledger.json"
    if not root_inspection_ledger.is_file():
        raise RuntimeError("missing archived root-inspection failure evidence")
    root_inspection = json.loads(root_inspection_ledger.read_text(encoding="utf-8"))
    if (
        root_inspection.get("status") != "BLOCKED"
        or "/etc/.pwd.lock" not in str(root_inspection.get("error"))
    ):
        raise RuntimeError("archived root-inspection failure identity mismatch")
    retries_ledger = RETRIES_ATTEMPT / "execution-ledger.json"
    if not retries_ledger.is_file():
        raise RuntimeError("missing archived retries-contract failure evidence")
    retries_failure = json.loads(retries_ledger.read_text(encoding="utf-8"))
    if (
        retries_failure.get("status") != "BLOCKED"
        or "Expected `int` >= 1 - at `$.retries`"
        not in str(retries_failure.get("error"))
    ):
        raise RuntimeError("archived retries-contract failure identity mismatch")
    crashpad_ledger = CRASHPAD_ATTEMPT / "execution-ledger.json"
    if not crashpad_ledger.is_file():
        raise RuntimeError("missing archived Crashpad database failure evidence")
    crashpad_failure = json.loads(crashpad_ledger.read_text(encoding="utf-8"))
    if (
        crashpad_failure.get("status") != "BLOCKED"
        or "chrome_crashpad_handler: --database is required"
        not in str(crashpad_failure.get("error"))
    ):
        raise RuntimeError("archived Crashpad database failure identity mismatch")
    commands = ledger.get("commands", [])
    bootstrap = [
        item
        for item in commands
        if item.get("argv", [None])[:3] == ["docker", "buildx", "build"]
        and "lock-export" in item.get("argv", [])
    ]
    if len(bootstrap) != 1 or bootstrap[0].get("exit_code") != 0:
        raise RuntimeError("archived bootstrap build is not a single successful command")
    manifest = ROOT / "browser-tree.manifest.json"
    lock = ROOT / "debian-packages.lock"
    if sha256_file(manifest) != sha256_file(manifest_path):
        raise RuntimeError("continuation browser manifest differs from archived bootstrap output")
    lock_bytes = lock.read_bytes()
    if b"\r" in lock_bytes or not lock_bytes.endswith(b"\n"):
        raise RuntimeError("continuation Debian lock is not normalized LF text")
    return {
        "archived_attempt": PREVIOUS_ATTEMPT.relative_to(ROOT).as_posix(),
        "archived_execution_ledger_sha256": sha256_file(ledger_path),
        "archived_lock_crlf_sha256": sha256_file(lock_path),
        "bootstrap_build": bootstrap[0],
        "browser_manifest_sha256": sha256_file(manifest),
        "debian_lock_lf_sha256": sha256_file(lock),
        "reason": "resume after host CRLF versus container LF lock comparison failure",
        "root_inspection_failure": {
            "archived_attempt": ROOT_INSPECTION_ATTEMPT.relative_to(ROOT).as_posix(),
            "execution_ledger_sha256": sha256_file(root_inspection_ledger),
            "remediation": "identity inspection only uses explicit docker --user 0",
        },
        "retries_contract_failure": {
            "archived_attempt": RETRIES_ATTEMPT.relative_to(ROOT).as_posix(),
            "execution_ledger_sha256": sha256_file(retries_ledger),
            "remediation": "both DynamicFetcher calls use retries=1",
        },
        "crashpad_database_failure": {
            "archived_attempt": CRASHPAD_ATTEMPT.relative_to(ROOT).as_posix(),
            "execution_ledger_sha256": sha256_file(crashpad_ledger),
            "remediation": "runtime-only HOME and XDG directories use controlled /tmp tmpfs paths",
        },
    }


def extract_notices(archive_bytes: bytes) -> None:
    with tarfile.open(fileobj=BytesIO(archive_bytes), mode="r:") as archive:
        for member in archive.getmembers():
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts or not member.isfile():
                raise RuntimeError(f"unsafe notice archive member: {member.name}")
        archive.extractall(EVIDENCE, filter="data")


def collect_supply_chain(image: str, suffix: str) -> dict[str, object]:
    sbom = docker_python(image, "generate_sbom.py")
    inventory = docker_python(image, "generate_sbom.py", "--debian-license-inventory")
    json.loads(sbom)
    json.loads(inventory)
    if suffix == "build1":
        (EVIDENCE / "sbom.cdx.json").write_bytes(sbom)
        (EVIDENCE / "debian-license-inventory.json").write_bytes(inventory)
        notices = docker_python(image, "export_notices.py")
        extract_notices(notices)
    return {
        "debian_inventory_sha256": sha256_bytes(inventory),
        "sbom_sha256": sha256_bytes(sbom),
    }


def runtime_check(image: str, container: str) -> dict[str, object]:
    outer_deadline_seconds = 120
    run(
        "docker",
        "create",
        "--name",
        container,
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        "/tmp:rw,nosuid,noexec,size=256m",  # noqa: S108 - container tmpfs mount
        "--env",
        f"HOME={RUNTIME_ENV['HOME']}",
        "--env",
        f"XDG_CONFIG_HOME={RUNTIME_ENV['XDG_CONFIG_HOME']}",
        "--env",
        f"XDG_CACHE_HOME={RUNTIME_ENV['XDG_CACHE_HOME']}",
        "--pids-limit",
        "128",
        "--memory",
        "768m",
        "--cpus",
        "1",
        image,
    )
    inspect = json_output("docker", "container", "inspect", container)[0]
    host = inspect["HostConfig"]
    security = {
        "cap_drop": sorted(host.get("CapDrop") or []),
        "network_mode": host["NetworkMode"],
        "no_new_privileges": "no-new-privileges" in (host.get("SecurityOpt") or []),
        "pids_limit": host["PidsLimit"],
        "privileged": host["Privileged"],
        "read_only_rootfs": host["ReadonlyRootfs"],
        "user": inspect["Config"]["User"],
        "tmpfs": host.get("Tmpfs") or {},
        "runtime_environment": {
            key: next(
                value.split("=", 1)[1]
                for value in inspect["Config"].get("Env", [])
                if value.startswith(f"{key}=")
            )
            for key in RUNTIME_ENV
        },
    }
    result = run(
        "docker", "start", "-a", container, check=False, timeout=outer_deadline_seconds
    )
    if result.returncode:
        raise RuntimeError(
            f"runtime probe failed for {image}: "
            f"{result.stderr.decode('utf-8', errors='replace')[-4000:]}"
        )
    payload = json.loads(result.stdout.decode("utf-8").splitlines()[-1])
    run("docker", "container", "rm", container)
    return {
        "outer_deadline_seconds": outer_deadline_seconds,
        "probe": payload,
        "security": security,
    }


def normalized_identity(image: str) -> dict[str, object]:
    value = run(
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--user",
        "0",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--entrypoint",
        "python",
        image,
        "/opt/flowtracer-r1c/scripts/image_identity.py",
        timeout=180,
    ).stdout.decode("ascii").strip()
    return {
        "cap_drop": ["ALL"],
        "network_mode": "none",
        "no_new_privileges": True,
        "purpose": "root-only normalized filesystem inspection",
        "read_only_rootfs": True,
        "sha256": value,
        "user": "0",
    }


def cleanup() -> dict[str, object]:
    for container in RUNTIME_CONTAINERS:
        run("docker", "container", "rm", "-f", container, check=False)
    run("docker", "image", "rm", BOOTSTRAP_IMAGE, BUILD1_IMAGE, BUILD2_IMAGE, check=False)
    run("docker", "buildx", "rm", BUILDER, check=False, timeout=120)
    return exact_objects()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume-from-archived-locks", action="store_true")
    arguments = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for path in EVIDENCE.rglob("*"):
        if path.is_file():
            path.unlink()
    protected_before = r3_hashes()
    write_json("protected-r3-sha256.json", protected_before)
    started = datetime.now(UTC)
    status = "BLOCKED"
    error_text: str | None = None
    comparison: dict[str, object] = {}
    cleanup_result: dict[str, object] | None = None
    protected_docker_before: dict[str, object] | None = None
    namespace_claimed = False
    try:
        ensure_clean_start()
        namespace_claimed = True
        protected_docker_before = protected_docker_objects()
        write_json("protected-docker-before.json", protected_docker_before)
        versions = {
            "branch": output("git", "branch", "--show-current").strip(),
            "buildx": output("docker", "buildx", "version").strip(),
            "docker": output("docker", "version", "--format", "{{json .}}").strip(),
            "head": output("git", "rev-parse", "HEAD").strip(),
            "host_architecture": os.environ.get("PROCESSOR_ARCHITECTURE"),
            "host_os": os.name,
            "origin_main": output("git", "rev-parse", "origin/main").strip(),
            "python_runner": sys.version,
        }
        write_json("versions.json", versions)
        if arguments.resume_from_archived_locks:
            write_json("continuation.json", resume_provenance())
        run(
            "docker",
            "buildx",
            "create",
            "--name",
            BUILDER,
            "--driver",
            "docker-container",
            "--driver-opt",
            f"network=bridge,image={BUILDKIT_IMAGE}",
        )
        run("docker", "buildx", "inspect", BUILDER, "--bootstrap", timeout=180)
        if not arguments.resume_from_archived_locks:
            build(BOOTSTRAP_IMAGE, "lock-export", "bootstrap-build.txt")
            capture_locks()
        build(BUILD1_IMAGE, "final", "build1.txt")
        build(BUILD2_IMAGE, "final", "build2.txt")
        identities = {
            "build1": normalized_identity(BUILD1_IMAGE),
            "build2": normalized_identity(BUILD2_IMAGE),
        }
        supply_chain = {
            "build1": collect_supply_chain(BUILD1_IMAGE, "build1"),
            "build2": collect_supply_chain(BUILD2_IMAGE, "build2"),
        }
        runtimes = {
            "build1": runtime_check(BUILD1_IMAGE, RUNTIME_CONTAINERS[0]),
            "build2": runtime_check(BUILD2_IMAGE, RUNTIME_CONTAINERS[1]),
        }
        if identities["build1"]["sha256"] != identities["build2"]["sha256"]:
            raise RuntimeError("normalized filesystem identities differ")
        if supply_chain["build1"] != supply_chain["build2"]:
            raise RuntimeError("SBOM or Debian inventory streams differ")
        if any(runtime["probe"]["network"] != "none" for runtime in runtimes.values()):
            raise RuntimeError("runtime probe did not prove network none")
        comparison = {
            "browser_manifest_entries": len(
                json.loads((ROOT / "browser-tree.manifest.json").read_text())["entries"]
            ),
            "debian_packages": len((ROOT / "debian-packages.lock").read_text().splitlines()),
            "image_ids": {
                "build1": json_output("docker", "image", "inspect", BUILD1_IMAGE)[0]["Id"],
                "build2": json_output("docker", "image", "inspect", BUILD2_IMAGE)[0]["Id"],
            },
            "identity_inspections": identities,
            "normalized_identity": identities["build1"]["sha256"],
            "runtimes": runtimes,
            "supply_chain": supply_chain,
        }
        write_json("build-comparison.json", comparison)
        validation = (
            run(
                sys.executable,
                str(ROOT / "scripts" / "validate_sbom.py"),
                str(EVIDENCE),
                timeout=60,
            )
            .stdout.decode("utf-8")
            .strip()
        )
        comparison["validation"] = validation
        status = "PASS"
    except Exception as error:
        error_text = f"{type(error).__name__}: {error}"
    finally:
        cleanup_result = cleanup() if namespace_claimed else exact_objects()
        protected_docker_after = protected_docker_objects()
        write_json(
            "protected-docker-objects.json",
            {"after": protected_docker_after, "before": protected_docker_before},
        )
        expected_cleanup = {
            "builder_exists": False,
            "containers": {name: False for name in RUNTIME_CONTAINERS},
            "images": {
                BOOTSTRAP_IMAGE: False,
                BUILD1_IMAGE: False,
                BUILD2_IMAGE: False,
            },
            "volumes": [],
        }
        if cleanup_result != expected_cleanup:
            status = "BLOCKED"
            error_text = error_text or "RuntimeError: R1C cleanup is incomplete"
        if protected_docker_after != protected_docker_before:
            status = "BLOCKED"
            error_text = error_text or "RuntimeError: protected Docker objects changed"
        ended = datetime.now(UTC)
        write_json("build-comparison.json", comparison)
        write_json(
            "execution-ledger.json",
            {
                "commands": COMMANDS,
                "duration_seconds": round((ended - started).total_seconds(), 3),
                "ended_at": ended.isoformat(),
                "error": error_text,
                "object_namespace": f"{RUN_ID}-*",
                "public_runtime_access": False,
                "started_at": started.isoformat(),
                "status": status,
            },
        )
        write_json("cleanup.json", cleanup_result)
        protected_after = r3_hashes()
        if protected_after != protected_before:
            raise RuntimeError("protected browser-r3 hashes changed during R1C")
    if status != "PASS":
        raise RuntimeError(error_text or "R1C did not pass")
    print(json.dumps({"result": "R1C_PASS", **comparison}, sort_keys=True))


if __name__ == "__main__":
    main()
