"""Pure deadline/terminal rules; no process creation or permission surrogate."""

import hashlib
import threading
import time
from dataclasses import dataclass

from contract import FILES, canonical, digest, identifier, object_fields, reject, strict_json

H1_CONTROL = "a215051d2a2f53b41d9b22339f1bab52a27dbdf7"


@dataclass(frozen=True)
class HostPins:
    """Externally pinned offline projection; construction grants NO authority."""

    record_sha256: str
    candidate: str
    inputs_sha256: str
    plan_sha256: str
    image_sha256: str
    container_id: str
    container_name: str
    session: str
    execution: str
    browser_version: str
    executable: str
    profile: str


@dataclass(frozen=True)
class OwnedFacts:
    container_id: str
    container_name: str
    session: str
    image_sha256: str


@dataclass(frozen=True)
class CandidateBytes:
    candidate: str
    git_files: dict
    raw_files: dict


@dataclass(frozen=True)
class Consumption:
    execution: str
    record_sha256: str
    purpose: str


def validate_host_input(raw: bytes, pins: HostPins, snapshot: CandidateBytes) -> None:
    """Check closed projection/raw closure. Not a record issuer or runtime permit."""
    if type(pins) is not HostPins or type(snapshot) is not CandidateBytes:
        reject("host_input_invalid")
    for value in (
        pins.record_sha256,
        pins.inputs_sha256,
        pins.plan_sha256,
        pins.image_sha256,
        pins.container_id,
    ):
        digest(value)
    digest(pins.candidate, 40)
    for value in (pins.container_name, pins.session, pins.execution):
        identifier(value)
    for value in (pins.browser_version, pins.executable, pins.profile):
        if type(value) is not str or not value or len(value) > 512:
            reject("host_identity_input_invalid")
    if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != pins.record_sha256:
        reject("host_record_digest_mismatch")
    expected = {
        "epoch": "GOV-2.1",
        "control": H1_CONTROL,
        "candidate": pins.candidate,
        "inputs_sha256": pins.inputs_sha256,
        "plan_sha256": pins.plan_sha256,
        "image_sha256": pins.image_sha256,
        "container_id": pins.container_id,
        "container_name": pins.container_name,
        "session": pins.session,
        "execution": pins.execution,
        "purpose": "r3-composite-h1",
        "r1e_payload_sha256": "5f4cf5acdf06a86f9b8907375f6f8f239ecf18152762b889f1e254b01e447e3b",
        "r1e_manifest_sha256": "f8d8bd0b64dfac53e244b00f29fbc9f18ed44b94491323b3f49ba2af191912e8",
        "r1e": "R1E-PR66",
        "r2c": "R2C-A4-PR68",
    }
    if canonical(strict_json(raw)) != canonical(expected):
        reject("host_record_scope_mismatch")
    if snapshot.candidate != pins.candidate:
        reject("candidate_mismatch")
    for files in (snapshot.git_files, snapshot.raw_files):
        if type(files) is not dict or set(files) != set(FILES):
            reject("candidate_closure_invalid")
        if any(type(value) is not bytes for value in files.values()):
            reject("candidate_closure_invalid")
    if snapshot.git_files != snapshot.raw_files:
        reject("candidate_raw_drift")
    files = snapshot.raw_files
    for name, expected_hash in (
        ("execution-inputs.json", pins.inputs_sha256),
        ("execution-plan.json", pins.plan_sha256),
    ):
        if hashlib.sha256(files[name]).hexdigest() != expected_hash:
            reject("candidate_digest_mismatch")
    manifest = strict_json(files["execution-inputs.json"])
    plan = strict_json(files["execution-plan.json"])
    if manifest.get("control_commit") != H1_CONTROL or manifest.get("scope") != "OFFLINE_ONLY":
        reject("candidate_control_mismatch")
    leaves = set(FILES) - {"execution-inputs.json", "execution-plan.json"}
    entries = manifest.get("files")
    if type(entries) is not dict or set(entries) != leaves:
        reject("candidate_closure_invalid")
    for name, entry in entries.items():
        item = object_fields(entry, {"sha256", "git_blob"})
        content = files[name]
        blob = b"blob " + str(len(content)).encode() + b"\x00" + content
        if (
            hashlib.sha256(content).hexdigest() != item["sha256"]
            or hashlib.sha1(blob, usedforsecurity=False).hexdigest() != item["git_blob"]
        ):
            reject("candidate_leaf_mismatch")
    if plan.get("input_sha256") != pins.inputs_sha256 or plan.get("runtime_permission") != "NO_GO":
        reject("candidate_plan_invalid")


