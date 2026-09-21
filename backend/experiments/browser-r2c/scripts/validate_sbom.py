from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from license_policy import expression_for_debian_headers

SHA256 = re.compile(r"^[0-9a-f]{64}$")
PACKAGE_TREE_DECLARATION = re.compile(
    r"R1C_PACKAGE_TREE_V1 files=(\d+) payload_bytes=(\d+) sha256=([0-9a-f]{64})"
)
TMP_ROOT = "/tmp"  # noqa: S108 - dedicated container tmpfs required by R1C
RENDER_PROFILE = f"{TMP_ROOT}/flowtracer-r1c-render-profile"
FAILURE_PROFILE = f"{TMP_ROOT}/flowtracer-r1c-failure-profile"
HOME_DIR = f"{TMP_ROOT}/flowtracer-r1c-home"
CONFIG_DIR = f"{TMP_ROOT}/flowtracer-r1c-config"
CACHE_DIR = f"{TMP_ROOT}/flowtracer-r1c-cache"
RUNTIME_ENV = {
    "HOME": HOME_DIR,
    "XDG_CONFIG_HOME": CONFIG_DIR,
    "XDG_CACHE_HOME": CACHE_DIR,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def properties(component: dict[str, Any]) -> dict[str, str]:
    return {item["name"]: item["value"] for item in component.get("properties", [])}


def package_tree_identity(package_root: Path) -> dict[str, int | str]:
    entries: list[tuple[str, Path]] = []
    for path in package_root.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"package tree contains a symlink: {path}")
        if path.is_file():
            entries.append((path.relative_to(package_root).as_posix(), path))
        elif not path.is_dir():
            raise RuntimeError(f"package tree contains an unsupported entry: {path}")

    # Python string ordering is locale-independent Unicode code-point order.
    # Each relative path is encoded as UTF-8 only after sorting; hashes cover
    # the exact file bytes. The final record also carries LF, so the payload
    # always has a trailing LF and Encoding never emits a BOM.
    entries.sort(key=lambda item: item[0])
    payload = b"".join(
        relative.encode("utf-8") + b" " + sha256(path).encode("ascii") + b"\n"
        for relative, path in entries
    )
    return {
        "files": len(entries),
        "payload_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def validate_package_tree(evidence_root: Path, declaration_path: Path) -> dict[str, int | str]:
    declarations = PACKAGE_TREE_DECLARATION.findall(declaration_path.read_text(encoding="utf-8"))
    if len(declarations) != 1:
        raise RuntimeError("expected exactly one R1C package tree declaration")
    files, payload_bytes, expected_sha256 = declarations[0]
    expected: dict[str, int | str] = {
        "files": int(files),
        "payload_bytes": int(payload_bytes),
        "sha256": expected_sha256,
    }
    actual = package_tree_identity(evidence_root.parent)
    if actual != expected:
        raise RuntimeError(f"R1C package tree identity mismatch: {actual} != {expected}")
    return actual


def validate_log_rename_proof(evidence_root: Path) -> None:
    proof_path = evidence_root.parent / "log-rename-sha256.json"
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    records = proof.get("files")
    if not isinstance(records, list) or len(records) != 10:
        raise RuntimeError("incomplete log rename proof")
    expected_new_paths = {
        "attempts/attempt-1-blocked-20260912T114447Z/bootstrap-build.txt",
        "attempts/attempt-1-blocked-20260912T114447Z/build1.txt",
        "attempts/attempt-2-blocked-root-inspection/build1.txt",
        "attempts/attempt-2-blocked-root-inspection/build2.txt",
        "attempts/attempt-3-blocked-retries-contract/build1.txt",
        "attempts/attempt-3-blocked-retries-contract/build2.txt",
        "attempts/attempt-4-blocked-crashpad-database/build1.txt",
        "attempts/attempt-4-blocked-crashpad-database/build2.txt",
        "evidence/build1.txt",
        "evidence/build2.txt",
    }
    actual_new_paths = {record.get("new_path") for record in records}
    if actual_new_paths != expected_new_paths:
        raise RuntimeError("unexpected renamed log path set")
    root = evidence_root.parent
    for record in records:
        old_path = root / record["old_path"]
        new_path = root / record["new_path"]
        old_sha = record.get("old_sha256", "")
        new_sha = record.get("new_sha256", "")
        if (
            old_path.exists()
            or not new_path.is_file()
            or not SHA256.fullmatch(old_sha)
            or old_sha != new_sha
            or sha256(new_path) != new_sha
            or new_path.stat().st_size != record.get("bytes")
        ):
            raise RuntimeError(f"log rename content mismatch: {new_path}")


def validate_runtime_boundaries(evidence_root: Path) -> None:
    comparison = json.loads((evidence_root / "build-comparison.json").read_text(encoding="utf-8"))
    identities = comparison.get("identity_inspections")
    if not isinstance(identities, dict) or set(identities) != {"build1", "build2"}:
        raise RuntimeError("missing root-only identity inspections")
    identity_hashes = set()
    for name, inspection in identities.items():
        expected = {
            "cap_drop": ["ALL"],
            "network_mode": "none",
            "no_new_privileges": True,
            "purpose": "root-only normalized filesystem inspection",
            "read_only_rootfs": True,
            "user": "0",
        }
        for key, value in expected.items():
            if inspection.get(key) != value:
                raise RuntimeError(f"unsafe identity inspection boundary: {name}:{key}")
        value = inspection.get("sha256", "")
        if not SHA256.fullmatch(value):
            raise RuntimeError(f"invalid identity hash: {name}")
        identity_hashes.add(value)
    if len(identity_hashes) != 1 or comparison.get("normalized_identity") not in identity_hashes:
        raise RuntimeError("normalized filesystem identity mismatch")

    runtimes = comparison.get("runtimes")
    if not isinstance(runtimes, dict) or set(runtimes) != {"build1", "build2"}:
        raise RuntimeError("missing UID 10001 runtime probes")
    for name, runtime in runtimes.items():
        security = runtime.get("security", {})
        expected_security = {
            "cap_drop": ["ALL"],
            "network_mode": "none",
            "no_new_privileges": True,
            "privileged": False,
            "read_only_rootfs": True,
            "user": "10001:10001",
            "tmpfs": {TMP_ROOT: "rw,nosuid,noexec,size=256m"},
            "runtime_environment": RUNTIME_ENV,
        }
        for key, value in expected_security.items():
            if security.get(key) != value:
                raise RuntimeError(f"unsafe UID 10001 runtime boundary: {name}:{key}")
        probe = runtime.get("probe", {})
        dynamic = probe.get("dynamic_fetcher", {})
        call_contract = dynamic.get("call_contract", {})
        executable = "/opt/browser-r1c/chromium-1234/chrome-linux64/chrome"
        expected_render = {
            "disable_resources": False,
            "headless": True,
            "network_idle": True,
            "retries": 1,
            "timeout": 8000,
            "user_data_dir": RENDER_PROFILE,
        }
        expected_failure = {
            "headless": True,
            "retries": 1,
            "timeout": 2500,
            "user_data_dir": FAILURE_PROFILE,
        }
        expected_render_dirs = {
            HOME_DIR: True,
            CONFIG_DIR: True,
            CACHE_DIR: True,
            RENDER_PROFILE: True,
        }
        expected_failure_dirs = {
            HOME_DIR: True,
            CONFIG_DIR: True,
            CACHE_DIR: True,
            FAILURE_PROFILE: True,
        }
        expected_directories = {
            "failure": expected_failure_dirs,
            "render": expected_render_dirs,
        }
        crashpad = dynamic.get("crashpad_databases", {})
        crashpad_valid = True
        for phase in ("failure", "render"):
            database = crashpad.get(phase, {})
            path = database.get("path", "")
            crashpad_valid = crashpad_valid and (
                database.get("uid") == 10001
                and database.get("gid") == 10001
                and database.get("mode") == "0700"
                and any(path.startswith(f"{root}/") for root in RUNTIME_ENV.values())
                and path.endswith("/Crash Reports")
            )
        if (
            runtime.get("outer_deadline_seconds") != 120
            or probe.get("uid") != 10001
            or probe.get("network") != "none"
            or probe.get("read_only_rootfs") is not True
            or dynamic.get("rendered") != "dynamic-rendered"
            or dynamic.get("terminal_browser_processes") != []
            or dynamic.get("terminal_fixture_thread") != "stopped"
            or not dynamic.get("failure_type")
            or call_contract.get("executable_path") != executable
            or call_contract.get("render") != expected_render
            or call_contract.get("failure") != expected_failure
            or dynamic.get("runtime_environment") != RUNTIME_ENV
            or dynamic.get("runtime_directories_absent_after") != expected_directories
            or dynamic.get("runtime_directories_absent_before") != expected_directories
            or not crashpad_valid
        ):
            raise RuntimeError(f"incomplete DynamicFetcher runtime evidence: {name}")


def validate(evidence_root: Path) -> dict[str, int]:
    validate_log_rename_proof(evidence_root)
    bom = json.loads((evidence_root / "sbom.cdx.json").read_text(encoding="utf-8"))
    inventory = json.loads(
        (evidence_root / "debian-license-inventory.json").read_text(encoding="utf-8")
    )
    if bom.get("bomFormat") != "CycloneDX" or bom.get("specVersion") != "1.6":
        raise RuntimeError("invalid CycloneDX identity")
    components = bom.get("components")
    if not isinstance(components, list):
        raise RuntimeError("missing SBOM components")
    debian = [item for item in components if item["bom-ref"].startswith("pkg:deb/")]
    records = inventory.get("components")
    if not isinstance(records, list) or len(records) != len(debian):
        raise RuntimeError("Debian inventory/SBOM count mismatch")
    record_by_name = {item["name"]: item for item in records}
    for component in debian:
        values = properties(component)
        notice = evidence_root / values["flowtracer:persistent-license-notice"]
        notice_hash = values["flowtracer:license-notice-sha256"]
        if not notice.is_file() or sha256(notice) != notice_hash:
            raise RuntimeError(f"Debian notice mismatch: {component['name']}")
        raw_headers = json.loads(values["flowtracer:license-raw-headers"])
        expression = component["licenses"][0]["expression"]
        if expression != expression_for_debian_headers(raw_headers, notice_hash):
            raise RuntimeError(f"Debian license mapping mismatch: {component['name']}")
        record = record_by_name.get(component["name"])
        if record is None or record["license_notice_sha256"] != notice_hash:
            raise RuntimeError(f"Debian inventory identity mismatch: {component['name']}")
    expected = {
        "browser:chromium-full@151.0.7922.34-r1234": (
            "notices/chromium-ABOUT",
            "/opt/browser-r1c/chromium-1234/chrome-linux64/chrome",
        ),
        "binary:ffmpeg@playwright-r1011": ("notices/ffmpeg-COPYING.LGPLv2.1", None),
    }
    for reference, (notice_name, executable) in expected.items():
        component = next(item for item in components if item["bom-ref"] == reference)
        values = properties(component)
        binary_hash = component["hashes"][0]["content"]
        notice_hash = values["flowtracer:notice-sha256"]
        notice = evidence_root / notice_name
        if not SHA256.fullmatch(binary_hash) or not SHA256.fullmatch(notice_hash):
            raise RuntimeError(f"invalid binary/notice hash: {reference}")
        if not notice.is_file() or sha256(notice) != notice_hash or binary_hash == notice_hash:
            raise RuntimeError(f"notice evidence mismatch: {reference}")
        if executable is not None and values.get("flowtracer:executable-path") != executable:
            raise RuntimeError("full Chromium executable path mismatch")
    validate_runtime_boundaries(evidence_root)
    return {"components": len(components), "debian": len(debian)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--package-tree-doc", type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.evidence)
    message = (
        "R1C_EVIDENCE_VALIDATION=PASS "
        f"components={result['components']} debian={result['debian']} "
        "identity_user=0 runtime_uid=10001"
    )
    if arguments.package_tree_doc is not None:
        package = validate_package_tree(arguments.evidence, arguments.package_tree_doc)
        message += (
            f" package_files={package['files']}"
            f" package_payload_bytes={package['payload_bytes']}"
            f" package_tree_sha256={package['sha256']}"
        )
    print(message)


if __name__ == "__main__":
    main()
