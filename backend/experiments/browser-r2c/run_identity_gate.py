from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
EVIDENCE = ROOT / "evidence"
RUN_ID = "flowtracer-r2c-20260913-identity-a"
BUILDER = f"{RUN_ID}-builder"
IMAGE = f"flowtracer-browser-r2c:{RUN_ID}"
BUILDKIT_IMAGE = (
    "moby/buildkit@sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8"
)
EXPECTED_IDENTITY = "6ef0e9ecb34d0a72c2135282b06548f7bdac92be27f8df2444188216013bddea"
EXPECTED_BROWSER_SHA = "0b20b130e7edd9dd51873be867761295fe0cfad490c2b9a64f95bd3cfc08fa71"
EXPECTED_SBOM_SHA = "a8d6ae5e450b10bd40d90f6d56a0e69742479cfaff79398c0d2fb0696cfcf774"
EXPECTED_INVENTORY_SHA = "bee9c30ae016be592521c383b9bb0be74f39892415ed28f9122d5b7ccced81da"
PROTECTED = ("browser-r1", "browser-r2", "browser-r1c", "browser-r3")
ledger: list[dict[str, object]] = []


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hashes(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): sha256(path)
        for path in sorted(directory.rglob("*"), key=lambda value: value.as_posix())
        if path.is_file()
    }


def run(
    argv: list[str], *, timeout: int = 120, check: bool = True
) -> subprocess.CompletedProcess[str]:
    started = now()
    result = subprocess.run(  # noqa: S603 - fixed local Docker argv only
        argv, cwd=REPO, capture_output=True, text=True, timeout=timeout
    )
    ledger.append(
        {
            "argv": argv,
            "started_at": started,
            "ended_at": now(),
            "exit_code": result.returncode,
        }
    )
    if check and result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {argv!r}\n{result.stderr[-2000:]}"
        )
    return result


def hardened_python(
    arguments: list[str], *, user: str = "0:0", timeout: int = 300
) -> subprocess.CompletedProcess[str]:
    return run(
        [
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
            "/tmp:rw,nosuid,nodev,noexec,size=256m,mode=1777",  # noqa: S108 - hardened container tmpfs
            "--entrypoint",
            "python",
            IMAGE,
            *arguments,
        ],
        timeout=timeout,
    )


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )


def absent_before() -> None:
    if run(["docker", "buildx", "inspect", BUILDER], check=False).returncode == 0:
        raise RuntimeError(f"builder already exists: {BUILDER}")
    if run(["docker", "image", "inspect", IMAGE], check=False).returncode == 0:
        raise RuntimeError(f"image already exists: {IMAGE}")


def verify_copied_inputs() -> None:
    source = ROOT.parent / "browser-r1c"
    paths = [
        Path("Dockerfile"),
        Path("browser-tree.manifest.json"),
        Path("debian-packages.lock"),
        Path("requirements.lock"),
    ]
    paths.extend(path.relative_to(source) for path in (source / "scripts").glob("*.py"))
    mismatches = [path.as_posix() for path in paths if sha256(ROOT / path) != sha256(source / path)]
    if mismatches:
        raise RuntimeError(f"copied R1C input mismatch: {mismatches}")


def cleanup() -> dict[str, object]:
    actions = []
    for argv in (["docker", "image", "rm", "-f", IMAGE], ["docker", "buildx", "rm", "-f", BUILDER]):
        result = run(argv, timeout=300, check=False)
        actions.append(
            {"argv": argv, "exit_code": result.returncode, "stderr": result.stderr[-1000:]}
        )
    return {
        "actions": actions,
        "builder_absent": run(["docker", "buildx", "inspect", BUILDER], check=False).returncode
        != 0,
        "image_absent": run(["docker", "image", "inspect", IMAGE], check=False).returncode != 0,
    }


