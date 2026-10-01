"""All receipts in this suite are SYNTHETIC, never runtime authority."""

from __future__ import annotations

import ast
import copy
import hashlib
import subprocess
import sys
import unittest
from pathlib import Path

from collector import Collector
from contract import FILES, MATRIX, Rejected, canonical, strict_json
from fixture import response
from harness import synthetic_graph, wiring_plan
from supervisor import launch_real, remaining_timeout_ms
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
            imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
            self.assertFalse(
                any(
                    "playwright" in ast.unparse(n)
                    or "scrapling" in ast.unparse(n)
                    or "socket" in ast.unparse(n)
                    for n in imports
                )
            )

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


if __name__ == "__main__":
    unittest.main()
