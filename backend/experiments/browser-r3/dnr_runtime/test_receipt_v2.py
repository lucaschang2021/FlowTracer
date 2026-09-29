"""Offline source-aware models, never Browser clock/inventory proof."""

import copy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from collector import ClockEvidence, Unknown
from contract_v2 import Rejected, fingerprint
from supervisor import actual_session_entry, phase_commands
from test_runtime_adapters import bound, receipt
from validator_v2 import validate_clock_samples, validate_observations


def matrix():
    rows, arms = [], []
    for ordinal, (actor, scheme) in enumerate(
        ((a, s) for a in ("page", "worker") for s in ("ws", "wss")), 1
    ):
        rows.append(
            {
                **receipt(),
                "request_id": f"synthetic-dnr-{ordinal}",
                "sequence": ordinal,
                "safe_request_fingerprint": fingerprint(actor, scheme),
            }
        )
        arms.append(
            {
                "actor": actor,
                "scheme": scheme,
                "start_ms": 1700000000000,
                "terminal_ms": 1700000000001,
                "end_ms": 1700000000002,
                "timestamp_source": "controlled_fixture_native_date_now_epoch_ms",
                "terminal": "error",
                "native_constructor": True,
                "navigation_alive": True,
                "proxy_attempts": 0,
                "fixture_ws_received": 0,
                "relay_bytes": 0,
                "http_script_alive": True,
                "pong": True,
                "terminated": True,
            }
        )
    return rows, arms


class ReceiptV2Tests(unittest.TestCase):
    def test_strict_four_observation_model_is_not_runtime_proof(self):
        rows, arms = matrix()
        result = validate_observations(rows, arms, "a" * 32, "SYNTHETIC-epoch")
        self.assertEqual(result["clock_equivalence"], "UNKNOWN")
        self.assertFalse(result["runtime_verified"])

    def test_source_types_late_callback_and_bad_order(self):
        for key, bad in (
            ("timestamp", 1700000000003),
            ("timestamp", 1700000000),
            ("timestamp", 1700000000000.0),
            ("timestamp", True),
            ("timestamp", float("nan")),
            ("timestamp_source", "fixture"),
            ("timestamp_source", None),
            ("schema_version", "r3-dnr-receipt-v1"),
            ("url", "SYNTHETIC_SECRET"),
        ):
            rows, arms = matrix()
            rows[0][key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(Rejected):
                validate_observations(rows, arms, "a" * 32, "SYNTHETIC-epoch")
        for key, bad in (
            ("terminal_ms", 1699999999999),
            ("end_ms", 1700000006000),
            ("timestamp_source", "fixture_message"),
            ("terminal", "timeout"),
        ):
            rows, arms = matrix()
            arms[0][key] = bad
            with self.assertRaises(Rejected):
                validate_observations(rows, arms, "a" * 32, "SYNTHETIC-epoch")

    def test_duplicate_missing_and_alias_are_rejected(self):
        rows, arms = matrix()
        for invalid in (rows[:-1], [rows[0]] * 4):
            with self.assertRaises(Rejected):
                validate_observations(invalid, arms, "a" * 32, "SYNTHETIC-epoch")
        value, cdp = bound()
        cdp.state.update(receipts=[receipt()], sequence=1)
        value.readback()["receipts"][0]["timestamp"] += 1
        value.readback()
        cdp.state["receipts"][0]["timestamp"] += 1
        with self.assertRaises(Unknown):
            value.readback()

    def test_clock_sources_domains_reject_instead_of_tolerance(self):
        samples = [
            {
                "source": "trusted_extension_native_date_now_epoch_ms",
                "epoch_ms": 1700000000000 + i,
                "host_before_ns": 10 + i * 10,
                "host_after_ns": 11 + i * 10,
            }
            for i in range(2)
        ]
        with self.assertRaisesRegex(Rejected, "cross_realm_equivalence_unknown"):
            validate_clock_samples(samples)
        for key, bad in (
            ("source", "fixture"),
            ("epoch_ms", 1700000000),
            ("epoch_ms", False),
            ("epoch_ms", 1699999999999),
            ("host_before_ns", 0.0),
            ("host_after_ns", 0),
        ):
            invalid = copy.deepcopy(samples)
            invalid[1][key] = bad
            with self.assertRaises(Rejected):
                validate_clock_samples(invalid)
        with self.assertRaises(Unknown):
            ClockEvidence(samples).require_mapping()

    def test_inventory_never_guesses_151_schema_or_hidden_filters(self):
        for origin in ("https://fixture.test", "chrome://settings/", "chrome://extensions/?x"):
            value, _ = bound()
            with self.assertRaisesRegex(Unknown, "origin_invalid"):
                value.read_inventory_candidate(SimpleNamespace(url=origin))
        for product in ("Chrome/145.0.7602.1", "Chrome/151.0.7922.34"):
            value, cdp = bound()
            original = cdp.send
            cdp.send = lambda method, args=None, product=product, original=original: (
                {"product": product} if method == "Browser.getVersion" else original(method, args)
            )
            cdp.state = {"ok": True, "entries": [{"token": "SYNTHETIC_SECRET"}]}
            with self.assertRaises(Unknown) as caught:
                value.read_inventory_candidate(SimpleNamespace(url="chrome://extensions/"))
            self.assertNotIn("SECRET", str(caught.exception))

    def test_exact_phase_argv_candidate_and_real_entry_remain_denied(self):
        mount = {
            "source": str(Path(__file__).resolve()),
            "target": "/opt/flowtracer-r3-runtime/probe.py",
            "sha256": "a" * 64,
            "readonly": True,
        }
        for phase in ("baseline", "enabled"):
            argv = phase_commands(
                "sha256:" + "b" * 64, "flowtracer-r3-dnr-synthetic", phase, [mount]
            )
            self.assertEqual(argv[:2], ["container", "create"])
            self.assertEqual(argv[-2:], ["--phase", phase])
            self.assertIn("--read-only", argv)
            self.assertIn("--cap-drop=ALL", argv)
            self.assertFalse(any("sysctl" in value or "privileged" in value for value in argv))
        for invalid in (
            {**mount, "readonly": False},
            {**mount, "source": "relative.py"},
            {**mount, "sha256": "bad"},
        ):
            with self.assertRaises(Unknown):
                phase_commands(
                    "sha256:" + "b" * 64, "flowtracer-r3-dnr-synthetic", "enabled", [invalid]
                )
        with patch("subprocess.Popen", side_effect=AssertionError("no real CLI")):
            with self.assertRaisesRegex(Unknown, "not_authorized"):
                actual_session_entry()


if __name__ == "__main__":
    unittest.main()