def main() -> int:
    EVIDENCE.mkdir(exist_ok=True)
    protected_before = {name: hashes(ROOT.parent / name) for name in PROTECTED}
    write_json(EVIDENCE / "protected-files-before.json", protected_before)
    result: dict[str, object] = {"run_id": RUN_ID, "status": "RUNNING", "started_at": now()}
    exit_code = 1
    try:
        verify_copied_inputs()
        absent_before()
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
                str(ROOT / "Dockerfile"),
                "-t",
                IMAGE,
                str(ROOT),
            ],
            timeout=1800,
        )
        (EVIDENCE / "identity-build.txt").write_text(
            build.stdout + build.stderr, encoding="utf-8", newline="\n"
        )

        identity = hardened_python(["/opt/flowtracer-r1c/scripts/image_identity.py"]).stdout.strip()
        manifest_raw = hardened_python(
            ["/opt/flowtracer-r1c/scripts/browser_tree_manifest.py"]
        ).stdout
        (EVIDENCE / "browser-tree.actual.json").write_text(
            manifest_raw, encoding="utf-8", newline="\n"
        )
        manifest = json.loads(manifest_raw)

        facts_program = (
            "import hashlib,json,pathlib,subprocess; "
            "p=pathlib.Path('/opt/browser-r1c/chromium-1234/chrome-linux64/chrome'); "
            "print(json.dumps({'path':str(p),'sha256':"
            "hashlib.sha256(p.read_bytes()).hexdigest(),'version':"
            "subprocess.check_output([str(p),'--version'],text=True).strip()}))"
        )
        facts_raw = hardened_python(
            [
                "-c",
                facts_program,
            ]
        ).stdout
        facts = json.loads(facts_raw)

        sbom_raw = hardened_python(
            ["/opt/flowtracer-r1c/scripts/generate_sbom.py"], timeout=600
        ).stdout
        inventory_raw = hardened_python(
            ["/opt/flowtracer-r1c/scripts/generate_sbom.py", "--debian-license-inventory"],
            timeout=600,
        ).stdout
        sbom_path = EVIDENCE / "sbom.cdx.json"
        inventory_path = EVIDENCE / "debian-license-inventory.json"
        sbom_path.write_text(sbom_raw, encoding="utf-8", newline="\n")
        inventory_path.write_text(inventory_raw, encoding="utf-8", newline="\n")
        sbom = json.loads(sbom_raw)
        inventory = json.loads(inventory_raw)

        image_id = run(["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE]).stdout.strip()
        checks = {
            "normalized_identity": {
                "expected": EXPECTED_IDENTITY,
                "actual": identity,
                "match": identity == EXPECTED_IDENTITY,
            },
            "browser_path": {
                "expected": "/opt/browser-r1c/chromium-1234/chrome-linux64/chrome",
                "actual": facts["path"],
                "match": facts["path"] == "/opt/browser-r1c/chromium-1234/chrome-linux64/chrome",
            },
            "browser_sha256": {
                "expected": EXPECTED_BROWSER_SHA,
                "actual": facts["sha256"],
                "match": facts["sha256"] == EXPECTED_BROWSER_SHA,
            },
            "browser_version": {
                "expected": "Google Chrome for Testing 151.0.7922.34",
                "actual": facts["version"],
                "match": facts["version"] == "Google Chrome for Testing 151.0.7922.34",
            },
            "browser_tree_entries": {
                "expected": 619,
                "actual": len(manifest["entries"]),
                "match": len(manifest["entries"]) == 619,
            },
            "sbom_components": {
                "expected": 231,
                "actual": len(sbom["components"]),
                "match": len(sbom["components"]) == 231,
            },
            "sbom_sha256": {
                "expected": EXPECTED_SBOM_SHA,
                "actual": sha256(sbom_path),
                "match": sha256(sbom_path) == EXPECTED_SBOM_SHA,
            },
            "debian_inventory_components": {
                "expected": 206,
                "actual": len(inventory["components"]),
                "match": len(inventory["components"]) == 206,
            },
            "debian_inventory_sha256": {
                "expected": EXPECTED_INVENTORY_SHA,
                "actual": sha256(inventory_path),
                "match": sha256(inventory_path) == EXPECTED_INVENTORY_SHA,
            },
        }
        result.update({"image": IMAGE, "image_id": image_id, "checks": checks})
        failures = [name for name, value in checks.items() if not value["match"]]
        if failures:
            result.update({"status": "BLOCKED", "blocking_checks": failures})
            exit_code = 78
        else:
            result["status"] = "IDENTITY_PASS"
            exit_code = 0
    except Exception as exc:
        result.update({"status": "BLOCKED", "error": str(exc)})
        exit_code = 78
    finally:
        result["cleanup"] = cleanup()
        protected_after = {name: hashes(ROOT.parent / name) for name in PROTECTED}
        write_json(EVIDENCE / "protected-files-after.json", protected_after)
        result["protected_files_unchanged"] = protected_before == protected_after
        result["ended_at"] = now()
        write_json(EVIDENCE / "identity-gate.json", result)
        write_json(EVIDENCE / "execution-ledger.json", ledger)
    print(json.dumps(result, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
