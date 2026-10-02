"""All receipts in this suite are SYNTHETIC, never runtime authority."""

from __future__ import annotations

import ast
import copy
import hashlib
import shutil
import subprocess
import sys
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from collector import Collector, join_network_receipts
from contract import FILES, MATRIX, Rejected, canonical, strict_json
from fixture import response
from harness import PolicyHooks, _execute_driver, synthetic_graph, wiring_plan
from supervisor import (
    CandidateBytes,
    Consumption,
    H1Host,
    HostPins,
    OwnedFacts,
    OwnedWatchdog,
    launch_real,
    remaining_timeout_ms,
    validate_host_input,
)
from validator import validate_real, validate_synthetic

ROOT = Path(__file__).resolve().parent


class CompositeTests(unittest.TestCase):
    def graph(self):
        return strict_json(synthetic_graph())

    def test_complete_synthetic_graph(self):
        self.assertEqual(validate_synthetic(synthetic_graph()), "SYNTHETIC_ACCEPTED_NOT_R3_PASS")
        self.assertEqual(len(self.graph()["triggers"]), len(MATRIX))

    def test_negative_graph_matrix(self):
        mutations = {
            "missing_trigger": lambda g: g["triggers"].pop(),
            "missing_decision": lambda g: g["decisions"].pop(),
            "missing_network": lambda g: g["observations"].pop(1),
            "duplicate_id": lambda g: g["triggers"].append(copy.deepcopy(g["triggers"][0])),
            "wrong_driver": lambda g: g["binding"].update(driver="Playwright"),
            "wrong_source": lambda g: g["binding"].update(source="page_signed"),
            "cross_execution": lambda g: g["decisions"][0].update(execution_id="another"),
            "cross_request": lambda g: g["observations"][0].update(request_id="another"),
            "wrong_actor": lambda g: g["triggers"][9].update(actor="page"),
            "timeout": lambda g: g["triggers"][0].update(result="timeout"),
            "forged_pass": lambda g: g.update(status="R3_PASS"),
            "unknown_field": lambda g: g["binding"].update(unrecognized="never-output"),
            "bad_hash": lambda g: g["binding"].update(input_sha="unknown"),
            "real_claim": lambda g: g.update(kind="REAL"),
            "proxy_backstop": lambda g: g["observations"][-1].update(result="proxy_denied"),
            "open_ws": lambda g: g["decisions"][8].update(action="allow"),
            "fake_child": lambda g: g["triggers"][-1].update(request_id="fake"),
            "wrong_parent": lambda g: g["triggers"][-1].update(parent_id="t-navigation"),
            "redirect_parent": lambda g: g["triggers"][2].update(parent_id="t-navigation"),
            "budget": lambda g: g["decisions"][0]["used"].update(requests=21),
            "negative_budget": lambda g: g["decisions"][0]["used"].update(bytes=-1),
            "bool_budget": lambda g: g["decisions"][0]["used"].update(bytes=True),
            "failed_scope": lambda g: g["decisions"][0]["checks"].update(scope="DENY"),
            "time_only": lambda g: g["observations"][0].update(decision_id="unknown"),
            "bad_order": lambda g: g["decisions"][0].update(seq=0),
            "duplicate_sequence": lambda g: g["decisions"][0].update(seq=3),
            "vendor_conflict": lambda g: g["observations"][4].update(
                transport_id="proxy-navigation"
            ),
            "no_cleanup": lambda g: g["completion"].update(cleanup="unknown"),
            "timeout_terminal": lambda g: g["completion"].update(duration_ms=15000),
            "incomplete_audit": lambda g: g["completion"].update(network_audit="partial"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                graph = self.graph()
                mutate(graph)
                with self.assertRaises(Rejected):
                    validate_synthetic(canonical(graph))

    def test_invalid_types_never_escape(self):
        for group in ("triggers", "decisions", "observations"):
            for field in self.graph()[group][0]:
                for value in ([], {}, None, True, 1.25):
                    graph = self.graph()
                    if graph[group][0][field] == value:
                        continue
                    graph[group][0][field] = value
                    with self.subTest(group=group, field=field, value=value):
                        with self.assertRaises(Rejected):
                            validate_synthetic(canonical(graph))

    def test_strict_json(self):
        for raw in (
            b'{"x":1,"x":2}',
            b'{"x":NaN}',
            b'{"x":Infinity}',
            b'{"x":-Infinity}',
            b'{"x":1e999}',
            b"[]",
            b"\xff",
            b"{" * 2000,
            b"x" * 262145,
        ):
            with self.subTest(raw_size=len(raw)):
                with self.assertRaises(Rejected):
                    strict_json(raw)

    def test_explicit_vendor_mapping_not_equal_ids(self):
        graph = self.graph()
        self.assertNotEqual(
            graph["observations"][1]["transport_id"], graph["triggers"][0]["request_id"]
        )
        self.assertEqual(validate_synthetic(canonical(graph)), "SYNTHETIC_ACCEPTED_NOT_R3_PASS")

    def test_denied_parent_no_fabricated_child(self):
        children = [
            t for t in self.graph()["triggers"] if t["result"] == "PREVENTED_BY_DENIED_PARENT"
        ]
        self.assertEqual({t["route"] for t in children}, {"sw-update", "sw-fetch"})
        self.assertTrue(all(t["request_id"] is None for t in children))

    def test_fixture_bytes(self):
        for route in MATRIX:
            status, body, content_type, target = response(route)
            self.assertLessEqual(len(body), 4096)
            self.assertIsInstance(content_type, str)
            self.assertEqual(
                status,
                302 if route == "redirect-start" else (200 if MATRIX[route][2] == "allow" else 403),
            )
            if target:
                self.assertEqual(target, "/redirect-end")
        self.assertEqual(response("https://example.com/secret")[0], 403)
        self.assertIn(b"new Worker", response("navigation")[1])

    def test_default_and_real_no_go(self):
        for function in (launch_real, validate_real):
            with self.assertRaisesRegex(Rejected, "NO_GO"):
                function({"authorized": True})
        self.assertEqual(wiring_plan()["status"], "NO_GO")
        for module in ("harness.py", "validator.py", "supervisor.py"):
            result = subprocess.run(  # noqa: S603 - fixed offline scripts, no driver imported
                [sys.executable, "-B", str(ROOT / module)],
                capture_output=True,
                timeout=5,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"NO_GO", result.stderr)

    def test_import_no_external_io(self):
        for module in ("contract", "fixture", "collector", "harness", "validator", "supervisor"):
            tree = ast.parse((ROOT / (module + ".py")).read_bytes())
            for node in tree.body:
                self.assertIsInstance(
                    node,
                    (
                        ast.Expr,
                        ast.Import,
                        ast.ImportFrom,
                        ast.FunctionDef,
                        ast.ClassDef,
                        ast.Assign,
                        ast.If,
                    ),
                )
                if isinstance(node, ast.Assign):
                    self.assertFalse(any(isinstance(n, ast.Call) for n in ast.walk(node.value)))
            imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
            self.assertFalse(
                any(
                    "playwright" in ast.unparse(n)
                    or "scrapling" in ast.unparse(n)
                    or "socket" in ast.unparse(n)
                    for n in imports
                )
            )

    def test_driver_hook_order_and_mapping(self):
        host = StubHost()
        result = _execute_driver(host, host.fetch)
        self.assertEqual(result["status"], "WIRING_RETURNED_NOT_R3_PASS")
        self.assertEqual(
            host.order[:6], ["runtime", "arm", "browser", "native", "route", "websocket"]
        )
        self.assertEqual(host.order[-2:], ["network", "cleanup"])
        records = {r["route"]: r for r in result["application_records"]}
        self.assertEqual(
            records["redirect-end"]["parent_id"], records["redirect-start"]["request_id"]
        )
        self.assertEqual(records["worker-ws"]["parent_id"], records["worker-script"]["request_id"])
        self.assertEqual(host.closed_socket, 1008)
        self.assertEqual(
            host.denied_routes, {"download", "page-ws", "worker-ws", "popup", "sw-register"}
        )
        self.assertEqual(host.forwarded, {k for k, v in MATRIX.items() if v[2] == "allow"})

    def test_driver_failures_never_pass(self):
        for failure in (
            "native",
            "network",
            "worker",
            "cleanup",
            "policy",
            "timeout",
            "missing_action",
        ):
            host = StubHost(failure)
            with self.subTest(failure=failure):
                with self.assertRaises(Rejected):
                    _execute_driver(host, host.fetch)
                self.assertIn("cleanup", host.order)

    def test_scope_budget_and_bad_redirect_abort(self):
        for url in (
            "https://example.com/x",
            "https://navigation-r3.test:8443/fetch?token=x",
            "https://user@navigation-r3.test:8443/fetch",
            "http://navigation-r3.test:8443/fetch",
            "https://navigation-r3.test:8443/../fetch",
        ):
            with self.assertRaises(Rejected):
                PolicyHooks(StubHost()).classify(url)
        for failure in ("budget", "redirect"):
            host = StubHost()
            hooks = PolicyHooks(host)
            hooks.setup(host.page)
            host.send("navigation")
            if failure == "budget":
                hooks.used["requests"] = 20
                target = "fetch"
            else:
                target = "redirect-end"
            request = (
                SimpleNamespace(
                    url="https://navigation-r3.test:8443/" + target,
                    headers={},
                    redirected_from=object(),
                )
                if failure == "redirect"
                else None
            )
            with self.assertRaises(Rejected):
                host.send(target, request=request)
            self.assertEqual(host.aborted[-1], target)


class StubHost:
    """SYNTHETIC only. Never passed through host_session or launch_real."""

    def __init__(self, failure=None):
        self.failure = failure
        self.order = []
        self.forwarded = set()
        self.denied_routes = set()
        self.ids = {}
        self.aborted = []
        self.now = 0
        self.closed_socket = None
        self.page = SimpleNamespace(
            context=self,
            set_default_timeout=lambda ms: None,
            evaluate=self.evaluate,
            locator=lambda selector: self,
            goto=self.goto,
        )

    def verify_runtime(self):
        self.order.append("runtime")

    def run_callback(self, callback):
        return callback()

    def verify_browser(self, page, timeout_ms):
        self.order.append("browser")
        if page is not self.page or not 0 < timeout_ms <= 5000:
            raise Rejected("synthetic_browser_mismatch")

    def execution_id(self):
        return "SYNTHETIC-driver-001"

    def clock_ns(self):
        return self.now

    def arm_parent_deadline(self, ms):
        self.order.append("arm")

    def install_native_denials(self, context, callback):
        self.order.append("native")
        if self.failure == "native":
            raise Rejected("native_observer_unknown")
        self.native = callback

    def route(self, pattern, callback):
        self.order.append("route")
        self.http = callback

    def route_web_socket(self, pattern, callback):
        self.order.append("websocket")
        self.ws = callback

    def check_target(self, url):
        if self.failure == "policy":
            raise Rejected("operator_denied")

    def request_id(self, request, route, parent):
        self.ids[route] = "actual-stub-" + route
        return self.ids[route]

    def bind_forwarding(self, request, request_id, expected_bytes):
        pass

    def application_denied(self, route, request_id):
        self.denied_routes.add(route)

    def attest_worker_attempt(self, page):
        self.order.append("worker-ready-attempt")
        if self.failure == "worker":
            raise Rejected("worker_attempt_unknown")

    def verify_native_matrix(self):
        pass

    def network_receipts(self, records):
        self.order.append("network")
        if self.failure == "network":
            raise Rejected("network_mapping_unknown")
        receipts = []
        for record in records["application_records"]:
            sources = (
                {"proxy": "forwarded", "fixture": "received"}
                if record["action"] == "allow"
                else {
                    "host-network": "application_prevented",
                }
            )
            for source, outcome in sources.items():
                receipts.append(
                    {
                        "request_id": record["request_id"],
                        "route": record["route"],
                        "parent_id": record["parent_id"],
                        "actor": MATRIX[record["route"]][1],
                        "source": source,
                        "transport_id": source + "-" + record["route"]
                        if record["action"] == "allow"
                        else None,
                        "outcome": outcome,
                        "body_bytes": len(response(record["route"])[1])
                        if record["action"] == "allow"
                        else 0,
                    }
                )
        return canonical(
            {"execution_id": self.execution_id(), "kind": "SYNTHETIC", "receipts": receipts}
        )

    def close_and_reap_owned(self):
        self.order.append("cleanup")
        if self.failure == "cleanup":
            raise Rejected("cleanup_unknown")

    def send(self, name, previous=None, request=None):
        req = request or SimpleNamespace(
            url="https://navigation-r3.test:8443/" + name, headers={}, redirected_from=previous
        )
        route = SimpleNamespace(
            abort=lambda code: self.aborted.append(name),
            continue_=lambda headers: self.forwarded.add(name),
        )
        self.http(route, req)
        return req

    def evaluate(self, script):
        if "xhr" in script:
            self.send("xhr")
        elif "fetch" in script:
            self.send("fetch")
        elif "workerWS" in script:
            self.send("worker-script")
            self.native("worker-ws", "native-worker-ws", self.ids["worker-script"])
        elif "pageWS" in script:
            self.ws(
                SimpleNamespace(
                    url="wss://navigation-r3.test:8443/page-ws",
                    close=lambda code, reason: setattr(self, "closed_socket", code),
                )
            )
        elif "popup" in script:
            self.native("popup", "native-popup", self.ids["navigation"])
        elif "register" in script:
            self.native("sw-register", "native-sw-register", self.ids["navigation"])

    def click(self, **kwargs):
        self.send("download")

    def goto(self, url, **kwargs):
        start = self.send("redirect-start")
        self.send("redirect-end", previous=start)

    def fetch(self, url, **options):
        if options["executable_path"] != "/opt/browser-r1c/chromium-1234/chrome-linux64/chrome":
            raise Rejected("wrong_driver_options")
        options["page_setup"](self.page)
        self.send("navigation")
        self.send("iframe")
        self.send("script")
        if self.failure == "timeout":
            self.now = 15000000000
        if self.failure != "missing_action":
            options["page_action"](self.page)


class ContractClosureTests(unittest.TestCase):
    def graph(self):
        return strict_json(synthetic_graph())

    def test_network_join_refuses_ambiguous_receipts(self):
        host = StubHost()
        records = _execute_driver(host, host.fetch)
        base = strict_json(host.network_receipts(records))
        for mutate in (
            lambda g: g.update(execution_id="other"),
            lambda g: g["receipts"].pop(),
            lambda g: g["receipts"][0].update(request_id="other"),
            lambda g: g["receipts"][0].update(body_bytes=5242880),
            lambda g: g["receipts"][-1].update(outcome="proxy_denied"),
            lambda g: g["receipts"].append(copy.deepcopy(g["receipts"][0])),
        ):
            graph = copy.deepcopy(base)
            mutate(graph)
            with self.assertRaises(Rejected):
                join_network_receipts(records, canonical(graph), host.execution_id())

    def test_budget_and_deadline(self):
        self.assertEqual(remaining_timeout_ms(0, 0), 5000)
        self.assertEqual(remaining_timeout_ms(0, 13999000000), 1)
        for args in ((0, 14000000000), (1, 0), (True, 0), (0, 0, 0)):
            with self.assertRaises(Rejected):
                remaining_timeout_ms(*args)
        graph = self.graph()
        graph["decisions"][0]["used"]["bytes"] = 5242880
        validate_synthetic(canonical(graph))
        graph["decisions"][1]["used"]["bytes"] = 1
        with self.assertRaises(Rejected):
            validate_synthetic(canonical(graph))

    def test_collector_copy_and_cap(self):
        binding = self.graph()["binding"]
        collector = Collector(binding, "SYNTHETIC")
        binding["driver"] = "changed"
        record = {"id": "unchanged"}
        collector.append("triggers", record)
        record["id"] = "changed"
        result = strict_json(collector.finish({}))
        self.assertEqual(result["binding"]["driver"], "DynamicFetcher.fetch")
        self.assertEqual(result["triggers"][0]["id"], "unchanged")
        with self.assertRaises(Rejected):
            collector.append("secret", {})
        for _ in range(99):
            collector.append("triggers", {})
        with self.assertRaises(Rejected):
            collector.append("triggers", {})

    def test_manifest_raw_git_blob_closure(self):
        manifest = strict_json((ROOT / "execution-inputs.json").read_bytes())
        expected = set(FILES) - {"execution-inputs.json", "execution-plan.json"}
        self.assertEqual(set(manifest["files"]), expected)
        for name, entry in manifest["files"].items():
            raw = (ROOT / name).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["sha256"])
            blob = b"blob " + str(len(raw)).encode() + b"\x00" + raw
            self.assertEqual(
                hashlib.sha1(blob, usedforsecurity=False).hexdigest(), entry["git_blob"]
            )
        plan = strict_json((ROOT / "execution-plan.json").read_bytes())
        self.assertEqual(
            plan["input_sha256"],
            hashlib.sha256((ROOT / "execution-inputs.json").read_bytes()).hexdigest(),
        )
        self.assertEqual(plan["runtime_permission"], "NO_GO")
        git_exe = shutil.which("git")
        self.assertIsNotNone(git_exe)
        for path, entry in manifest["interface_refs"].items():
            raw = subprocess.check_output(  # noqa: S603 - fixed read-only Git object
                [git_exe, "show", entry["commit"] + ":" + path]
            )
            self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["sha256"])
            blob = b"blob " + str(len(raw)).encode() + b"\x00" + raw
            self.assertEqual(
                hashlib.sha1(blob, usedforsecurity=False).hexdigest(), entry["git_blob"]
            )


