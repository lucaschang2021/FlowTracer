"""Exclusive probe supervision/input closure; never launched by offline tests."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock, Thread, Timer
from types import MappingProxyType

from collector import Unknown

REAL_SESSION_AUTHORIZED = False

HOST_CONTROLLER = Path("D:/FlowTracer/.r3-control/source_preflight_controller.py")
HOST_RECORD = Path("D:/FlowTracer/.r3-control/source_preflight_approval.json")
R1E_MANIFEST = "f8d8bd0b64dfac53e244b00f29fbc9f18ed44b94491323b3f49ba2af191912e8"
R1E_PAYLOAD = "5f4cf5acdf06a86f9b8907375f6f8f239ecf18152762b889f1e254b01e447e3b"
DOCKER_EXE = "C:/Users/liuj/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe"
GIT_EXE = "C:/Program Files/Git/cmd/git.exe"
SOURCE_SESSIONS = set()
SOURCE_SESSION_LOCK = Lock()
SCRATCH_TARGET = "/tmp"  # noqa: S108 - approved isolated container tmpfs


def strict_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise Unknown("duplicate_json_key")
            value[key] = item
        return value

    def constant(_):
        raise Unknown("nonfinite_json")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


@dataclass(frozen=True)
class HostApproval:
    """Consumption boundary, NOT authentication of an arbitrary Python caller.

    Only the separately reviewed fixed host program may instantiate and launch.
    Its independently frozen source constants are the trust root. No prod CLI,
    environment, reflection loader, test-double switch or self approval exists.
    """

    record_path: Path
    record_raw_sha256: str
    control_commit: str
    record_data: dict

    def __post_init__(self):
        value = dict(self.record_data)
        if isinstance(value.get("phases"), list):
            value["phases"] = tuple(value["phases"])
        object.__setattr__(self, "record_data", MappingProxyType(value))

    def read_approved_record(self, session, phase):
        try:
            if (
                self.record_path != HOST_RECORD
                or not re.fullmatch(r"[0-9a-f]{64}", self.record_raw_sha256)
                or not re.fullmatch(r"[0-9a-f]{40}", self.control_commit)
            ):
                raise Unknown("host_binding_invalid")
            # Record/host are not Backend inputs and are never created here.
            checked_repo_file(HOST_RECORD.parent, HOST_CONTROLLER)
            checked_repo_file(HOST_RECORD.parent, HOST_RECORD)
            with HOST_RECORD.open("rb") as stream:
                raw = stream.read(65537)
            if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != self.record_raw_sha256:
                raise Unknown("host_record_digest_invalid")
            value = strict_json(raw)
            keys = {
                "schema_version",
                "mode",
                "candidate_commit",
                "manifest_raw_sha256",
                "plan_raw_sha256",
                "image_id",
                "r1e_manifest_sha256",
                "r1e_payload_sha256",
                "control_commit",
                "session",
                "phases",
                "launches_per_phase",
                "target_permission",
            }
            if (
                type(value) is not dict
                or set(value) != keys
                or any(type(value[k]) is not str for k in keys - {"phases", "launches_per_phase"})
            ):
                raise Unknown("host_record_schema_invalid")
            if (
                value["schema_version"] != "r3-source-preflight-approval-v1"
                or value["mode"] != "source-preflight"
                or value["target_permission"] != "DENIED"
                or value["phases"] != ["baseline", "enabled"]
                or type(value["launches_per_phase"]) is not int
                or value["launches_per_phase"] != 1
            ):
                raise Unknown("host_record_contract_invalid")
            if (
                value["control_commit"] != self.control_commit
                or value["session"] != session
                or not re.fullmatch(r"flowtracer-r3-dnr-[a-z0-9-]{1,64}", session)
                or phase not in value["phases"]
            ):
                raise Unknown("host_record_session_invalid")
            for key, pattern in (
                ("candidate_commit", r"[0-9a-f]{40}"),
                ("manifest_raw_sha256", r"[0-9a-f]{64}"),
                ("plan_raw_sha256", r"[0-9a-f]{64}"),
                ("image_id", r"sha256:[0-9a-f]{64}"),
            ):
                if not re.fullmatch(pattern, value[key]):
                    raise Unknown("host_record_value_invalid")
            if (
                value["r1e_manifest_sha256"] != R1E_MANIFEST
                or value["r1e_payload_sha256"] != R1E_PAYLOAD
            ):
                raise Unknown("host_record_image_authority_invalid")
            approved = dict(self.record_data)
            if type(approved.get("phases")) is tuple:
                approved["phases"] = list(approved["phases"])
            # Exact semantic/type equality too (bool is not integer authority).
            if json.dumps(value, sort_keys=True, allow_nan=False) != json.dumps(
                approved, sort_keys=True, allow_nan=False
            ):
                raise Unknown("host_parsed_record_changed")
            return value
        except Exception:
            raise Unknown("source_approval_unissued_or_invalid") from None


def source_plan(rows):
    """One fixed plan; tokens are only approved ROOT/session/image substitutions."""
    base = "backend/experiments/browser-r3/"
    mounts = []
    for name in ("probe.py", "collector.py", "contract_v2.py", "validator_v2.py", "harness_v2.py"):
        mounts.append((base + "dnr_runtime/" + name, "/opt/flowtracer-r3-runtime/" + name))
    for name in ("contract.py", "harness.py"):
        mounts.append((base + "dnr_offline/" + name, "/opt/flowtracer-r3-runtime/" + name))
    hashes = {row["path"]: row["sha256"] for row in rows}
    phases = []
    from probe import source_fetch_options

    for phase in ("baseline", "enabled"):
        selected = list(mounts)
        if phase == "enabled":
            selected += [
                (base + "dnr_runtime/extension-v2/" + name, "/opt/flowtracer-r3-dnr/" + name)
                for name in ("manifest.json", "rules.json", "observer.js", "audit.html", "audit.js")
            ]
        specs = [
            {
                "source": "$ROOT/" + p,
                "inspect_sources": [
                    "$ROOT/" + p,
                    "/run/desktop/mnt/host/d/FlowTracer-wt/backend/" + p,
                ],
                "target": t,
                "sha256": hashes[p],
                "readonly": True,
            }
            for p, t in selected
        ]
        profile = f"/tmp/r3-source/{phase}/profile"  # noqa: S108 - per-phase isolated tmpfs
        argv = [
            "container",
            "create",
            "--pull=never",
            "--name",
            f"$SESSION-{phase}",
            "--label",
            f"flowtracer.r3.session=$SESSION-{phase}",
            "--label",
            "flowtracer.r3.parent=$SESSION",
            "--user",
            "10001:10001",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--pids-limit",
            "128",
            "--memory",
            "768m",
            "--cpus",
            "1.0",
            "--network",
            "none",
            "--restart",
            "no",
            "--tmpfs",
            "/tmp:rw,nosuid,noexec,size=256m",  # noqa: S108 - approved ephemeral container mount
            "--env",
            "HOME=/tmp/r3-home",
            "--env",
            "XDG_CONFIG_HOME=/tmp/r3-config",
            "--env",
            "XDG_CACHE_HOME=/tmp/r3-cache",
        ]
        for spec in specs:
            argv += [
                "--mount",
                f"type=bind,source={spec['source']},target={spec['target']},readonly",
            ]
        command = [
            "/opt/flowtracer-r3-runtime/probe.py",
            "--source-preflight",
            "--phase",
            phase,
            "--profile",
            profile,
            "--session",
            "$SESSION",
        ]
        argv += ["--entrypoint", "python", "$IMAGE", *command]
        options = source_fetch_options(Path(profile), phase, None)
        options.pop("page_setup")
        phases.append(
            {
                "phase": phase,
                "profile": profile,
                "create_argv": argv,
                "child_command": command,
                "mounts": specs,
                "browser_options": options,
            }
        )
    return {
        "schema_version": "r3-source-preflight-plan-v1",
        "mode": "source-preflight",
        "base_commit": "8f5fcc6d70c152616440eb340c7186bd64b690ba",
        "docker_executable": DOCKER_EXE,
        "git_executable": GIT_EXE,
        "repository_root": "D:/FlowTracer-wt/backend",
        "image_authority": "image_id from independent controller record; no build/pull",
        "r1e_manifest_sha256": R1E_MANIFEST,
        "r1e_payload_sha256": R1E_PAYLOAD,
        "driver": "Scrapling DynamicFetcher 0.4.15 / Playwright 1.62.0 / full CfT 151.0.7922.34",
        "phases": phases,
        "url": "about:blank",
        "completion": "page_setup_closes_then_SourcePreflightCompleted_not_fetch_return",
        "parent_seconds": 120,
        "preflight_seconds": 15,
        "close_seconds": 5,
        "target_permission": "DENIED",
        "dependency_services": [],
        "actual_approval": None,
        "expected_output": {
            "status": "SOURCE_OBSERVED_or_BLOCKED",
            "inventory_complete": False,
            "cross_realm_equivalence": "UNKNOWN",
            "dns_status": "NOT_TESTED_NETWORK_NONE",
            "r3": "BLOCKED",
            "r4_r5": "NOT_ADMITTED",
        },
    }


def source_preflight(approval):
    """Only callable by the separately frozen host program; never CLI enabled."""
    if type(approval) is not HostApproval:
        raise Unknown("source_host_approval_required")
    session = approval.record_data.get("session")
    record = approval.read_approved_record(session, "baseline")
    here = Path(__file__).absolute().parent
    root = here.parents[3]
    raw_files = {}
    for name, key in (
        ("execution-inputs.json", "manifest_raw_sha256"),
        ("execution_plan.json", "plan_raw_sha256"),
    ):
        path = checked_repo_file(root, here / name)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != record[key]:
            raise Unknown("source_control_input_digest_invalid")
        raw_files[name] = raw
    manifest = strict_json(raw_files["execution-inputs.json"])
    plan = strict_json(raw_files["execution_plan.json"])
    rows = manifest["inputs"]
    if plan != source_plan(rows):
        raise Unknown("source_plan_not_fixed")
    if root.as_posix() != plan["repository_root"]:
        raise Unknown("source_repository_root_invalid")
    check_inputs(root, rows)
    # Host checks exact candidate Git objects, not a mutable checkout assertion.
    head = (
        subprocess.run(  # noqa: S603 - fixed local Git executable and read-only arguments
            [GIT_EXE, "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, timeout=5
        )
        .stdout.decode()
        .strip()
    )
    if head != record["candidate_commit"]:
        raise Unknown("source_candidate_mismatch")
    for relative in [row["path"] for row in rows] + [
        "backend/experiments/browser-r3/dnr_runtime/execution-inputs.json"
    ]:
        file = checked_repo_file(root, root / relative)
        blob = subprocess.run(  # noqa: S603 - approved commit/path, fixed Git, no shell/network
            [GIT_EXE, "show", f"{head}:{relative}"],
            cwd=root,
            check=True,
            capture_output=True,
            timeout=5,
        ).stdout
        if blob != file.read_bytes():
            raise Unknown("source_candidate_bytes_changed")
    with SOURCE_SESSION_LOCK:
        if session in SOURCE_SESSIONS:
            raise Unknown("source_session_already_consumed")
        SOURCE_SESSIONS.add(session)
    commands = DockerCommands(DOCKER_EXE)
    outcomes = []
    for item in plan["phases"]:
        approval.read_approved_record(session, item["phase"])

        def render(value):
            return (
                value.replace("$ROOT", root.as_posix())
                .replace("$SESSION", session)
                .replace("$IMAGE", record["image_id"])
            )

        create = [render(v) for v in item["create_argv"]]
        contract = {
            "create": create,
            "image": record["image_id"],
            "command": [render(v) for v in item["child_command"]],
            "mounts": [
                {
                    **s,
                    "source": render(s["source"]),
                    "inspect_sources": [render(v) for v in s["inspect_sources"]],
                }
                for s in item["mounts"]
            ],
            "phase": item["phase"],
            "parent_session": session,
        }
        parent = ParentSupervisor(commands, f"{session}-{item['phase']}")
        outcome = parent.run(create, source_contract=contract)
        outcomes.append(outcome)
        if outcome["status"] != "SOURCE_OBSERVED":
            break
    return {
        "status": "SOURCE_OBSERVED"
        if len(outcomes) == 2 and all(o["status"] == "SOURCE_OBSERVED" for o in outcomes)
        else "BLOCKED",
        "target_permission": "DENIED",
        "phases": outcomes,
        "r3": "BLOCKED",
    }


def read_controller_manifest_digest(session: str) -> str:
    """Unissued external approval boundary; never read env/CLI/fixture/self hash.

    Future independent controlcommit/session-bound record path and bytes authority
    must be separately frozen and mounted read-only. No record is issued now.
    Offline tests replace THIS reader with explicitly SYNTHETIC authority doubles.
    """
    raise Unknown("controller_manifest_authority_not_issued")


def checked_repo_file(root: Path, leaf: Path) -> Path:
    """Reject links/reparse/unknown metadata throughout the lexical approved chain."""
    try:
        if (
            not root.is_absolute()
            or not leaf.is_absolute()
            or ".." in root.parts
            or ".." in leaf.parts
            or not leaf.is_relative_to(root)
        ):
            raise Unknown("path_boundary_unknown")
        nodes = [root]
        for part in leaf.relative_to(root).parts:
            nodes.append(nodes[-1] / part)
        for index, node in enumerate(nodes):
            metadata = node.lstat()
            mode = metadata.st_mode
            attrs = getattr(metadata, "st_file_attributes", None)
            if (
                type(mode) is not int
                or stat.S_ISLNK(mode)
                or (sys.platform == "win32" and type(attrs) is not int)
                or (attrs is not None and (type(attrs) is not int or attrs & 0x400))
                or (index < len(nodes) - 1 and not stat.S_ISDIR(mode))
                or (index == len(nodes) - 1 and not stat.S_ISREG(mode))
            ):
                raise Unknown("path_chain_link_or_unknown")
        resolved_root = root.resolve(strict=True)
        if resolved_root != root or not leaf.resolve(strict=True).is_relative_to(resolved_root):
            raise Unknown("path_boundary_escape")
        return leaf
    except Exception:
        raise Unknown("path_chain_unproven") from None


def phase_commands(image: str, session: str, phase: str, mounts: list[dict]):
    """Exact browser create candidate, never executable without separate admission."""
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image) or phase not in {"baseline", "enabled"}:
        raise Unknown("image_or_phase_unfrozen")
    if not re.fullmatch(r"flowtracer-r3-dnr-[a-z0-9-]{1,64}", session):
        raise Unknown("session_invalid")
    argv = [
        "container",
        "create",
        "--pull=never",
        "--name",
        session,
        "--label",
        f"flowtracer.r3.session={session}",
        "--user",
        "10001:10001",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--pids-limit",
        "128",
        "--memory",
        "768m",
        "--cpus",
        "1.0",
        "--network",
        f"{session}_browser",
        "--ip",
        "198.51.100.10",
        "--dns",
        "198.51.100.40",
        "--tmpfs",
        "/tmp:rw,nosuid,noexec,size=256m",  # noqa: S108 - dedicated container tmpfs
    ]
    try:
        here = Path(__file__).absolute().parent
        root = here.parents[3]
        manifest_path = checked_repo_file(root, here / "execution-inputs.json")
        approved_digest = read_controller_manifest_digest(session)
        if type(approved_digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", approved_digest):
            raise Unknown("controller_digest_invalid")
        manifest_bytes = manifest_path.read_bytes()
        if hashlib.sha256(manifest_bytes).hexdigest() != approved_digest:
            raise Unknown("manifest_not_independently_approved")
        manifest = json.loads(manifest_bytes)
        rows = manifest["inputs"]
        if type(rows) is not list or len({row["path"] for row in rows}) != len(rows):
            raise Unknown("mount_manifest_invalid")
        recorded = {row["path"]: row for row in rows}
        targets = {
            "/opt/flowtracer-r3-runtime/" + name: "backend/experiments/browser-r3/dnr_runtime/"
            + name
            for name in (
                "collector.py",
                "probe.py",
                "contract_v2.py",
                "validator_v2.py",
                "harness_v2.py",
            )
        }
        targets.update(
            {
                "/opt/flowtracer-r3-runtime/" + name: "backend/experiments/browser-r3/dnr_offline/"
                + name
                for name in ("contract.py", "harness.py")
            }
        )
        if phase == "enabled":
            targets.update(
                {
                    "/opt/flowtracer-r3-dnr/"
                    + name: "backend/experiments/browser-r3/dnr_runtime/extension-v2/" + name
                    for name in (
                        "manifest.json",
                        "rules.json",
                        "observer.js",
                        "audit.html",
                        "audit.js",
                    )
                }
            )
        if type(mounts) is not list or len(mounts) != len(targets):
            raise Unknown("mount_closure_missing")
        destinations = set()
        for mount in mounts:
            if (
                type(mount) is not dict
                or set(mount) != {"source", "target", "sha256", "readonly"}
                or any(type(mount[k]) is not str for k in ("source", "target", "sha256"))
                or mount["readonly"] is not True
            ):
                raise Unknown("mount_inputs_unfrozen")
            source, target = mount["source"], mount["target"]
            if (
                target not in targets
                or target in destinations
                or "\\" in target
                or ".." in target.split("/")
                or "//" in target
                or any(ord(c) < 32 or c == "," for c in source + target)
            ):
                raise Unknown("mount_target_invalid")
            relative = targets[target]
            expected = root / relative
            supplied = Path(source)
            checked_repo_file(root, expected)
            checked_repo_file(root, supplied)
            row = recorded.get(relative)
            if (
                not supplied.is_absolute()
                or ".." in supplied.parts
                or supplied != expected
                or type(row) is not dict
                or not re.fullmatch(r"[0-9a-f]{64}", mount["sha256"])
                or mount["sha256"] != row.get("sha256")
                or hashlib.sha256(expected.read_bytes()).hexdigest() != row.get("sha256")
            ):
                raise Unknown("mount_source_or_hash_unbound")
            destinations.add(target)
            argv += ["--mount", f"type=bind,source={source},target={target},readonly"]
        if destinations != set(targets):
            raise Unknown("mount_closure_missing")
        if phase == "enabled":
            from contract_v2 import check_static

            check_static(
                here / "extension-v2",
                {
                    name: recorded[
                        "backend/experiments/browser-r3/dnr_runtime/extension-v2/" + name
                    ]["sha256"]
                    for name in (
                        "manifest.json",
                        "rules.json",
                        "observer.js",
                        "audit.html",
                        "audit.js",
                    )
                },
            )
    except Exception:
        raise Unknown("phase_mount_contract_unknown") from None
    argv += [
        "--entrypoint",
        "python",
        image,
        "/opt/flowtracer-r3-runtime/probe.py",
        "--phase",
        phase,
    ]
    return argv


def actual_session_entry(*_args):
    # Immutable source gate, never enabled by CLI/environment/caller boolean.
    if not REAL_SESSION_AUTHORIZED:
        raise Unknown("real_session_not_authorized")
    raise Unknown("inventory_clock_dns_identity_not_proven")


def dependency_commands(image: str, session: str, phase: str):
    """Exact internal dependency candidate; no create/start calls or pulls here."""
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image) or phase not in {"baseline", "enabled"}:
        raise Unknown("image_or_phase_unfrozen")
    if not re.fullmatch(r"flowtracer-r3-dnr-[a-z0-9-]{1,64}", session):
        raise Unknown("session_invalid")
    roles = {
        "proxy": ("198.51.100.20", "proxy.py"),
        "dns": ("198.51.100.40", "proxy.py"),
        "fixture": ("192.0.2.10", "fixture.py"),
    }
    return {
        role: [
            "container",
            "create",
            "--pull=never",
            "--name",
            f"{session}-{role}",
            "--label",
            f"flowtracer.r3.session={session}",
            "--user",
            "10001:10001",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--pids-limit",
            "64",
            "--memory",
            "256m",
            "--cpus",
            "0.5",
            "--network",
            f"{session}_{'fixture' if role == 'fixture' else 'browser'}",
            "--ip",
            ip,
            "--entrypoint",
            "python",
            image,
            f"/opt/flowtracer-r3-runtime/{script}",
            "--role",
            role,
            "--phase",
            phase,
        ]
        for role, (ip, script) in roles.items()
    }


def check_inputs(root: Path, rows: list[dict]) -> None:
    """Raw-byte, import and mount closure; third party bytes use R1E authority."""
    paths, modules = set(), {}
    for row in rows:
        name = row["path"]
        if name in paths or Path(name).is_absolute() or ".." in Path(name).parts:
            raise Unknown("input_path_invalid")
        paths.add(name)
        file = root / name
        if (
            file.is_symlink()
            or not file.is_file()
            or not file.resolve().is_relative_to(root.resolve())
        ):
            raise Unknown("input_path_invalid")
        if row.get("origin") not in {"new_candidate", "tracked_at_base"}:
            raise Unknown("input_origin_unreviewable")
        if hashlib.sha256(file.read_bytes()).hexdigest() != row["sha256"]:
            raise Unknown("input_hash_changed")
        module = row.get("module")
        if module:
            if module in modules:
                raise Unknown("input_module_collision")
            modules[module] = file
    for file in modules.values():
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    raise Unknown("relative_import_unlisted")
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            for name in names:
                if (
                    name not in sys.stdlib_module_names
                    and name not in modules
                    and name != "scrapling"
                ):
                    raise Unknown("import_outside_closed_inputs")
    # Static import proof is not a generalized sandbox. New source review must
    # also account for file reads, config/mounts/TLS artifacts; no dynamic imports.


class DockerCommands:
    """Bounded host CLI candidate: explicit argv, no shell/config mutation/pull."""

    def __init__(self, executable: str) -> None:
        if not Path(executable).is_absolute() or Path(executable).name.lower() not in {
            "docker",
            "docker.exe",
        }:
            raise Unknown("docker_executable_unfrozen")
        self.executable = executable

    def call(self, args: list[str], timeout: float) -> bytes:
        if (
            len(args) < 2
            or args[0] != "container"
            or args[1]
            not in {
                "create",
                "inspect",
                "start",
                "wait",
                "kill",
                "rm",
                "logs",
                "ls",
            }
            or not 0 < timeout <= 120
        ):
            raise Unknown("docker_command_unapproved")
        output, overflow, reader_failed = bytearray(), Event(), Event()
        process = subprocess.Popen(  # noqa: S603 - audited Docker executable/argv, no shell
            [self.executable, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        def collect():
            try:
                while block := process.stdout.read1(4096):
                    if len(output) + len(block) > 1024 * 1024:
                        overflow.set()
                        process.kill()
                        return
                    output.extend(block)
            except Exception:
                # Independent latch: an exit-0 CLI with partial output is NOT success.
                # Never let the thread export exception text, traceback or data.
                reader_failed.set()
                try:
                    process.kill()
                except Exception:
                    reader_failed.set()

        reader = Thread(target=collect, daemon=True)
        reader.start()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                process.wait(timeout=2)
            except Exception:
                reader_failed.set()
            raise Unknown("docker_command_timeout") from None
        finally:
            reader.join(timeout=2)
            if not reader.is_alive():
                try:
                    process.stdout.close()
                except Exception:
                    reader_failed.set()
        if reader.is_alive() or overflow.is_set() or reader_failed.is_set():
            try:
                process.kill()
                process.wait(timeout=2)
            except Exception:
                reader_failed.set()
            raise Unknown("docker_command_failed_or_unbounded") from None
        if process.returncode != 0:
            raise Unknown("docker_command_failed_or_unbounded")
        return bytes(output)


class ParentSupervisor:
    """Deadline is armed before create/start, independent of child/driver hooks.

    Docker APIs are dependency-injected for OFFLINE fake tests. No constructor
    invokes a command. No image build/volume/other container cleanup is included.
    """

    def __init__(self, commands, session: str, arm=None, clock=time.monotonic) -> None:
        if not re.fullmatch(r"flowtracer-r3-dnr-[a-z0-9-]{1,64}", session):
            raise Unknown("session_invalid")
        self.commands, self.session, self.clock = commands, session, clock
        self.arm = arm or self.timer
        self.container = None
        self.failure = None
        self.started = None
        self.lock = Lock()

    @staticmethod
    def timer(seconds, callback):
        timer = Timer(seconds, callback)
        timer.daemon = True
        timer.start()
        return timer

    def remaining(self) -> float:
        remaining = 120 - (self.clock() - self.started)
        if remaining <= 0:
            raise Unknown("parent_deadline")
        return remaining

    def inspect_owned(self, timeout=5):
        if self.container is None:
            raise Unknown("container_identity_unknown")
        try:
            values = json.loads(
                self.commands.call(["container", "inspect", self.container], timeout)
            )
            if len(values) != 1:
                raise ValueError
            value = values[0]
            if (
                value.get("Id") != self.container
                or value.get("Name") != "/" + self.session
                or value.get("Config", {}).get("Labels", {}).get("flowtracer.r3.session")
                != self.session
            ):
                raise ValueError
            return value
        except Exception:
            raise Unknown("container_ownership_unknown") from None

    def timeout(self):
        self.failure = "parent_deadline"
        try:
            self.stop_owned()
        except Exception:
            self.failure = "cleanup_unknown"

    def stop_owned(self):
        with self.lock:
            state = self.inspect_owned()
            if state.get("State", {}).get("Running") is True:
                self.commands.call(["container", "kill", self.container], 5)
            state = self.inspect_owned()
            if state.get("State", {}).get("Running") is not False:
                raise Unknown("cleanup_unknown")

    def verify_source_container(self, state, contract):
        host = state.get("HostConfig", {})
        config = state.get("Config", {})
        if (
            state.get("Image") != contract["image"]
            or config.get("User") != "10001:10001"
            or config.get("Entrypoint") != ["python"]
            or config.get("Cmd") != contract["command"]
            or config.get("Labels", {}).get("flowtracer.r3.parent") != contract["parent_session"]
            or host.get("NetworkMode") != "none"
            or host.get("ReadonlyRootfs") is not True
            or host.get("Privileged") is not False
            or host.get("CapAdd") not in (None, [])
            or host.get("CapDrop") != ["ALL"]
            or host.get("SecurityOpt") != ["no-new-privileges:true"]
            or host.get("PidsLimit") != 128
            or host.get("Memory") != 768 * 1024 * 1024
            or host.get("NanoCpus") != 1000000000
            or host.get("PidMode") not in (None, "")
            or host.get("IpcMode") not in ("private", None, "")
            or host.get("PortBindings") not in (None, {})
            or host.get("Sysctls") not in (None, {})
            or host.get("RestartPolicy", {}).get("Name") != "no"
            or host.get("Tmpfs")
            != {
                "/tmp": "rw,nosuid,noexec,size=256m"  # noqa: S108 - approved ephemeral tmpfs
            }
        ):
            raise Unknown("source_container_boundary_invalid")
        mounts = state.get("Mounts")
        if type(mounts) is not list or any(type(m) is not dict for m in mounts):
            raise Unknown("source_mount_closure_invalid")
        scratch = [m for m in mounts if m.get("Type") == "tmpfs"]
        if len(scratch) > 1 or any(
            m.get("Destination") != SCRATCH_TARGET or m.get("RW") is not True for m in scratch
        ):
            raise Unknown("source_tmpfs_mount_invalid")
        mounts = [m for m in mounts if m.get("Type") != "tmpfs"]
        if len(mounts) != len(contract["mounts"]):
            raise Unknown("source_mount_closure_invalid")
        for expected in contract["mounts"]:
            matches = [m for m in mounts if m.get("Destination") == expected["target"]]
            if (
                len(matches) != 1
                or matches[0].get("Type") != "bind"
                or matches[0].get("RW") is not False
            ):
                raise Unknown("source_mount_invalid")
            # Only the two exact sources in the independently approved plan.
            if matches[0].get("Source") not in expected["inspect_sources"]:
                raise Unknown("source_mount_source_unknown")
            path = checked_repo_file(Path(__file__).absolute().parents[4], Path(expected["source"]))
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]:
                raise Unknown("source_mounted_bytes_changed")

    def run(self, create_args: list[str], *, source_contract=None) -> dict:
        if source_contract is None and isinstance(self.commands, DockerCommands):
            # Full approved create argv/mount/image authority is not frozen yet.
            # Fake tests exercise lifecycle only; never authorize a real launch.
            raise Unknown("actual_launch_manifest_unreviewed")
        if self.started is not None:
            raise Unknown("caller_retry_forbidden")
        if source_contract is not None and create_args != source_contract["create"]:
            raise Unknown("source_create_not_fixed")
        # Caller must freeze every create argument/mount/image before real entry.
        if (
            create_args[:2] != ["container", "create"]
            or "--pull=never" not in create_args
            or "--name" not in create_args
            or create_args[create_args.index("--name") + 1] != self.session
            or "--label" not in create_args
            or f"flowtracer.r3.session={self.session}" not in create_args
        ):
            raise Unknown("create_inputs_unfrozen")
        self.started = self.clock()
        watchdog = self.arm(120, self.timeout)  # BEFORE any container creation/launch
        outcome = {"status": "NO_GO", "runtime_verified": False, "cleanup": "UNKNOWN"}
        creation_attempted = False
        try:
            if source_contract is not None:
                existing = self.commands.call(
                    [
                        "container",
                        "ls",
                        "-a",
                        "--no-trunc",
                        "--filter",
                        f"name=^/{self.session}$",
                        "--format",
                        "{{json .ID}}",
                    ],
                    min(5, self.remaining()),
                )
                if existing.strip():
                    raise Unknown("source_container_name_in_use")
            creation_attempted = True
            container = self.commands.call(create_args, self.remaining()).decode("ascii").strip()
            if not re.fullmatch(r"[0-9a-f]{64}", container):
                raise Unknown("container_identity_unknown")
            self.container = container
            state = self.inspect_owned(min(5, self.remaining()))
            if source_contract is not None:
                self.verify_source_container(state, source_contract)
            if self.failure:
                raise Unknown("parent_deadline")
            self.commands.call(["container", "start", container], self.remaining())
            if self.failure:
                raise Unknown("parent_deadline")
            exited = self.commands.call(["container", "wait", container], self.remaining()).strip()
            state = self.inspect_owned(min(5, self.remaining()))
            if exited != b"0" or state.get("State", {}).get("Running") is not False or self.failure:
                raise Unknown("probe_exit_unknown")
            if source_contract is not None and (
                type(state.get("State", {}).get("Pid")) is not int
                or type(state.get("State", {}).get("ExitCode")) is not int
                or state.get("State", {}).get("Pid") != 0
                or state.get("State", {}).get("ExitCode") != 0
            ):
                raise Unknown("source_process_exit_unknown")
            # Natural exit is necessary, not receipt/identity/R3 success.
            outcome["natural_exit"] = True
            if source_contract is not None:
                self.verify_source_container(state, source_contract)
                raw = self.commands.call(
                    ["container", "logs", self.container], min(5, self.remaining())
                )
                if len(raw) > 65536:
                    raise Unknown("source_log_budget")
                observation = strict_json(raw)
                if (
                    type(observation) is not dict
                    or set(observation)
                    != {
                        "schema_version",
                        "status",
                        "session",
                        "phase",
                        "target_permission",
                        "close_confirmed",
                        "fetch_returned",
                        "facts",
                    }
                    or observation["schema_version"] != "r3-source-observation-v1"
                    or observation["status"] != "SOURCE_OBSERVED"
                    or observation["session"] != source_contract["parent_session"]
                    or observation["phase"] != source_contract["phase"]
                    or observation["target_permission"] != "DENIED"
                    or observation["close_confirmed"] is not True
                    or observation["fetch_returned"] is not False
                    or type(observation["facts"]) is not dict
                    or observation["facts"].get("target_permission") != "DENIED"
                    or self.failure
                ):
                    raise Unknown("source_observation_invalid")
                outcome["observation"] = observation
        except Exception:
            outcome["failure"] = "probe_or_supervision_unknown"
        finally:
            try:
                if source_contract is not None and self.container is None:
                    if not creation_attempted:
                        raise Unknown("source_no_owned_container")
                    values = strict_json(
                        self.commands.call(["container", "inspect", self.session], 5)
                    )
                    if type(values) is not list or len(values) != 1:
                        raise Unknown("source_create_identity_unknown")
                    value = values[0]
                    candidate = value.get("Id")
                    if (
                        not isinstance(candidate, str)
                        or not re.fullmatch(r"[0-9a-f]{64}", candidate)
                        or value.get("Name") != "/" + self.session
                        or value.get("Config", {}).get("Labels", {}).get("flowtracer.r3.session")
                        != self.session
                        or value.get("Config", {}).get("Labels", {}).get("flowtracer.r3.parent")
                        != source_contract["parent_session"]
                    ):
                        raise Unknown("source_create_ownership_unknown")
                    self.container = candidate
                self.stop_owned()
                self.commands.call(["container", "rm", self.container], 5)
                remaining = self.commands.call(
                    [
                        "container",
                        "ls",
                        "-a",
                        "--no-trunc",
                        "--filter",
                        f"id={self.container}",
                        "--format",
                        "{{json .ID}}",
                    ],
                    5,
                )
                if remaining.strip():
                    raise Unknown("cleanup_absence_unknown")
                outcome["cleanup"] = (
                    "ABSENT_IN_INJECTED_DAEMON_VIEW"
                    if source_contract is None
                    else "OWNED_CONTAINER_REMOVED"
                )
            except Exception:
                outcome["cleanup"] = "UNKNOWN"
            watchdog.cancel()
        if source_contract is not None:
            outcome["status"] = (
                "SOURCE_OBSERVED"
                if outcome.get("observation")
                and outcome.get("natural_exit") is True
                and outcome["cleanup"] == "OWNED_CONTAINER_REMOVED"
                and not self.failure
                and "failure" not in outcome
                else "BLOCKED"
            )
            outcome["target_permission"] = "DENIED"
        # Legacy target mode remains NO_GO. Source observations never admit a
        # target; fake daemon tests alone are not real cleanup/runtime proof.
        return outcome
