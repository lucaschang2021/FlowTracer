"""Exclusive probe supervision/input closure; never launched by offline tests."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from threading import Event, Lock, Thread, Timer

from collector import Unknown


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

    def run(self, create_args: list[str]) -> dict:
        if isinstance(self.commands, DockerCommands):
            # Full approved create argv/mount/image authority is not frozen yet.
            # Fake tests exercise lifecycle only; never authorize a real launch.
            raise Unknown("actual_launch_manifest_unreviewed")
        if self.started is not None:
            raise Unknown("caller_retry_forbidden")
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
        try:
            container = self.commands.call(create_args, self.remaining()).decode("ascii").strip()
            if not re.fullmatch(r"[0-9a-f]{64}", container):
                raise Unknown("container_identity_unknown")
            self.container = container
            self.inspect_owned(min(5, self.remaining()))
            if self.failure:
                raise Unknown("parent_deadline")
            self.commands.call(["container", "start", container], self.remaining())
            if self.failure:
                raise Unknown("parent_deadline")
            exited = self.commands.call(["container", "wait", container], self.remaining()).strip()
            state = self.inspect_owned(min(5, self.remaining()))
            if exited != b"0" or state.get("State", {}).get("Running") is not False or self.failure:
                raise Unknown("probe_exit_unknown")
            # Natural exit is necessary, not receipt/identity/R3 success.
            outcome["natural_exit"] = True
        except Exception:
            outcome["failure"] = "probe_or_supervision_unknown"
        finally:
            try:
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
                outcome["cleanup"] = "ABSENT_IN_INJECTED_DAEMON_VIEW"
            except Exception:
                outcome["cleanup"] = "UNKNOWN"
            watchdog.cancel()
        # Fake daemon view is not real cleanup proof. Dependency orchestration and
        # frozen create inputs are still missing; status always remains NO_GO.
        return outcome
