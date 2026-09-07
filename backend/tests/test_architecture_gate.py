from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from architecture_gate.gate import (
    FINGERPRINT_FIELDS,
    ArchitectureError,
    SourceModule,
    _load_snapshot,
    check_architecture,
    generate_baseline,
    load_contract,
    scan_modules,
    validate_contract,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_contract_and_committed_baseline_are_valid() -> None:
    contract = load_contract(REPO_ROOT / "ARCHITECTURE.toml")
    report = check_architecture(REPO_ROOT)

    assert contract["baseline_commit"] == "f4b58c1ec0d20d075b98d5a9ca3d146d0b4deb56"
    assert report.p0_total == 0
    assert report.introduced == ()
    snapshot = json.loads((REPO_ROOT / "backend" / "architecture-baseline.json").read_text())
    assert {json.dumps(item, sort_keys=True) for item in report.resolved} == {
        json.dumps(item, sort_keys=True) for item in snapshot["resolved_fingerprints"]
    }
    assert report.existing


def test_frozen_openapi_blob_and_alembic_head_are_unchanged() -> None:
    contract = load_contract(REPO_ROOT / "ARCHITECTURE.toml")
    openapi = (REPO_ROOT / "backend" / "openapi" / "flowtracer-alpha-v0.1.json").read_bytes()
    header = f"blob {len(openapi)}\0".encode()
    blob = hashlib.sha1(header + openapi, usedforsecurity=False).hexdigest()
    head = contract["gate"]["compatibility"]["alembic_head"]
    revision_files = (REPO_ROOT / "backend" / "alembic" / "versions").glob("*.py")

    assert blob == contract["gate"]["compatibility"]["openapi_blob"]
    assert any(
        f'revision: str = "{head}"' in path.read_text(encoding="utf-8") for path in revision_files
    )


def test_minimal_backend_ci_has_required_concurrency_and_steps() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "backend.yml").read_text(encoding="utf-8")
    assert "cancel-in-progress: true" in workflow
    assert "group: backend-${{ github.workflow }}-${{ github.ref }}" in workflow
    for label in ("Lint", "Types", "Tests", "Architecture"):
        assert f"- name: {label}" in workflow


def test_baseline_generation_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    first_snapshot = generate_baseline(REPO_ROOT, first)
    second_snapshot = generate_baseline(REPO_ROOT, second)

    assert first.read_bytes() == second.read_bytes()
    assert first_snapshot == second_snapshot
    assert first_snapshot["fingerprint_fields"] == list(FINGERPRINT_FIELDS)
    assert "backend/tests/test_error_paths.py" in first_snapshot["tracked_tests"]
    assert all(
        set(item["fingerprint"]) == set(FINGERPRINT_FIELDS) for item in first_snapshot["findings"]
    )


def test_missing_or_malformed_snapshot_fails_closed(tmp_path: Path) -> None:
    contract = load_contract(REPO_ROOT / "ARCHITECTURE.toml")
    missing = tmp_path / "missing.json"
    with pytest.raises(ArchitectureError, match="missing required snapshot"):
        _load_snapshot(missing, contract)

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{}", encoding="utf-8")
    with pytest.raises(ArchitectureError, match="unsupported schema_version"):
        _load_snapshot(malformed, contract)


def test_contract_semantics_reject_severity_and_fingerprint_drift() -> None:
    contract = load_contract(REPO_ROOT / "ARCHITECTURE.toml")
    severity_drift = copy.deepcopy(contract)
    severity_drift["forbidden_dependency_rules"][3]["severity"] = "P0"
    errors = validate_contract(severity_drift)
    assert any("severity conflicts" in error for error in errors)

    fingerprint_drift = copy.deepcopy(contract)
    fingerprint_drift["gate"]["baseline_snapshot"]["fingerprint_fields"].pop()
    errors = validate_contract(fingerprint_drift)
    assert any("fingerprint fields changed" in error for error in errors)


@pytest.mark.parametrize(
    ("path", "source", "expected_rule", "severity"),
    [
        (
            "backend/app/services/new_service.py",
            "from app.api import dependencies\n",
            "service_to_api",
            "P0",
        ),
        (
            "backend/app/domains/new_policy.py",
            "import httpx\n",
            "domain_to_framework_or_io",
            "P0",
        ),
        (
            "backend/app/services/new_service.py",
            "CACHE = []\n",
            "module_mutable_runtime_state",
            "P1",
        ),
        (
            "backend/app/services/new_service.py",
            "import httpx\nRESULT = httpx.get('https://invalid.test')\n",
            "suspected_import_time_external_call",
            "P0",
        ),
    ],
)
def test_ast_gate_detects_forbidden_new_findings(
    path: str, source: str, expected_rule: str, severity: str
) -> None:
    contract = load_contract(REPO_ROOT / "ARCHITECTURE.toml")
    findings, _metrics = scan_modules([SourceModule(path, source)], contract)

    match = next(item for item in findings if item.rule_id == expected_rule)
    assert match.severity == severity
    assert match.source_path == path


def test_layer_assignment_fails_for_unowned_module() -> None:
    contract = load_contract(REPO_ROOT / "ARCHITECTURE.toml")
    with pytest.raises(ArchitectureError, match="has no unique layer"):
        scan_modules([SourceModule("backend/app/unknown.py", "VALUE = 1\n")], contract)


def test_complexity_warning_uses_stable_function_location() -> None:
    contract = load_contract(REPO_ROOT / "ARCHITECTURE.toml")
    body = "\n".join(["def oversized():", *["    value = 1"] * 81]) + "\n"
    findings, metrics = scan_modules(
        [SourceModule("backend/app/services/new_service.py", body)], contract
    )

    warning = next(item for item in findings if item.rule_id == "complexity_function_warning")
    assert warning.normalized_location == "function:oversized"
    assert metrics[0].functions == (("oversized", 82),)


def test_snapshot_json_has_no_duplicate_fingerprints() -> None:
    snapshot = json.loads(
        (REPO_ROOT / "backend" / "architecture-baseline.json").read_text(encoding="utf-8")
    )
    fingerprints = [
        tuple(item["fingerprint"][key] for key in FINGERPRINT_FIELDS)
        for item in snapshot["findings"]
    ]
    assert len(fingerprints) == len(set(fingerprints))
