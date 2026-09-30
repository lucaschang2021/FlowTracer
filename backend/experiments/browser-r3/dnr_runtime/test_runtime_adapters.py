"""Only injected CDP/context/process/clock/stream doubles, no Browser or Docker."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from collector import ClockEvidence, Collector, Unknown, evaluate, observe_sources, observed_clock
from contract import FLAGS, MANIFEST, MOUNT, SESSION, fingerprint
from fixture import PAGE, WORKER, response
from harness import Terminal
from harness_v2 import Guard
from probe import (
    SourcePreflightCompleted,
    close_confirmed,
    fetch_once,
    guarded_setup,
    invoke_dynamic_fetch,
    source_fetch_once,
    source_fetch_options,
)
from proxy import denied_request, handler_type, read_headers, valid_connect
from supervisor import (
    HOST_RECORD,
    DockerCommands,
    HostApproval,
    ParentSupervisor,
    check_inputs,
    source_plan,
    source_preflight,
)

HERE = Path(__file__).parent
EXTENSION = HERE / "extension-v2"
EXT_HASHES = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in EXTENSION.iterdir()}
EXT_ID = "a" * 32
SOURCE_PROFILE = Path("/tmp/r3-source/baseline/profile")  # noqa: S108 - fake-only path


def snapshot():
    return {
        "schema_version": "r3-dnr-audit-v2",
        "extension_id": EXT_ID,
        "session": SESSION,
        "ok": True,
        "configured": True,
        "fatal": None,
        "enabled_rulesets": ["ws_default_deny_v1"],
        "dynamic_rules": [],
        "session_rules": [],
        "observer_registered": True,
        "flushed": True,
        "storage_access_level": "TRUSTED_CONTEXTS",
        "observer_epoch": "SYNTHETIC-epoch",
        "sequence": 0,
        "receipts": [],
    }


def receipt():
    return {
        "schema_version": "r3-dnr-receipt-v2",
        "extension_id": EXT_ID,
        "session": SESSION,
        "sequence": 1,
        "observer_epoch": "SYNTHETIC-epoch",
        "request_id": "SYNTHETIC-dnr-1",
        "timestamp": 1700000000000,
        "timestamp_source": "trusted_observer_callback_epoch_ms",
        "ruleset_id": "ws_default_deny_v1",
        "rule_id": 1,
        "action": "block",
        "resource_type": "websocket",
        "safe_request_fingerprint": fingerprint("page", "ws"),
        "tab_id": None,
        "frame_id": None,
        "document_id": None,
        "initiator": None,
        "initiator_note": "omitted_to_prevent_origin_secret_exposure",
    }


class FakeCDP:
    def __init__(self):
        self.state = snapshot()
        self.identity = {
            "origin": f"chrome-extension://{EXT_ID}",
            "id": EXT_ID,
            "manifest": MANIFEST,
        }
        self.targets = [
            {"type": "service_worker", "url": f"chrome-extension://{EXT_ID}/observer.js"}
        ]
        self.fail = False

    def send(self, method, args=None):
        if self.fail:
            raise RuntimeError("SYNTHETIC_SECRET")
        if method == "Target.getTargets":
            return {"targetInfos": self.targets}
        assert method == "Runtime.evaluate"  # noqa: S101 - offline double
        value = self.state if args["expression"].startswith("r3Audit.") else self.identity
        return {"result": {"type": "object", "value": copy.deepcopy(value)}}


def collector():
    cdp = FakeCDP()
    profile = {
        "exclusive_new_profile": True,
        "initial_entries": [],
        "readonly_mount": True,
        "approved_extension_flags": FLAGS,
        "mount_target": MOUNT,
    }
    context = SimpleNamespace(new_cdp_session=lambda page: cdp)
    value = Collector(cdp, context, EXTENSION, EXT_HASHES, profile)
    return value, cdp


def bound():
    value, cdp = collector()
    value.discover()
    value.bind_audit_page(SimpleNamespace(url=f"chrome-extension://{EXT_ID}/audit.html"))
    return value, cdp


class Timer:
    def __init__(self, seconds, callback):
        self.seconds, self.callback, self.cancelled = seconds, callback, False

    def cancel(self):
        self.cancelled = True


def fake_guard():
    timers, kills = [], []

    def arm(seconds, callback):
        timer = Timer(seconds, callback)
        timers.append(timer)
        return timer

    return Guard(arm, lambda: kills.append(True), lambda: 0), timers, kills


def page_double(*, connected=False, closed=True, event=True, fail=False):
    callbacks = []
    browser = SimpleNamespace(
        on=lambda name, callback: callbacks.append(callback), is_connected=lambda: connected
    )

    def close():
        if fail:
            raise RuntimeError("SYNTHETIC_SECRET")
        if event:
            for callback in callbacks:
                callback()

    context = SimpleNamespace(browser=browser, close=close)
    return SimpleNamespace(context=context, is_closed=lambda: closed)


def ws_request(path="/dnr-page-ws", headers=b""):
    return (
        (
            f"GET http://websocket-r3.test:8443{path} HTTP/1.1\r\n"
            "Host: websocket-r3.test:8443\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
        ).encode()
        + headers
        + b"\r\n"
    )


class FakeDocker:
    def __init__(self, timers):
        self.timers, self.calls, self.running = timers, [], False
        self.id = "a" * 64
        self.foreign, self.residual, self.wait_fail = False, False, False
        self.on_start = None

    def call(self, args, timeout):
        self.calls.append(args)
        if args[1] == "create":
            assert self.timers[0].seconds == 120  # noqa: S101 - fake ordering proof
            return self.id.encode()
        if args[1] == "inspect":
            return json.dumps(
                [
                    {
                        "Id": self.id,
                        "Name": "/" + SESSION,
                        "Config": {
                            "Labels": {
                                "flowtracer.r3.session": "FOREIGN" if self.foreign else SESSION
                            }
                        },
                        "State": {"Running": self.running, "Pid": 0, "ExitCode": 0},
                    }
                ]
            ).encode()
        if args[1] == "start":
            self.running = True
            if self.on_start:
                self.on_start()
            return b""
        if args[1] == "wait":
            if self.wait_fail:
                raise RuntimeError("SYNTHETIC failure")
            self.running = False
            return b"0\n"
        if args[1] == "kill":
            self.running = False
        if args[1] == "ls":
            return self.id.encode() if self.residual else b""
        return b""


def supervisor_model():
    timers = []

    def arm(seconds, callback):
        timer = Timer(seconds, callback)
        timers.append(timer)
        return timer

    api = FakeDocker(timers)
    parent = ParentSupervisor(api, SESSION, arm, clock=lambda: 0)
    create = [
        "container",
        "create",
        "--pull=never",
        "--name",
        SESSION,
        "--label",
        f"flowtracer.r3.session={SESSION}",
    ]
    return parent, api, timers, create


class SyntheticSourceDocker:
    """In-memory daemon; used only by tests, never selectable by prod inputs."""

    def __init__(self, failure=None):
        self.objects, self.calls = {}, []
        self.failure = failure
        self.start_phases = []

    def call(self, args, timeout):
        self.calls.append(args)
        operation = args[1]
        if operation == "ls":
            criterion = args[args.index("--filter") + 1]
            if criterion.startswith("name="):
                name = criterion.removeprefix("name=^/").removesuffix("$")
                return b"\n".join(
                    i.encode() for i, o in self.objects.items() if o["Name"] == "/" + name
                )
            identifier = criterion.removeprefix("id=")
            return identifier.encode() if identifier in self.objects else b""
        if operation == "create":
            name = args[args.index("--name") + 1]
            phase = "enabled" if name.endswith("-enabled") else "baseline"
            identifier = ("b" if phase == "enabled" else "a") * 64
            labels = dict(args[n + 1].split("=", 1) for n, a in enumerate(args) if a == "--label")
            mounts = []
            for n, a in enumerate(args):
                if a == "--mount":
                    parts = dict(v.split("=", 1) for v in args[n + 1].split(",") if "=" in v)
                    mounts.append(
                        {
                            "Type": "bind",
                            "Source": parts["source"],
                            "Destination": parts["target"],
                            "RW": False,
                        }
                    )
            entrypoint = args.index("--entrypoint")
            self.objects[identifier] = {
                "Id": identifier,
                "Name": "/" + name,
                "Image": args[entrypoint + 2],
                "Config": {
                    "User": "10001:10001",
                    "Entrypoint": ["python"],
                    "Cmd": args[entrypoint + 3 :],
                    "Labels": labels,
                },
                "HostConfig": {
                    "NetworkMode": "none",
                    "ReadonlyRootfs": True,
                    "Privileged": False,
                    "CapAdd": None,
                    "CapDrop": ["ALL"],
                    "SecurityOpt": ["no-new-privileges:true"],
                    "PidsLimit": 128,
                    "Memory": 768 * 1024 * 1024,
                    "NanoCpus": 1000000000,
                    "PidMode": "",
                    "IpcMode": "private",
                    "PortBindings": None,
                    "Sysctls": None,
                    "RestartPolicy": {"Name": "no"},
                    "Tmpfs": {"/tmp": "rw,nosuid,noexec,size=256m"},  # noqa: S108 - fake inspect only
                },
                "Mounts": mounts,
                "State": {"Running": False, "Pid": 0, "ExitCode": 0},
            }
            if self.failure == "create_interrupted":
                raise RuntimeError("SYNTHETIC create output interrupted")
            return identifier.encode()
        key = args[2]
        if key not in self.objects:
            key = next((i for i, o in self.objects.items() if o["Name"] == "/" + key), key)
        value = self.objects[key]
        phase = "enabled" if value["Name"].endswith("-enabled") else "baseline"
        if operation == "inspect":
            result = copy.deepcopy(value)
            if self.failure == "network":
                result["HostConfig"]["NetworkMode"] = "bridge"
            if self.failure == "writable_mount":
                result["Mounts"][0]["RW"] = True
            if self.failure == "foreign":
                result["Config"]["Labels"]["flowtracer.r3.session"] = "FOREIGN"
            return json.dumps([result]).encode()
        if operation == "start":
            self.start_phases.append(phase)
            value["State"]["Running"] = True
        if operation in {"wait", "kill"}:
            value["State"]["Running"] = False
            if operation == "wait":
                return b"0"
        if operation == "logs":
            return json.dumps(
                {
                    "schema_version": "r3-source-observation-v1",
                    "status": "SOURCE_OBSERVED",
                    "session": value["Config"]["Labels"]["flowtracer.r3.parent"],
                    "phase": phase,
                    "target_permission": "DENIED",
                    "close_confirmed": self.failure != "close",
                    "fetch_returned": False,
                    "facts": {"target_permission": "DENIED", "inventory_complete": False},
                }
            ).encode()
        if operation == "rm" and self.failure != "cleanup":
            self.objects.pop(key)
        return b""


class SourcePreflightTests(unittest.TestCase):
    """SYNTHETIC only: no controller record, subprocess, Docker or Browser."""

    def run_fetch(self, fetch, *, close=True, facts=None):
        guard, _, _ = fake_guard()
        with (
            patch(
                "probe.observe_sources",
                return_value=facts or {"target_permission": "DENIED", "inventory_complete": False},
            ),
            patch("probe.close_confirmed", return_value=close),
        ):
            return source_fetch_once(
                fetch,
                "baseline",
                SOURCE_PROFILE,
                SESSION,
                guard,
                EXTENSION,
            )

    def test_setup_signal_prevents_goto_action_and_response_path(self):
        calls = []

        def fetch(url, **options):
            self.assertEqual(url, "about:blank")
            self.assertEqual(options["retries"], 1)
            self.assertIs(options["google_search"], False)
            self.assertNotIn("proxy", options)
            self.assertNotIn("page_action", options)
            calls.append("setup")
            options["page_setup"](SimpleNamespace(url="about:blank"))
            calls.extend(["goto", "page_action", "response"])

        result = self.run_fetch(fetch)
        self.assertEqual(calls, ["setup"])
        self.assertIs(result["close_confirmed"], True)
        self.assertIs(result["fetch_returned"], False)
        self.assertEqual(result["target_permission"], "DENIED")

    def test_close_failure_wrong_origin_and_normal_return_refuse(self):
        def driver(url, **options):
            options["page_setup"](SimpleNamespace(url="about:blank"))

        with self.assertRaises(Terminal):
            self.run_fetch(driver, close=False)
        with self.assertRaises(Terminal):
            self.run_fetch(lambda url, **opts: None)
        with self.assertRaises(Terminal):
            self.run_fetch(
                lambda url, **opts: opts["page_setup"](
                    SimpleNamespace(url="https://target.invalid")
                )
            )

    def test_only_exact_signal_is_caught_other_exceptions_never_succeed(self):
        for exception in (
            ValueError("SYNTHETIC"),
            KeyboardInterrupt(),
            SystemExit(),
            BaseException(),
        ):

            def driver(url, exception=exception, **options):
                raise exception

            with self.assertRaises(type(exception)):
                self.run_fetch(driver)

        class WrongSignal(SourcePreflightCompleted):
            pass

        with self.assertRaises(Terminal):
            self.run_fetch(lambda url, **options: (_ for _ in ()).throw(WrongSignal({})))
        with self.assertRaises(Terminal):
            self.run_fetch(
                lambda url, **options: (_ for _ in ()).throw(SourcePreflightCompleted({}))
            )

        def swallowing_driver(url, **options):
            try:
                options["page_setup"](SimpleNamespace(url="about:blank"))
            except SourcePreflightCompleted:
                return None

        with self.assertRaises(Terminal):
            self.run_fetch(swallowing_driver)

        def forged_after_close(url, **options):
            try:
                options["page_setup"](SimpleNamespace(url="about:blank"))
            except SourcePreflightCompleted as completed:
                raise SourcePreflightCompleted(completed.facts) from None

        with self.assertRaises(Terminal):
            self.run_fetch(forged_after_close)

    def test_failure_latch_close_timeout_and_repeated_setup(self):
        guard, _, _ = fake_guard()

        def close(page):
            guard.denied = True
            return True

        with (
            patch("probe.observe_sources", return_value={"target_permission": "DENIED"}),
            patch("probe.close_confirmed", side_effect=close),
            self.assertRaises(Terminal),
        ):
            source_fetch_once(
                lambda url, **opts: opts["page_setup"](SimpleNamespace(url="about:blank")),
                "baseline",
                SOURCE_PROFILE,
                SESSION,
                guard,
                EXTENSION,
            )
        guard, timers, _ = fake_guard()
        ticks = iter([0, 15])
        guard.clock = lambda: next(ticks)
        with (
            patch("probe.observe_sources", return_value={"target_permission": "DENIED"}),
            patch("probe.close_confirmed") as close,
            self.assertRaises(Terminal),
        ):
            source_fetch_once(
                lambda url, **opts: opts["page_setup"](SimpleNamespace(url="about:blank")),
                "baseline",
                SOURCE_PROFILE,
                SESSION,
                guard,
                EXTENSION,
            )
        close.assert_not_called()
        self.assertEqual([t.seconds for t in timers], [120, 15])
        guard, _, _ = fake_guard()
        ticks = iter([0, 0, 0, 5])
        guard.clock = lambda: next(ticks)
        with (
            patch("probe.observe_sources", return_value={"target_permission": "DENIED"}),
            patch("probe.close_confirmed", return_value=True),
            self.assertRaises(Terminal),
        ):
            source_fetch_once(
                lambda url, **opts: opts["page_setup"](SimpleNamespace(url="about:blank")),
                "baseline",
                SOURCE_PROFILE,
                SESSION,
                guard,
                EXTENSION,
            )

    def test_fixed_plan_network_profiles_phase_and_v2_only(self):
        rows = json.loads((HERE / "execution-inputs.json").read_bytes())["inputs"]
        plan = source_plan(rows)
        self.assertEqual(plan["dependency_services"], [])
        self.assertEqual(plan["target_permission"], "DENIED")
        self.assertEqual(plan["url"], "about:blank")
        for item in plan["phases"]:
            argv = item["create_argv"]
            self.assertEqual(argv[argv.index("--network") + 1], "none")
            self.assertEqual(argv[argv.index("--user") + 1], "10001:10001")
            self.assertNotIn("--sysctl", argv)
            extensions = [s for s in item["mounts"] if "/extension-v2/" in s["source"]]
            self.assertEqual(len(extensions), 0 if item["phase"] == "baseline" else 5)
            self.assertEqual(
                item["profile"], SOURCE_PROFILE.as_posix().replace("baseline", item["phase"])
            )
        for phase, profile in (("retry", "invalid"), ("baseline", "invalid")):
            with self.assertRaises(Unknown):
                source_fetch_options(Path(profile), phase, None)

    def test_missing_record_wrong_object_and_bool_authority_reject(self):
        with self.assertRaises(Unknown):
            source_preflight({"approved": True})
        approval = HostApproval(HOST_RECORD, "a" * 64, "b" * 40, {"session": SESSION})
        with self.assertRaises(Unknown):
            approval.read_approved_record(SESSION, "baseline")
        record = {
            "schema_version": "r3-source-preflight-approval-v1",
            "mode": "source-preflight",
            "candidate_commit": "c" * 40,
            "manifest_raw_sha256": "d" * 64,
            "plan_raw_sha256": "e" * 64,
            "image_id": "sha256:" + "f" * 64,
            "r1e_manifest_sha256": (
                "f8d8bd0b64dfac53e244b00f29fbc9f18ed44b94491323b3f49ba2af191912e8"
            ),
            "r1e_payload_sha256": (
                "5f4cf5acdf06a86f9b8907375f6f8f239ecf18152762b889f1e254b01e447e3b"
            ),
            "control_commit": "b" * 40,
            "session": SESSION,
            "phases": ["baseline", "enabled"],
            "launches_per_phase": 1,
            "target_permission": "DENIED",
        }

        def read(value, requested=SESSION):
            raw = json.dumps(value).encode()
            candidate = HostApproval(HOST_RECORD, hashlib.sha256(raw).hexdigest(), "b" * 40, value)
            with (
                patch("supervisor.checked_repo_file"),
                patch.object(Path, "open", return_value=io.BytesIO(raw)),
            ):
                return candidate.read_approved_record(requested, "baseline")

        self.assertEqual(read(record)["mode"], "source-preflight")
        for edit in (
            {"launches_per_phase": True},
            {"target_permission": "ALLOW"},
            {"phases": ["enabled", "baseline"]},
            {"extra": "x"},
            {"image_id": "sha256:" + "x" * 64},
        ):
            with self.assertRaises(Unknown):
                read({**record, **edit})
        with self.assertRaises(Unknown):
            read(record, SESSION + "-different")
        raw = json.dumps(record).encode()
        with (
            patch("supervisor.checked_repo_file"),
            patch.object(Path, "open", return_value=io.BytesIO(raw)),
            self.assertRaises(Unknown),
        ):
            HostApproval(HOST_RECORD, "0" * 64, "b" * 40, record).read_approved_record(
                SESSION, "baseline"
            )

    def test_internal_observations_unknown_never_target_or_ws(self):
        for enabled in (False, True):
            cdp = FakeCDP()
            if not enabled:
                cdp.targets = []
            old_send = cdp.send

            def send(method, args=None, old_send=old_send):
                if method == "Browser.getVersion":
                    return {"product": "Chrome/151.0.7922.34"}
                if method == "Browser.getBrowserCommandLine":
                    raise RuntimeError("SYNTHETIC")
                if method == "Runtime.evaluate" and args["expression"].startswith("new Promise"):
                    return {"result": {"type": "object", "value": {"ok": False}}}
                return old_send(method, args)

            cdp.send = send
            visited = []

            class Page:
                url = "about:blank"

                def goto(self, url, visited=visited, **kwargs):
                    visited.append(url)
                    self.url = url

            context = SimpleNamespace(
                browser=SimpleNamespace(new_browser_cdp_session=lambda cdp=cdp: cdp),
                service_workers=[],
                new_cdp_session=lambda p, cdp=cdp: cdp,
                new_page=lambda: Page(),
            )
            page = SimpleNamespace(url="about:blank", context=context)
            result = observe_sources(
                page,
                enabled,
                EXTENSION,
                EXT_HASHES,
                Path(
                    SOURCE_PROFILE.as_posix().replace(
                        "baseline", "enabled" if enabled else "baseline"
                    )
                ),
            )
            self.assertEqual(result["target_permission"], "DENIED")
            self.assertIs(result["inventory_complete"], False)
            self.assertEqual(result["argv_status"], "UNKNOWN")
            self.assertTrue(
                all(
                    u == "chrome://extensions/" or u == f"chrome-extension://{EXT_ID}/audit.html"
                    for u in visited
                )
            )

    def test_native_clock_observation_is_not_mapping(self):
        sample = {
            "epoch_ms": 1700000000000,
            "performance_ms": 1.5,
            "time_origin_ms": 1699999999998.5,
        }
        value = observed_clock(lambda: sample, "SYNTHETIC")
        self.assertEqual(value["mapping"], "UNKNOWN")
        self.assertEqual(len(value["samples"]), 2)
        for edit in (
            {"epoch_ms": True},
            {"performance_ms": float("nan")},
            {"time_origin_ms": float("inf")},
        ):
            with self.assertRaises(Unknown):
                observed_clock(lambda edit=edit: {**sample, **edit}, "SYNTHETIC")

    def test_source_parent_requires_natural_exit_logs_cleanup_and_no_retry(self):
        parent, api, _, create = supervisor_model()
        contract = {"create": create, "phase": "baseline", "parent_session": SESSION}
        observation = {
            "schema_version": "r3-source-observation-v1",
            "status": "SOURCE_OBSERVED",
            "session": SESSION,
            "phase": "baseline",
            "target_permission": "DENIED",
            "close_confirmed": True,
            "fetch_returned": False,
            "facts": {"target_permission": "DENIED"},
        }
        original = api.call
        api.call = lambda args, timeout: (
            json.dumps(observation).encode() if args[1] == "logs" else original(args, timeout)
        )
        with patch.object(parent, "verify_source_container"):
            result = parent.run(create, source_contract=contract)
        self.assertEqual(result["status"], "SOURCE_OBSERVED")
        self.assertEqual(result["cleanup"], "OWNED_CONTAINER_REMOVED")
        with self.assertRaises(Unknown):
            parent.run(create, source_contract=contract)
        for failure in ("close", "cleanup", "wait", "deadline"):
            parent, api, _, create = supervisor_model()
            value = {**observation, "close_confirmed": failure != "close"}
            api.residual = failure == "cleanup"
            api.wait_fail = failure == "wait"
            api.on_start = parent.timeout if failure == "deadline" else None
            original = api.call
            api.call = lambda args, timeout, value=value, original=original: (
                json.dumps(value).encode() if args[1] == "logs" else original(args, timeout)
            )
            with patch.object(parent, "verify_source_container"):
                self.assertEqual(
                    parent.run(create, source_contract={**contract, "create": create})["status"],
                    "BLOCKED",
                )

    def test_end_to_end_host_binding_and_real_parent_flow_with_synthetic_daemon(self):
        root = HERE.absolute().parents[3]
        manifest = (HERE / "execution-inputs.json").read_bytes()
        plan = (HERE / "execution_plan.json").read_bytes()
        record = {
            "session": SESSION,
            "candidate_commit": "c" * 40,
            "image_id": "sha256:" + "f" * 64,
            "manifest_raw_sha256": hashlib.sha256(manifest).hexdigest(),
            "plan_raw_sha256": hashlib.sha256(plan).hexdigest(),
        }
        approval = HostApproval(HOST_RECORD, "a" * 64, "b" * 40, record)

        def git_objects(args, **kwargs):
            if args[1] == "rev-parse":
                return SimpleNamespace(stdout=record["candidate_commit"].encode())
            relative = args[2].split(":", 1)[1]
            return SimpleNamespace(stdout=(root / relative).read_bytes())

        for failure in (
            None,
            "network",
            "writable_mount",
            "create_interrupted",
            "close",
            "cleanup",
            "foreign",
        ):
            daemon = SyntheticSourceDocker(failure)
            timers = []

            def arm(seconds, callback, timers=timers):
                timer = Timer(seconds, callback)
                timers.append(timer)
                return timer

            with (
                patch.object(HostApproval, "read_approved_record", return_value=record),
                patch("supervisor.subprocess.run", side_effect=git_objects),
                patch("supervisor.DockerCommands", return_value=daemon),
                patch("supervisor.SOURCE_SESSIONS", set()),
                patch.object(ParentSupervisor, "timer", staticmethod(arm)),
            ):
                result = source_preflight(approval)
                self.assertEqual(
                    result["status"], "SOURCE_OBSERVED" if failure is None else "BLOCKED"
                )
                self.assertEqual(result["target_permission"], "DENIED")
                self.assertTrue(all(t.seconds == 120 for t in timers))
                self.assertEqual(
                    daemon.start_phases,
                    ["baseline", "enabled"]
                    if failure is None
                    else (["baseline"] if failure in {"close", "cleanup"} else []),
                )
                if failure not in {"cleanup", "foreign"}:
                    self.assertEqual(daemon.objects, {})
                if failure == "foreign":
                    self.assertFalse(any(c[1] in {"kill", "rm"} for c in daemon.calls))
                with self.assertRaisesRegex(Unknown, "already_consumed"):
                    source_preflight(approval)
        # Both digests are checked before parsing/calling ANY Docker API.
        for key in ("manifest_raw_sha256", "plan_raw_sha256"):
            with (
                patch.object(
                    HostApproval, "read_approved_record", return_value={**record, key: "0" * 64}
                ),
                patch("supervisor.DockerCommands") as commands,
                self.assertRaises(Unknown),
            ):
                source_preflight(approval)
            commands.assert_not_called()


class RuntimeTests(unittest.TestCase):
    def test_actual_invocation_never_imports_driver_without_admission(self):
        with self.assertRaisesRegex(Unknown.__bases__[0], "not_authorized"):
            invoke_dynamic_fetch(Path("unused"), None, None, enabled=True)

    def test_trusted_origin_id_manifest_and_target_prechecks(self):
        value, cdp = bound()
        self.assertEqual(value.readback(configure=True)["sequence"], 0)
        for edit in (
            lambda c: c.identity.update(id="b" * 32),
            lambda c: c.identity.update(origin="https://fixture.test"),
            lambda c: c.identity.update(manifest={}),
        ):
            value, cdp = collector()
            value.discover()
            edit(cdp)
            with self.assertRaises(Unknown):
                value.bind_audit_page(
                    SimpleNamespace(url=f"chrome-extension://{EXT_ID}/audit.html")
                )

    def test_wrong_page_missing_ambiguous_target_and_profile(self):
        value, cdp = collector()
        value.discover()
        with self.assertRaises(Unknown):
            value.bind_audit_page(SimpleNamespace(url="https://fixture.test/audit.html"))
        for targets in ([], [{"type": "page", "url": "https://fixture.test"}], cdp.targets * 2):
            value, cdp = collector()
            cdp.targets = targets
            with self.assertRaises(Unknown):
                value.discover()
        for key in ("exclusive_new_profile", "readonly_mount", "approved_extension_flags"):
            value, _ = collector()
            value.profile[key] = None
            with self.assertRaises(Unknown):
                value.discover()

    def test_inventory_and_clock_are_unknown_not_fake_proof(self):
        value, _ = bound()
        with self.assertRaisesRegex(Unknown, "inventory_source_unreviewed"):
            value.require_target_permission(ClockEvidence([]))
        anchor = {"before_monotonic_ms": 0, "browser_epoch_ms": 1000, "after_monotonic_ms": 1}
        with self.assertRaisesRegex(Unknown, "mapping_unreviewed"):
            ClockEvidence([anchor]).require_mapping()
        for key in anchor:
            for bad in (float("nan"), float("inf"), -float("inf"), True, "1", None, 10**400):
                row = {**anchor, key: bad}
                with self.assertRaises(Unknown):
                    ClockEvidence([row]).require_mapping()
        with self.assertRaises(Unknown):
            ClockEvidence([{**anchor, "after_monotonic_ms": -1}]).require_mapping()

    def test_readback_rule_epoch_flush_and_connection_loss(self):
        for key, bad in (
            ("flushed", False),
            ("enabled_rulesets", []),
            ("dynamic_rules", [{}]),
            ("session_rules", [{}]),
            ("fatal", "overflow"),
            ("sequence", 101),
            ("observer_registered", False),
            ("ok", False),
        ):
            value, cdp = bound()
            cdp.state[key] = bad
            with self.assertRaises(Unknown):
                value.readback()
        value, cdp = bound()
        value.readback()
        cdp.state["observer_epoch"] = "changed"
        with self.assertRaises(Unknown):
            value.readback()
        value, cdp = bound()
        cdp.fail = True
        with self.assertRaisesRegex(Unknown, "transport_unknown"):
            value.readback()

    def test_evaluate_rejects_unknown_response_structures(self):
        for raw in (
            None,
            [],
            {},
            {"result": None},
            {"result": {"type": "string"}},
            {"result": {"type": "object", "value": []}},
        ):
            with self.assertRaises(Unknown):
                evaluate(SimpleNamespace(send=lambda *args, raw=raw: raw), "ignored")

    def test_receipt_loss_duplicate_and_strict_time_are_refused(self):
        row = receipt()
        for edit in (
            lambda r: r.update(timestamp=float("nan")),
            lambda r: r.update(sequence=True),
            lambda r: r.update(action="allow"),
        ):
            value, cdp = bound()
            invalid = copy.deepcopy(row)
            edit(invalid)
            cdp.state.update(receipts=[invalid], sequence=1)
            with self.assertRaises(Unknown):
                value.readback()
        value, cdp = bound()
        cdp.state.update(receipts=[row], sequence=1)
        value.readback()
        cdp.state.update(receipts=[], sequence=0)
        with self.assertRaises(Unknown):
            value.readback()

    def test_receipt_exact_schema_and_metadata(self):
        for actor in ("page", "worker"):
            for scheme in ("ws", "wss"):
                value, cdp = bound()
                row = receipt()
                row.update(
                    safe_request_fingerprint=fingerprint(actor, scheme),
                    tab_id=-1,
                    frame_id=0,
                    document_id="SYNTHETIC-document",
                )
                cdp.state.update(receipts=[row], sequence=1)
                self.assertEqual(value.readback()["receipts"], [row])
        bad_rows = []
        for key in receipt():
            row = receipt()
            del row[key]
            bad_rows.append(row)
        for key, bad in (
            ("url", "SYNTHETIC_SECRET"),
            ("token", "SYNTHETIC_SECRET"),
            ("rule_id", True),
            ("rule_id", 1.0),
            ("safe_request_fingerprint", "0" * 64),
            ("safe_request_fingerprint", fingerprint("page", "ws").upper()),
            ("tab_id", True),
            ("tab_id", 1.0),
            ("frame_id", "1"),
            ("document_id", 1),
            ("initiator", "SYNTHETIC_SECRET"),
            ("initiator_note", "SYNTHETIC_SECRET"),
        ):
            bad_rows.append({**receipt(), key: bad})
        for row in bad_rows:
            with self.subTest(row=row):
                value, cdp = bound()
                cdp.state.update(receipts=[row], sequence=1)
                with self.assertRaisesRegex(Unknown, "audit_receipt_invalid"):
                    value.readback()

    def test_cumulative_receipts_cannot_be_rewritten_or_alias_return(self):
        for key, changed in (
            ("timestamp", 1700000000001),
            ("tab_id", 1),
            ("safe_request_fingerprint", fingerprint("worker", "ws")),
            ("document_id", "changed"),
        ):
            value, cdp = bound()
            cdp.state.update(receipts=[receipt()], sequence=1)
            returned = value.readback()
            returned["receipts"][0][key] = changed
            cdp.state["receipts"][0][key] = changed
            with self.assertRaisesRegex(Unknown, "audit_receipt_rewritten"):
                value.readback()
        value, cdp = bound()
        cdp.state.update(receipts=[receipt()], sequence=1)
        value.readback()
        cdp.state["receipts"].append({**receipt(), "sequence": 2, "request_id": "dnr-2"})
        cdp.state["sequence"] = 2
        self.assertEqual(value.readback()["sequence"], 2)

    def test_pipe_partial_then_reader_error_is_latched_safe_failure(self):
        class BrokenPipe:
            def __init__(self):
                self.first = True
                self.closed = False

            def read1(self, size):
                self.assert_size = size
                if self.first:
                    self.first = False
                    return b"SYNTHETIC_PARTIAL_SECRET"
                raise OSError("SYNTHETIC_EXCEPTION_SECRET")

            def close(self):
                self.closed = True

        class Process:
            def __init__(self):
                self.stdout, self.returncode = BrokenPipe(), 0
                self.killed, self.waits = False, []

            def wait(self, timeout):
                self.waits.append(timeout)
                return 0

            def kill(self):
                self.killed = True

        process = Process()
        api = DockerCommands(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")
        with (
            patch("subprocess.Popen", return_value=process),
            patch("threading.excepthook") as thread_errors,
        ):
            with self.assertRaisesRegex(Unknown, "^docker_command_failed_or_unbounded$") as caught:
                api.call(["container", "wait", "a" * 64], 1)
        thread_errors.assert_not_called()
        self.assertNotIn("SECRET", str(caught.exception))
        self.assertIsNone(caught.exception.__context__)
        self.assertTrue(process.killed)
        self.assertTrue(process.stdout.closed)
        self.assertEqual(process.stdout.assert_size, 4096)
        self.assertTrue(all(0 < wait <= 2 for wait in process.waits))

    def test_bounded_docker_pipe_with_fake_process_only(self):
        class Process:
            def __init__(self, data):
                self.stdout, self.returncode = io.BytesIO(data), 0

            def wait(self, timeout):
                return self.returncode

            def kill(self):
                self.returncode = -9

        api = DockerCommands(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")
        with patch("subprocess.Popen", return_value=Process(b"0\n")):
            self.assertEqual(api.call(["container", "wait", "a" * 64], 1), b"0\n")
        with (
            patch("subprocess.Popen", return_value=Process(b"x" * (1024 * 1024 + 1))),
            self.assertRaises(Unknown),
        ):
            api.call(["container", "wait", "a" * 64], 1)

    def test_actual_close_adapter_requires_all_confirmation_signals(self):
        self.assertTrue(close_confirmed(page_double()))
        for kwargs in ({"connected": True}, {"closed": False}, {"event": False}, {"fail": True}):
            with self.assertRaisesRegex(Unknown, "close_confirmation_unknown"):
                close_confirmed(page_double(**kwargs))

    def test_guarded_precheck_failure_close_and_terminal_never_goto(self):
        guard, timers, kills = fake_guard()
        guard.start()
        value, _ = collector()
        page = page_double()
        page.context.new_page = lambda: (_ for _ in ()).throw(RuntimeError("synthetic"))
        with self.assertRaises(Terminal):
            guarded_setup(guard, value, page, ClockEvidence([]))
        self.assertTrue(guard.denied)
        self.assertTrue(guard.closed)
        self.assertEqual(kills, [True])
        self.assertEqual([t.seconds for t in timers], [120, 15, 5])

    def test_child_timer_precedes_injected_fetch(self):
        guard, timers, _ = fake_guard()

        def fetch(**kwargs):
            self.assertEqual(timers[0].seconds, 120)
            self.assertEqual(kwargs["retries"], 1)
            return "SYNTHETIC"

        self.assertEqual(fetch_once(guard, fetch, None, None), "SYNTHETIC")
        with self.assertRaisesRegex(Unknown.__bases__[0], "retry_forbidden"):
            fetch_once(guard, fetch, None, None)

    def test_plain_ws_method_host_port_fingerprint_deny_only(self):
        event = denied_request(ws_request(), "baseline")
        self.assertEqual(
            (event["method"], event["host"], event["port"], event["status"]),
            ("GET", "websocket-r3.test", 8443, 405),
        )
        self.assertEqual(event["upstream_bytes"], 0)
        self.assertEqual(event["relay_bytes"], 0)
        self.assertEqual(
            event["fingerprint"],
            hashlib.sha256(b"ws://websocket-r3.test:8443/dnr-page-ws").hexdigest(),
        )

    def test_plain_ws_malformed_authority_headers_path_phase_are_not_correlated(self):
        cases = [
            ws_request("/dnr-page-ws?"),
            ws_request("/dnr-page-ws#"),
            ws_request().replace(b"http://", b"http://@"),
            ws_request().replace(b"http://", b"http://:@"),
            ws_request().replace(b"websocket-r3.test:8443/dnr", b"WEBSOCKET-R3.test:8443/dnr"),
            ws_request().replace(b":8443/dnr", b":08443/dnr"),
            ws_request().replace(b"/dnr-page", b"/dnr-\tpage"),
            ws_request().replace(b"http://", b"http://\x00"),
            ws_request().replace(b"http://", b"http://\r"),
            ws_request().replace(b"http://", b"http://\n"),
            ws_request().replace(b"/dnr-page", b"/dnr-\x7fpage"),
            ws_request("/dnr-page-ws?SYNTHETIC_SECRET=1"),
            ws_request("/wrong"),
            ws_request(headers=b"Host: evil.test\r\n"),
            ws_request(headers=b" Folded: x\r\n"),
            ws_request().replace(b"http://", b"http://user:secret@"),
            ws_request().replace(b":8443/dnr", b":999999/dnr"),
            ws_request().replace(b"websocket-r3.test:8443\r\n", b"evil.test:8443\r\n"),
            b"x" * 16385,
            ws_request().replace(b"GET ", b"POST "),
        ]
        for raw in cases:
            event = denied_request(raw, "enabled")
            self.assertIsNone(event["fingerprint"])
            self.assertEqual(event["decision"], "deny")
            self.assertNotIn("SYNTHETIC_SECRET", json.dumps(event))
        with self.assertRaises(ValueError):
            denied_request(ws_request(), "fixture_claimed_phase")

    def test_proxy_handler_does_not_delegate_or_connect_for_ws(self):
        class Base:
            def handle(self):
                raise AssertionError("must not delegate denied WS")

        accepted = SimpleNamespace(TARGET_ANSWERS={}, ProxyHandler=Base)
        audit = []
        handler = handler_type(accepted, audit.append, "baseline")
        for raw, status in (
            (ws_request(), b"405"),
            (ws_request("/dnr-page-ws?"), b"405"),
            (ws_request("/dnr-page-ws#"), b"405"),
            (ws_request().replace(b"http://", b"http://@"), b"405"),
            (ws_request().replace(b"/dnr-page", b"/dnr-\tpage"), b"405"),
            (b"CONNECT websocket-r3.test:8443 HTTP/1.1\r\n\r\n", b"403"),
        ):
            instance = object.__new__(handler)
            instance.request = SimpleNamespace(settimeout=lambda seconds: None)
            instance.rfile, instance.wfile = io.BytesIO(raw), io.BytesIO()
            with patch("socket.create_connection", side_effect=AssertionError("no socket allowed")):
                instance.handle()
            self.assertIn(status, instance.wfile.getvalue())
            self.assertIn(b"Connection: close", instance.wfile.getvalue())
            self.assertEqual(audit[-1]["upstream_bytes"], 0)
            self.assertEqual(audit[-1]["relay_bytes"], 0)

    def test_bounded_headers_and_connect_ambiguity(self):
        self.assertEqual(read_headers(io.BytesIO(b"x" * 4097)), b"")
        self.assertTrue(valid_connect(b"CONNECT navigation-r3.test:8443 HTTP/1.1\r\n\r\n"))
        self.assertFalse(
            valid_connect(b"CONNECT navigation-r3.test:8443 HTTP/1.1\r\nHost: evil\r\n\r\n")
        )
        self.assertFalse(
            valid_connect(b"CONNECT navigation-r3.test:8443 HTTP/1.1\r\nHost: x\r\nHost: x\r\n\r\n")
        )

    def test_fixture_native_http_worker_and_no_websocket_acceptance(self):
        self.assertIn("new WebSocket", PAGE)
        self.assertIn("new WebSocket", WORKER)
        self.assertIn("new Worker('/dnr-worker.js')", PAGE)
        self.assertNotIn("Blob", PAGE)
        self.assertNotIn("globalThis.WebSocket", WORKER)
        self.assertEqual(response("/dnr-worker.js")[0], 200)
        self.assertEqual(response("/anything", True)[0], 403)

    def test_parent_arms_before_create_natural_exit_not_r3_pass(self):
        parent, _api, timers, create = supervisor_model()
        result = parent.run(create)
        self.assertTrue(result["natural_exit"])
        self.assertEqual(result["status"], "NO_GO")
        self.assertFalse(result["runtime_verified"])
        self.assertEqual(result["cleanup"], "ABSENT_IN_INJECTED_DAEMON_VIEW")
        self.assertTrue(timers[0].cancelled)
        with self.assertRaises(Unknown):
            parent.run(create)

    def test_parent_foreign_owner_residual_wait_failure_timeout(self):
        for failure in ("foreign", "residual", "wait_fail", "timeout"):
            parent, api, timers, create = supervisor_model()
            if failure == "timeout":
                api.on_start = lambda timers=timers: timers[0].callback()
            else:
                setattr(api, failure, True)
            result = parent.run(create)
            self.assertEqual(result["status"], "NO_GO")
            if failure in {"foreign", "residual"}:
                self.assertEqual(result["cleanup"], "UNKNOWN")
            if failure == "foreign":
                self.assertFalse(any(call[1] in {"start", "kill", "rm"} for call in api.calls))

    def test_unfrozen_real_docker_entry_rejects_without_call(self):
        api = DockerCommands(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")
        parent = ParentSupervisor(api, SESSION)
        with (
            patch("subprocess.Popen", side_effect=AssertionError("not authorized")),
            self.assertRaises(Unknown),
        ):
            parent.run([])

    def test_input_hash_and_unreviewable_origin_reject(self):
        row = {
            "path": "test_runtime_adapters.py",
            "sha256": hashlib.sha256((HERE / "test_runtime_adapters.py").read_bytes()).hexdigest(),
            "origin": "new_candidate",
        }
        check_inputs(HERE, [row])
        for change in (
            {"sha256": "0" * 64},
            {"origin": "untracked_history"},
            {"path": "../escape.py"},
        ):
            with self.assertRaises(Unknown):
                check_inputs(HERE, [{**row, **change}])


if __name__ == "__main__":
    unittest.main()
