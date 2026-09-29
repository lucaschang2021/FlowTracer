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

from collector import ClockEvidence, Collector, Unknown, evaluate
from contract import FLAGS, MANIFEST, MOUNT, SESSION, fingerprint
from fixture import PAGE, WORKER, response
from harness import Guard, Terminal
from probe import close_confirmed, fetch_once, guarded_setup, invoke_dynamic_fetch
from proxy import denied_request, handler_type, read_headers, valid_connect
from supervisor import DockerCommands, ParentSupervisor, check_inputs

HERE = Path(__file__).parent
EXTENSION = HERE / "extension-v2"
EXT_HASHES = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in EXTENSION.iterdir()}
EXT_ID = "a" * 32


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
                        "State": {"Running": self.running},
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