class OwnedWatchdog:
    """Host-only independent timer; never holds/calls page, Playwright or CDP.

    Executor contract: every inspect/kill/wait/remove/absence honors timeout_ms.
    Actual host executor is UNBOUND. Synthetic tests do not attest host behavior.
    """

    def __init__(self, pins, executor, clock=time.monotonic_ns, timer_factory=threading.Timer):
        self.pins, self.executor, self.clock = pins, executor, clock
        self.timer_factory = timer_factory
        self.started = clock()
        self.parent_end = self.started + 120_000_000_000
        self.timer = None
        self.lock = threading.Lock()
        self.outcome = "not_started"

    def expected(self):
        return OwnedFacts(
            self.pins.container_id,
            self.pins.container_name,
            self.pins.session,
            self.pins.image_sha256,
        )

    def owned(self, timeout_ms):
        facts = self.executor.inspect_owned(self.pins.container_id, timeout_ms)
        if type(facts) is not OwnedFacts or facts != self.expected():
            reject("owned_identity_mismatch")

    def arm(self):
        if self.timer is not None:
            reject("watchdog_already_armed")
        left = 15 - (self.clock() - self.started) / 1_000_000_000
        if left <= 0:
            reject("deadline")
        self.timer = self.timer_factory(left, self.reap)
        self.timer.daemon = True
        self.timer.start()

    def bounded(self, callback):
        if self.outcome != "not_started":
            reject("callback_after_cleanup")
        timeout_ms = remaining_timeout_ms(self.started, self.clock())
        end = self.clock() + timeout_ms * 1_000_000
        timer = self.timer_factory(timeout_ms / 1000, self.reap)
        timer.daemon = True
        timer.start()
        try:
            result = callback()
            if self.clock() >= end or self.outcome != "not_started":
                reject("callback_deadline")
            return result
        finally:
            timer.cancel()

    def reap(self):
        if not self.lock.acquire(blocking=False):
            return
        try:
            if self.outcome != "not_started":
                return
            end = min(self.parent_end, self.clock() + 30_000_000_000)

            def budget():
                left = (end - self.clock()) // 1_000_000
                if left <= 0:
                    reject("cleanup_deadline")
                return min(5000, left)

            self.owned(budget())
            self.executor.kill(self.pins.container_id, budget())
            code = self.executor.wait(self.pins.container_id, budget())
            if type(code) is not int:
                reject("cleanup_wait_unknown")
            self.owned(budget())
            self.executor.remove(self.pins.container_id, budget())
            if self.executor.absent(self.pins.container_id, budget()) is not True:
                reject("cleanup_absence_unknown")
            budget()
            self.outcome = "owned_removed"
        except Exception:
            self.outcome = "cleanup_unknown"
        finally:
            self.lock.release()

    def finish(self):
        self.reap()
        if self.timer is not None:
            self.timer.cancel()
        if self.outcome != "owned_removed":
            reject("cleanup_unknown")