class H1Timer:
    """Synthetic timer scheduler: never a host runtime attestation."""

    def __init__(self, seconds, callback):
        self.seconds, self.callback = seconds, callback
        self.cancelled = False

    def start(self):
        pass

    def cancel(self):
        self.cancelled = True


class H1Executor:
    def __init__(self, pins, snapshot):
        self.pins, self.snapshot = pins, snapshot
        self.operations = []
        self.consumed = set()
        self.fault = None
        self.now = 0

    def candidate_bytes(self, candidate):
        self.operations.append("snapshot")
        return self.snapshot

    def consume_once(self, execution, record_hash, purpose):
        self.operations.append("consume")
        if execution in self.consumed:
            return None
        self.consumed.add(execution)
        return Consumption(execution, record_hash, purpose)

    def inspect_owned(self, container_id, timeout_ms):
        self.operations.append("inspect")
        if self.fault == "owner":
            return OwnedFacts(container_id, "foreign", "foreign", "f" * 64)
        return OwnedFacts(
            container_id, self.pins.container_name, self.pins.session, self.pins.image_sha256
        )

    def operation(self, name, container_id, timeout_ms):
        if container_id != self.pins.container_id or not 0 < timeout_ms <= 5000:
            raise Rejected("synthetic_bad_target_or_timeout")
        self.operations.append(name)
        if self.fault == name:
            raise Rejected("synthetic_operation_failure")
        if self.fault == "late":
            self.now += 6_000_000_000

    def kill(self, container_id, timeout_ms):
        self.operation("kill", container_id, timeout_ms)

    def wait(self, container_id, timeout_ms):
        self.operation("wait", container_id, timeout_ms)
        return 137

    def remove(self, container_id, timeout_ms):
        self.operation("remove", container_id, timeout_ms)

    def absent(self, container_id, timeout_ms):
        self.operation("absent", container_id, timeout_ms)
        return True


