"""Offline source-aware models, never Browser clock/inventory proof."""

import copy
import hashlib
import json
import stat
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from collector import ClockEvidence, Unknown
from contract_v2 import Rejected, check_snapshot, fingerprint
from harness import Terminal
from harness_v2 import Guard
from supervisor import actual_session_entry, checked_repo_file, phase_commands
from test_runtime_adapters import TEST_RAW_READ, bound, fake_guard, receipt, snapshot
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


def full_identity():
    return {
        "extension_id": "a" * 32,
        "trusted_cdp": True,
        "hashes_match": True,
        "readonly_mount": True,
        "unique_extension": True,
        "inventory_proven": True,
        "clock_equivalence_proven": True,
    }


def phase_mounts(phase):
    import hashlib

    here = Path(__file__).resolve().parent
    sources = {
        name: here / name
        for name in (
            "collector.py",
            "probe.py",
            "contract_v2.py",
            "validator_v2.py",
            "harness_v2.py",
        )
    }
    sources.update(
        {name: here.parent / "dnr_offline" / name for name in ("contract.py", "harness.py")}
    )
    mounts = [
        {
            "source": str(path),
            "target": "/opt/flowtracer-r3-runtime/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "readonly": True,
        }
        for name, path in sources.items()
    ]
    if phase == "enabled":
        mounts += [
            {
                "source": str(path),
                "target": "/opt/flowtracer-r3-dnr/" + path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "readonly": True,
            }
            for path in sorted((here / "extension-v2").iterdir())
        ]
    return mounts


def synthetic_render(image, session, phase, mounts):
    """TEST ONLY: independent SYNTHETIC approval captured before execution."""
    approved = hashlib.sha256(
        (Path(__file__).parent / "execution-inputs.json").read_bytes()
    ).hexdigest()

    def trusted_double(requested_session):
        if requested_session != session:
            raise Unknown("synthetic_session_mismatch")
        return approved

    with patch("supervisor.read_controller_manifest_digest", trusted_double):
        return phase_commands(image, session, phase, mounts)