class H1Host:
    """Tested HostPort adapter; H2 ports delegated, real factory still NO_GO."""

    def __init__(
        self,
        pins,
        record,
        executor,
        native_port,
        clock=time.monotonic_ns,
        timer_factory=threading.Timer,
    ):
        self.pins, self.record, self.executor = pins, record, executor
        self.native_port = native_port
        self.watchdog = OwnedWatchdog(pins, executor, clock, timer_factory)
        self.stage = 0
        self.driver_thread = threading.get_ident()

    def __getattr__(self, name):
        method = getattr(self.native_port, name)
        return lambda *args, **kwargs: self.watchdog.bounded(lambda: method(*args, **kwargs))

    def run_callback(self, callback):
        if threading.get_ident() != self.driver_thread:
            reject("driver_thread_mismatch")
        return self.watchdog.bounded(callback)

    def clock_ns(self):
        return self.watchdog.clock()

    def execution_id(self):
        return self.pins.execution

    def verify_runtime(self):
        self.watchdog.arm()
        snapshot = self.watchdog.bounded(lambda: self.executor.candidate_bytes(self.pins.candidate))
        validate_host_input(self.record, self.pins, snapshot)
        self.watchdog.bounded(
            lambda: self.watchdog.owned(
                remaining_timeout_ms(self.watchdog.started, self.clock_ns())
            )
        )
        used = self.watchdog.bounded(
            lambda: self.executor.consume_once(
                self.pins.execution, self.pins.record_sha256, "r3-composite-h1"
            )
        )
        if type(used) is not Consumption or used != Consumption(
            self.pins.execution, self.pins.record_sha256, "r3-composite-h1"
        ):
            reject("host_record_consumed_or_invalid")
        self.stage = 1

    def arm_parent_deadline(self, milliseconds):
        if self.stage != 1 or milliseconds != 15000:
            reject("identity_order")
        remaining_timeout_ms(self.watchdog.started, self.clock_ns())

    def verify_browser(self, page, timeout_ms):
        if self.stage != 1 or threading.get_ident() != self.driver_thread:
            reject("browser_identity_order_or_thread")
        if type(timeout_ms) is not int or not 0 < timeout_ms <= 5000:
            reject("invalid_identity_timeout")
        session = None
        try:
            browser = page.context.browser
            if browser is None or page.context not in browser.contexts:
                reject("browser_context_mismatch")
            session = self.watchdog.bounded(browser.new_browser_cdp_session)
            version = self.watchdog.bounded(lambda: session.send("Browser.getVersion"))
            command = self.watchdog.bounded(lambda: session.send("Browser.getBrowserCommandLine"))
            args = command.get("arguments") if type(command) is dict else None
            if (
                type(version) is not dict
                or version.get("product") != self.pins.browser_version
                or type(args) is not list
                or not args
                or any(type(arg) is not str for arg in args)
                or args[0] != self.pins.executable
                or [arg for arg in args if arg.startswith("--user-data-dir=")]
                != ["--user-data-dir=" + self.pins.profile]
                or "--remote-debugging-pipe" not in args
                or any(arg.startswith("--remote-debugging-port") for arg in args)
            ):
                reject("browser_identity_mismatch")
            self.stage = 2
        except Exception:
            reject("browser_identity_failed")
        finally:
            if session is not None:
                try:
                    self.watchdog.bounded(session.detach)
                except Exception:
                    reject("browser_identity_detach_failed")

    def close_and_reap_owned(self):
        self.watchdog.finish()


def remaining_timeout_ms(start_ns: int, now_ns: int, limit_ms: int = 15000) -> int:
    if any(type(v) is not int for v in (start_ns, now_ns, limit_ms)):
        reject("invalid_clock")
    if start_ns < 0 or now_ns < start_ns or not 1 <= limit_ms <= 15000:
        reject("invalid_clock")
    remaining = limit_ms - (now_ns - start_ns) // 1000000 - 1000
    if remaining <= 0:
        reject("deadline")
    return min(5000, remaining)


def terminal(value: object) -> None:
    item = object_fields(value, {"outcome", "cleanup", "network_audit", "duration_ms"})
    if (item["outcome"], item["cleanup"], item["network_audit"]) != (
        "completed",
        "owned_removed",
        "complete",
    ):
        reject("invalid_terminal")
    if type(item["duration_ms"]) is not int or not 0 < item["duration_ms"] < 15000:
        reject("invalid_terminal")


def host_session():
    """No permit yet. Later host-owned exact-record loader belongs at this boundary.

    Deliberately accepts no caller object, page message, environment flag or Boolean.
    No signed-record scheme is invented here and nothing is read while forbidden.
    """
    reject("NO_GO_exact_host_record_not_frozen")


def launch_real(*_args, **_kwargs):
    host = host_session()  # must reject BEFORE runtime import or process/network I/O
    from harness import _execute_driver
    from scrapling.fetchers import DynamicFetcher

    return _execute_driver(host, DynamicFetcher.fetch)


if __name__ == "__main__":
    raise SystemExit("NO_GO_real_execution_not_authorized")