class H1Tests(unittest.TestCase):
    def make(self):
        files = {name: (ROOT / name).read_bytes() for name in FILES}
        record = {
            "epoch": "GOV-2.1",
            "control": "a215051d2a2f53b41d9b22339f1bab52a27dbdf7",
            "candidate": "0" * 40,
            "inputs_sha256": hashlib.sha256(files["execution-inputs.json"]).hexdigest(),
            "plan_sha256": hashlib.sha256(files["execution-plan.json"]).hexdigest(),
            "image_sha256": "1" * 64,
            "container_id": "2" * 64,
            "container_name": "SYNTHETIC-owned",
            "session": "SYNTHETIC-session",
            "execution": "SYNTHETIC-driver-001",
            "purpose": "r3-composite-h1",
            "r1e_payload_sha256": (
                "5f4cf5acdf06a86f9b8907375f6f8f239ecf18152762b889f1e254b01e447e3b"
            ),
            "r1e_manifest_sha256": (
                "f8d8bd0b64dfac53e244b00f29fbc9f18ed44b94491323b3f49ba2af191912e8"
            ),
            "r1e": "R1E-PR66",
            "r2c": "R2C-A4-PR68",
        }
        raw = canonical(record)
        pins = HostPins(
            hashlib.sha256(raw).hexdigest(),
            record["candidate"],
            record["inputs_sha256"],
            record["plan_sha256"],
            record["image_sha256"],
            record["container_id"],
            record["container_name"],
            record["session"],
            record["execution"],
            "Chrome/SYNTHETIC",
            "/opt/browser-r1c/chromium-1234/chrome-linux64/chrome",
            "/tmp/r3-composite-profile",  # noqa: S108 - synthetic input only
        )
        executor = H1Executor(pins, CandidateBytes(pins.candidate, dict(files), dict(files)))
        native = StubHost()
        args = [pins.executable, "--user-data-dir=" + pins.profile, "--remote-debugging-pipe"]
        commands = []

        def send(command):
            commands.append(command)
            return (
                {"product": pins.browser_version}
                if command == "Browser.getVersion"
                else {"arguments": args}
            )

        cdp = SimpleNamespace(send=send, detach=lambda: commands.append("detach"))
        native.browser = SimpleNamespace(contexts=[native], new_browser_cdp_session=lambda: cdp)
        host = H1Host(pins, raw, executor, native, lambda: executor.now, H1Timer)
        return host, executor, native, record, args, commands

    def test_record_and_candidate_closure(self):
        host, executor, _, record, _, _ = self.make()
        validate_host_input(host.record, host.pins, executor.snapshot)
        for key, value in (
            ("purpose", "source-preflight"),
            ("purpose", "baseline-enabled"),
            ("session", "foreign"),
            ("image_sha256", "3" * 64),
            ("r1e", "foreign"),
            ("authorized", True),
        ):
            bad = canonical({**record, key: value})
            with self.subTest(key=key, value=value), self.assertRaises(Rejected):
                validate_host_input(
                    bad,
                    replace(host.pins, record_sha256=hashlib.sha256(bad).hexdigest()),
                    executor.snapshot,
                )
        with self.assertRaises(Rejected):
            validate_host_input(host.record + b" ", host.pins, executor.snapshot)
        bad_files = dict(executor.snapshot.raw_files)
        bad_files["harness.py"] += b"# drift"
        with self.assertRaises(Rejected):
            validate_host_input(
                host.record, host.pins, replace(executor.snapshot, raw_files=bad_files)
            )
        with self.assertRaises(Rejected):
            validate_host_input(host.record, True, executor.snapshot)
        with self.assertRaises(Rejected):
            validate_host_input(
                host.record, host.pins, replace(executor.snapshot, candidate="f" * 40)
            )
        both_bad = dict(bad_files)
        with self.assertRaises(Rejected):
            validate_host_input(
                host.record,
                host.pins,
                replace(executor.snapshot, git_files=both_bad, raw_files=both_bad),
            )

    def test_two_stage_driver_and_replay(self):
        host, executor, native, _, _, commands = self.make()
        result = _execute_driver(host, native.fetch)
        self.assertEqual(result["status"], "WIRING_RETURNED_NOT_R3_PASS")
        self.assertEqual(host.stage, 2)
        self.assertEqual(
            commands, ["Browser.getVersion", "Browser.getBrowserCommandLine", "detach"]
        )
        self.assertEqual(executor.operations[:3], ["snapshot", "inspect", "consume"])
        self.assertEqual(
            executor.operations[-6:], ["inspect", "kill", "wait", "inspect", "remove", "absent"]
        )
        replay = H1Host(host.pins, host.record, executor, native, lambda: executor.now, H1Timer)
        with self.assertRaises(Rejected):
            _execute_driver(replay, native.fetch)

    def test_browser_order_identity_and_thread(self):
        for fault in ("order", "profile", "port", "context", "thread"):
            host, _, native, _, args, commands = self.make()
            if fault != "order":
                host.verify_runtime()
            if fault == "profile":
                args[1] = "--user-data-dir=/foreign"
            if fault == "port":
                args.append("--remote-debugging-port=1")
            if fault == "context":
                native.browser.contexts = []
            if fault == "thread":
                host.driver_thread = -1
            with self.subTest(fault=fault), self.assertRaises(Rejected):
                host.verify_browser(native.page, 5000)
            if fault in {"order", "context", "thread"}:
                self.assertEqual(commands, [])
            host.close_and_reap_owned()

    def test_owned_cleanup_failures_and_deadlines(self):
        self.assertIsInstance(self.make()[0].watchdog, OwnedWatchdog)
        for fault in ("owner", "kill", "wait", "remove", "absent", "late"):
            host, executor, _, _, _, _ = self.make()
            executor.fault = fault
            if fault == "late":
                executor.now = 119_000_000_000
            with self.subTest(fault=fault), self.assertRaises(Rejected):
                host.close_and_reap_owned()
            if fault == "owner":
                self.assertEqual(executor.operations, ["inspect"])
        host, executor, _, _, _, _ = self.make()
        host.watchdog.arm()
        self.assertEqual(host.watchdog.timer.seconds, 15)
        with self.assertRaises(Rejected):
            host.watchdog.arm()
        executor.now = 15_000_000_000
        host.watchdog.timer.callback()
        host.close_and_reap_owned()
        self.assertEqual(executor.operations.count("remove"), 1)

    def test_callback_remaining_budget_and_no_extension(self):
        host, executor, _, _, _, _ = self.make()
        executor.now = 10_000_000_000
        self.assertEqual(remaining_timeout_ms(host.watchdog.started, executor.now), 4000)

        def late_read():
            executor.now += 4_000_000_000

        with self.assertRaises(Rejected):
            host.run_callback(late_read)
        host.close_and_reap_owned()
        self.assertEqual(host.watchdog.parent_end, 120_000_000_000)

    def test_independent_watchdog_never_calls_driver(self):
        host, executor, native, _, _, commands = self.make()
        host.watchdog.arm()
        thread = threading.Thread(target=host.watchdog.timer.callback)
        thread.start()
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(commands, [])
        self.assertEqual(native.order, [])
        self.assertEqual(executor.operations[-1], "absent")
        with self.assertRaises(Rejected):
            host.run_callback(lambda: self.fail("callback must not execute after reap"))

    def test_failed_host_input_still_reaps_and_real_stays_closed(self):
        host, executor, native, _, _, _ = self.make()
        host.record += b" "
        with self.assertRaises(Rejected):
            _execute_driver(host, lambda *a, **kw: self.fail("fetch must not start"))
        self.assertIn("absent", executor.operations)
        with self.assertRaises(Rejected):
            launch_real(authorized=True, host=host)
        with patch.dict("os.environ", {"R3_AUTHORIZED": "true"}), self.assertRaises(Rejected):
            launch_real()
        self.assertEqual(native.order, [])

    def test_host_owner_and_consumption_refusal_before_fetch(self):
        for fault in ("owner", "boolean", "old_purpose"):
            host, executor, _, _, _, _ = self.make()
            if fault == "owner":
                executor.fault = "owner"
            elif fault == "boolean":
                executor.consume_once = lambda *args: True
            else:
                executor.consume_once = lambda *args, host=host: Consumption(
                    host.pins.execution, host.pins.record_sha256, "baseline-enabled"
                )
            with self.subTest(fault=fault), self.assertRaises(Rejected):
                _execute_driver(host, lambda *a, **kw: self.fail("fetch must not start"))
            if fault == "owner":
                self.assertNotIn("kill", executor.operations)
                self.assertNotIn("remove", executor.operations)
            else:
                self.assertIn("absent", executor.operations)


if __name__ == "__main__":
    unittest.main()