class ReceiptV2Tests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(Path, "read_bytes", TEST_RAW_READ))

    def test_missing_independent_authority_rejected(self):
        with self.assertRaises(Unknown):
            phase_commands(
                "sha256:" + "b" * 64,
                "flowtracer-r3-dnr-synthetic",
                "baseline",
                phase_mounts("baseline"),
            )

    def test_parent_and_manifest_link_rejected(self):
        original = Path.lstat
        here = Path(__file__).parent
        mounts = phase_mounts("baseline")
        root = here.parents[3]
        self.assertEqual(checked_repo_file(root, here / "collector.py"), here / "collector.py")
        for victim in (root, here, here / "execution-inputs.json"):

            def linked(path, *args, victim=victim, **kwargs):
                if path == victim:
                    return SimpleNamespace(
                        st_mode=stat.S_IFLNK | 0o777,
                        st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,
                    )
                return original(path, *args, **kwargs)

            with patch.object(Path, "lstat", linked), self.assertRaises(Unknown):
                synthetic_render(
                    "sha256:" + "b" * 64, "flowtracer-r3-dnr-synthetic", "baseline", mounts
                )

    def test_source_and_manifest_joint_reseal_cannot_update_independent_authority(self):
        here = Path(__file__).parent
        manifest_path = here / "execution-inputs.json"
        original_bytes = manifest_path.read_bytes()
        approved = hashlib.sha256(original_bytes).hexdigest()
        mutated = json.loads(original_bytes)
        mounts = phase_mounts("baseline")
        victim = here / "collector.py"
        forged = victim.read_bytes() + b"\n# SYNTHETIC_CHANGED\n"
        digest = hashlib.sha256(forged).hexdigest()
        for row in mutated["inputs"]:
            if row["path"].endswith("dnr_runtime/collector.py"):
                row["sha256"] = digest
        mounts[0]["sha256"] = digest
        original_read = Path.read_bytes

        def read_double(path):
            if path == manifest_path:
                return json.dumps(mutated).encode()
            return forged if path == victim else original_read(path)

        with (
            patch("supervisor.read_controller_manifest_digest", return_value=approved),
            patch.object(Path, "read_bytes", read_double),
            self.assertRaises(Unknown),
        ):
            phase_commands("sha256:" + "b" * 64, "flowtracer-r3-dnr-synthetic", "baseline", mounts)
        with (
            patch("supervisor.read_controller_manifest_digest", return_value="a" * 64),
            self.assertRaises(Unknown),
        ):
            phase_commands(
                "sha256:" + "b" * 64,
                "flowtracer-r3-dnr-synthetic",
                "baseline",
                phase_mounts("baseline"),
            )

    def test_same_hash_external_source_and_unknown_reparse_metadata_rejected(self):
        mounts = phase_mounts("baseline")
        mounts[0]["source"] = str(Path(__file__).parent.parents[3].parent / "external-same-hash.py")
        with self.assertRaises(Unknown):
            synthetic_render(
                "sha256:" + "b" * 64, "flowtracer-r3-dnr-synthetic", "baseline", mounts
            )
        here = Path(__file__).parent
        root = here.parents[3]
        original = Path.lstat
        for attrs in (None, True, 0x400):

            def unknown(path, *args, attrs=attrs, **kwargs):
                if path == here:
                    return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_file_attributes=attrs)
                return original(path, *args, **kwargs)

            with patch.object(Path, "lstat", unknown), self.assertRaises(Unknown):
                checked_repo_file(root, here / "collector.py")

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
        for phase in ("baseline", "enabled"):
            mounts = phase_mounts(phase)
            argv = synthetic_render(
                "sha256:" + "b" * 64, "flowtracer-r3-dnr-synthetic", phase, mounts
            )
            self.assertEqual(argv[:2], ["container", "create"])
            self.assertEqual(argv[-2:], ["--phase", phase])
            self.assertIn("--read-only", argv)
            self.assertIn("--cap-drop=ALL", argv)
            self.assertFalse(any("sysctl" in value or "privileged" in value for value in argv))
        mount = phase_mounts("enabled")[0]
        for invalid in (
            {**mount, "readonly": False},
            {**mount, "source": "relative.py"},
            {**mount, "sha256": "bad"},
        ):
            with self.assertRaises(Unknown):
                synthetic_render(
                    "sha256:" + "b" * 64, "flowtracer-r3-dnr-synthetic", "enabled", [invalid]
                )
        with patch("subprocess.Popen", side_effect=AssertionError("no real CLI")):
            with self.assertRaisesRegex(Unknown, "not_authorized"):
                actual_session_entry()

    def test_v2_guard_never_readies_on_caller_proof_flags(self):
        minimal = {"schema_version": "r3-dnr-audit-v2", "ok": True, "flushed": True}
        for state in (minimal, snapshot()):
            guard, _, _ = fake_guard()
            self.assertIsInstance(guard, Guard)
            guard.start()
            with self.assertRaises(Terminal):
                guard.setup(lambda state=state: (state, full_identity()), lambda: True)
            self.assertFalse(guard.ready)
            self.assertTrue(guard.closed)
            with self.assertRaises(Terminal):
                guard.before_target()

    def test_full_v2_snapshot_validation_rejects_each_missing_field_and_rules(self):
        state = snapshot()
        self.assertIsNone(check_snapshot(state, full_identity()))
        for key in state:
            malformed = copy.deepcopy(state)
            del malformed[key]
            with self.subTest(missing=key), self.assertRaises(Rejected):
                check_snapshot(malformed, full_identity())
        for key, bad in (
            ("schema_version", "r3-dnr-audit-v1"),
            ("extension_id", "b" * 32),
            ("session", "other"),
            ("observer_epoch", None),
            ("enabled_rulesets", ["wrong"]),
            ("dynamic_rules", [{}]),
            ("session_rules", [{}]),
            ("sequence", True),
            ("sequence", 1),
            ("token", "SYNTHETIC_SECRET"),
        ):
            malformed = {**state, key: bad}
            with self.subTest(key=key), self.assertRaises(Rejected):
                check_snapshot(malformed, full_identity())
        for identity in (
            {},
            {"trusted_cdp": True, "inventory_proven": True, "clock_equivalence_proven": True},
            {**full_identity(), "extension_id": "bad"},
        ):
            with self.assertRaises(Rejected):
                check_snapshot(state, identity)
        malformed = {
            **state,
            "sequence": 1,
            "receipts": [{**receipt(), "timestamp_source": "fixture"}],
        }
        with self.assertRaises(Rejected):
            check_snapshot(malformed, full_identity())

    def test_v2_guard_close_and_termination_never_fall_through_exception_barrier(self):
        def raises():
            raise RuntimeError("SYNTHETIC_SECRET")

        for close, confirmed in ((lambda: True, True), (lambda: False, False), (raises, False)):
            for terminate in (lambda: None, raises):
                guard, timers, _ = fake_guard()
                self.assertIsInstance(guard, Guard)
                guard.terminate = terminate
                guard.start()
                with self.assertRaises(Terminal) as caught:
                    try:
                        guard.setup(lambda: (snapshot(), full_identity()), close)
                    except Exception:
                        self.fail("Exception barrier swallowed refusal")
                self.assertNotIn("SECRET", str(caught.exception))
                self.assertFalse(guard.ready)
                self.assertTrue(guard.denied)
                self.assertEqual(guard.closed, confirmed)
                self.assertEqual([timer.seconds for timer in timers], [120, 15, 5])
                self.assertTrue(timers[1].cancelled)
                with self.assertRaises(Terminal):
                    guard.before_target()

    def test_phase_mount_escape_wrong_phase_and_unbound_source_refused(self):
        enabled = phase_mounts("enabled")
        for phase, mounts in (
            ("baseline", enabled),
            ("enabled", phase_mounts("baseline")),
            ("enabled", enabled[:-1]),
            ("enabled", [*enabled, enabled[-1]]),
        ):
            with self.subTest(phase=phase, count=len(mounts)), self.assertRaises(Unknown):
                synthetic_render("sha256:" + "b" * 64, "flowtracer-r3-dnr-synthetic", phase, mounts)
        for edit in (
            {"target": "/opt/flowtracer-r3-runtime/../escape"},
            {"target": "/opt/flowtracer-r3-evil/probe.py"},
            {"target": "/opt//flowtracer-r3-runtime/probe.py"},
            {"target": "/opt/flowtracer-r3-runtime\\probe.py"},
            {"target": "/opt/flowtracer-r3-runtime/./collector.py"},
            {"sha256": "a" * 64},
            {"source": str(Path(__file__).resolve())},
        ):
            mounts = copy.deepcopy(enabled)
            mounts[0].update(edit)
            with self.subTest(edit=edit), self.assertRaises(Unknown):
                synthetic_render(
                    "sha256:" + "b" * 64, "flowtracer-r3-dnr-synthetic", "enabled", mounts
                )
        mounts = copy.deepcopy(enabled)
        mounts[-1]["source"] = str(
            Path(__file__).resolve().parent.parent / "dnr_offline/extension/rules.json"
        )
        with self.assertRaises(Unknown):
            synthetic_render("sha256:" + "b" * 64, "flowtracer-r3-dnr-synthetic", "enabled", mounts)

    def test_internal_source_base_not_historical_v2_base(self):
        import json

        plan = json.loads((Path(__file__).parent / "execution_plan.json").read_text())
        self.assertEqual(plan["base_commit"], "8f5fcc6d70c152616440eb340c7186bd64b690ba")
        self.assertNotEqual(plan["base_commit"], "ff70c198acb74b764435485611ec67484bcc7262")
        manifest = json.loads((Path(__file__).parent / "execution-inputs.json").read_text())
        self.assertEqual(manifest["actual_base"], plan["base_commit"])


if __name__ == "__main__":
    unittest.main()
