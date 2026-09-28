"""Offline doubles only, without Browser/Docker/HTTP or dependency installation."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from contract import MANIFEST, RULES, SESSION, Rejected, check_readback, check_static, fingerprint
from harness import Guard, Terminal, model_fetch_once
from validator import validate_model

HERE = Path(__file__).parent


def sample():
    # All identity/CDP/receipts below are deliberately SYNTHETIC test doubles.
    identity = dict.fromkeys(
        ("hashes_match", "readonly_mount", "unique_extension", "trusted_cdp"), True
    )
    identity["extension_id"] = "a" * 32
    snapshot = {
        "schema_version": "r3-dnr-audit-v1",
        "extension_id": "a" * 32,
        "session": SESSION,
        "ok": True,
        "configured": True,
        "fatal": None,
        "enabled_rulesets": ["ws_default_deny_v1"],
        "dynamic_rules": [],
        "session_rules": [],
        "observer_registered": True,
        "observer_epoch": "SYNTHETIC-epoch",
        "flushed": True,
        "storage_access_level": "TRUSTED_CONTEXTS",
        "sequence": 4,
        "receipts": [],
    }
    arms = []
    for actor in ("page", "worker"):
        for scheme in ("ws", "wss"):
            ordinal = len(arms) + 1
            snapshot["receipts"].append(
                {
                    "schema_version": "r3-dnr-receipt-v1",
                    "session": SESSION,
                    "extension_id": "a" * 32,
                    "ruleset_id": "ws_default_deny_v1",
                    "rule_id": 1,
                    "action": "block",
                    "resource_type": "websocket",
                    "request_id": f"dnr-{ordinal}",
                    "timestamp": 1000,
                    "sequence": ordinal,
                    "observer_epoch": "SYNTHETIC-epoch",
                    "safe_request_fingerprint": fingerprint(actor, scheme),
                    "tab_id": None,
                    "frame_id": None,
                    "document_id": None,
                    "initiator": None,
                    "initiator_note": "omitted_to_prevent_origin_secret_exposure",
                }
            )
            arms.append(
                {
                    "actor": actor,
                    "scheme": scheme,
                    "start_ms": 900,
                    "end_ms": 1100,
                    "terminal_ms": 1010,
                    "source": "native_constructor",
                    "receipt_source": "trusted_extension_cdp",
                    "terminal": "error",
                    "proxy_attempts": 0,
                    "fixture_ws_received": 0,
                    "relay_bytes": 0,
                    "navigation_alive": True,
                    "target_id": f"target-{ordinal}",
                    "cdp_session_id": f"session-{ordinal}",
                    "cdp_request_id": f"cdp-{ordinal}",
                    "http_script_alive": True,
                    "pong": True,
                    "terminated": True,
                }
            )
    baseline = {
        "ws_proxy_denied": True,
        "wss_proxy_denied": True,
        "dnr_receipts": 0,
        "independent_403": True,
        "upstream_bytes": 0,
        "relay_bytes": 0,
        "fixture_ws_received": 0,
    }
    return snapshot, identity, arms, baseline


class Timer:
    def __init__(self, seconds, callback):
        self.seconds, self.callback, self.cancelled = seconds, callback, False

    def cancel(self):
        self.cancelled = True


def guard_model():
    timers, kills = [], []

    def arm(seconds, callback):
        timer = Timer(seconds, callback)
        timers.append(timer)
        return timer

    return Guard(arm, lambda: kills.append("SYNTHETIC-kill"), lambda: 0), timers, kills


class OfflineTests(unittest.TestCase):
    def test_permissions_exceptions_and_rule_semantics_rejected(self):
        expected = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (HERE / "extension").iterdir()
        }
        for edit in (
            lambda m: m["permissions"].pop(),
            lambda m: m["permissions"].append("tabs"),
            lambda m: m.update(host_permissions=["<all_urls>"]),
        ):
            altered = copy.deepcopy(MANIFEST)
            edit(altered)
            with (
                patch("contract.json.loads", side_effect=[altered, RULES]),
                self.assertRaises(Rejected),
            ):
                check_static(HERE / "extension", expected)
        for edit in (
            lambda r: r[0]["action"].update(type="allow"),
            lambda r: r[0]["condition"].update(excludedInitiatorDomains=["fixture.test"]),
            lambda r: r.append(copy.deepcopy(r[0])),
        ):
            altered = copy.deepcopy(RULES)
            edit(altered)
            with (
                patch("contract.json.loads", side_effect=[MANIFEST, altered]),
                self.assertRaises(Rejected),
            ):
                check_static(HERE / "extension", expected)

    def test_exact_static_five_files(self):
        expected = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (HERE / "extension").iterdir()
        }
        check_static(HERE / "extension", expected)
        self.assertEqual(json.loads((HERE / "extension/manifest.json").read_text()), MANIFEST)
        self.assertEqual(json.loads((HERE / "extension/rules.json").read_text()), RULES)

    def test_hash_or_missing_file_rejected(self):
        expected = {p.name: "0" * 64 for p in (HERE / "extension").iterdir()}
        with self.assertRaisesRegex(Rejected, "hash_invalid"):
            check_static(HERE / "extension", expected)
        expected.pop("audit.js")
        with self.assertRaisesRegex(Rejected, "files_invalid"):
            check_static(HERE / "extension", expected)

    def test_positive_model_never_runtime_or_formal_pass(self):
        result = validate_model(*sample())
        self.assertEqual(result["r3_status"], "BLOCKED")
        self.assertFalse(result["runtime_verified"])
        self.assertFalse(result["formal_r3_gate"])

    def test_readback_failure_matrix(self):
        for key, value in [
            ("enabled_rulesets", []),
            ("dynamic_rules", [{}]),
            ("session_rules", [{}]),
            ("fatal", "epoch_changed"),
            ("flushed", False),
            ("observer_registered", False),
            ("extension_id", None),
            ("configured", False),
            ("storage_access_level", "TRUSTED_AND_UNTRUSTED_CONTEXTS"),
        ]:
            snapshot, identity, _, _ = sample()
            snapshot[key] = value
            with self.subTest(key=key), self.assertRaises(Rejected):
                check_readback(snapshot, identity)

    def test_identity_and_provenance_not_inferred(self):
        for key in (
            "hashes_match",
            "readonly_mount",
            "unique_extension",
            "trusted_cdp",
            "extension_id",
        ):
            snapshot, identity, _, _ = sample()
            identity[key] = None
            with self.subTest(key=key), self.assertRaises(Rejected):
                check_readback(snapshot, identity)

    def test_receipt_invalid_matrix(self):
        for key, value in [
            ("rule_id", 2),
            ("action", "allow"),
            ("ruleset_id", "other"),
            ("resource_type", "script"),
            ("observer_epoch", "restart"),
            ("extension_id", "b" * 32),
            ("safe_request_fingerprint", "foreign"),
            ("sequence", 2),
            ("timestamp", float("nan")),
            ("session", "other"),
        ]:
            values = sample()
            values[0]["receipts"][0][key] = value
            with self.subTest(key=key), self.assertRaises(Rejected):
                validate_model(*values)

    def test_secret_and_invented_native_connect_count_rejected(self):
        for field in ("url", "authorization", "native_connect_calls"):
            values = sample()
            values[0]["receipts"][0][field] = "must_not_be_accepted"
            with self.assertRaises(Rejected):
                validate_model(*values)

    def test_duplicate_loss_and_epoch(self):
        for mutation in (
            lambda s: s["receipts"].pop(),
            lambda s: s["receipts"].append(copy.deepcopy(s["receipts"][0])),
            lambda s: s["receipts"][1].update(request_id=s["receipts"][0]["request_id"]),
            lambda s: s.update(sequence=3),
        ):
            values = sample()
            mutation(values[0])
            with self.assertRaises(Rejected):
                validate_model(*values)

    def test_missing_ambiguous_and_out_of_window(self):
        for change in (
            lambda a: a.update(start_ms=2000),
            lambda a: a.update(actor="worker"),
            lambda a: a.update(end_ms=999),
        ):
            values = sample()
            change(values[2][0])
            with self.assertRaises(Rejected):
                validate_model(*values)

    def test_mock_ack_fixture_receipt_and_no_liveness_refused(self):
        for key, value in [
            ("source", "mock"),
            ("receipt_source", "fixture_console"),
            ("terminal", "ack"),
            ("proxy_attempts", 1),
            ("relay_bytes", 1),
            ("fixture_ws_received", 1),
            ("navigation_alive", False),
            ("cdp_request_id", None),
            ("terminal_ms", 6001),
        ]:
            values = sample()
            values[2][0][key] = value
            with self.subTest(key=key), self.assertRaises(Rejected):
                validate_model(*values)
        for key in ("http_script_alive", "pong", "terminated"):
            values = sample()
            values[2][2][key] = False
            with self.assertRaises(Rejected):
                validate_model(*values)

    def test_baseline_proxy_allow_relay_and_missing_403(self):
        for key, value in [
            ("ws_proxy_denied", False),
            ("wss_proxy_denied", False),
            ("dnr_receipts", 1),
            ("independent_403", False),
            ("upstream_bytes", 1),
            ("relay_bytes", 1),
            ("fixture_ws_received", 1),
        ]:
            values = sample()
            values[3][key] = value
            with self.subTest(key=key), self.assertRaises(Rejected):
                validate_model(*values)

    def test_supervision_precedes_injected_dynamic_launch(self):
        guard, timers, _ = guard_model()

        def fetch(setup, before, retries):
            self.assertEqual(timers[0].seconds, 120)
            self.assertEqual(retries, 1)
            setup()
            before()
            return "SYNTHETIC-result"

        snapshot, identity, _, _ = sample()
        model_fetch_once(guard, fetch, lambda: (snapshot, identity), lambda: True)
        self.assertTrue(guard.ready)
        self.assertEqual(timers[1].seconds, 15)

    def test_swallowed_exception_cannot_goto_on_rejection(self):
        for close in (lambda: True, lambda: False, lambda: None):
            guard, timers, kills = guard_model()
            goto = []

            def fetch(setup, before, retries, goto=goto):
                try:
                    setup()
                except Exception:
                    goto.append("swallowed")  # simulated Scrapling log, no secrets
                goto.append("UNSAFE")

            with self.assertRaises(Terminal):
                model_fetch_once(guard, fetch, lambda: ({}, {}), close)
            self.assertEqual(goto, [])
            self.assertTrue(guard.denied)
            self.assertEqual(kills, ["SYNTHETIC-kill"])
            self.assertEqual(timers[-1].seconds, 5)

    def test_close_exception_kills_without_fallthrough(self):
        guard, _, kills = guard_model()
        guard.start()

        def close():
            raise RuntimeError("secret_do_not_export")

        with self.assertRaisesRegex(Terminal, "probe_terminated"):
            guard.setup(lambda: ({}, {}), close)
        self.assertEqual(len(kills), 1)

    def test_hanging_close_preflight_total_deadline_are_terminal(self):
        for budget in (120, 15, 5):
            guard, timers, kills = guard_model()
            guard.start()

            def inspect(budget=budget, timers=timers):
                if budget == 5:
                    return {}, {}
                return timers[-1 if budget == 15 else 0].callback()

            def close(budget=budget, timers=timers):
                if budget == 5:
                    return timers[-1].callback()  # simulated close hang
                return True

            with self.subTest(budget=budget), self.assertRaises(Terminal):
                guard.setup(inspect, close)
            self.assertTrue(kills)

    def test_unarmed_retry_and_lost_readiness_refused(self):
        guard, _, _ = guard_model()
        with self.assertRaises(Terminal):
            guard.before_target()
        guard, _, _ = guard_model()
        guard.start()
        with self.assertRaisesRegex(Rejected, "retry_forbidden"):
            guard.start()

    def test_node_observer_offline_vm(self):
        result = subprocess.run(  # noqa: S603 - fixed local Node VM, no Browser/network
            [r"C:\Program Files\nodejs\node.exe", str(HERE / "test_observer.js")],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        self.assertEqual(
            json.loads(result.stdout), {"offline_vm_tests": 11, "chrome_verified": False}
        )


if __name__ == "__main__":
    unittest.main()
