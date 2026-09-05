from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

FINGERPRINT_FIELDS = (
    "rule_id",
    "source_path",
    "imported_module",
    "symbol_or_call",
    "normalized_location",
)
SEVERITIES = {"P0", "P1", "P2"}
REQUIRED_CHECKS = {
    "contract_toml_parse",
    "contract_schema_validation",
    "layer_assignment",
    "cross_layer_imports",
    "service_to_api",
    "domain_forbidden_infrastructure",
    "module_mutable_runtime_state",
    "suspected_import_time_external_call",
    "complexity_and_responsibility_growth",
    "provider_substitutability",
    "machine_baseline_snapshot",
    "baseline_existing_introduced_resolved",
}
MUTABLE_FACTORIES = {"defaultdict", "deque", "dict", "list", "set"}
IMPORT_TIME_EXTERNAL_CALLS = {
    "asyncpg.connect",
    "builtins.open",
    "httpx.get",
    "httpx.post",
    "httpx.request",
    "open",
    "redis.from_url",
    "requests.get",
    "requests.post",
    "requests.request",
    "socket.create_connection",
    "sqlalchemy.create_engine",
    "sqlalchemy.ext.asyncio.create_async_engine",
    "urllib.request.urlopen",
}
IMPORT_TIME_EXTERNAL_SUFFIXES = {
    ".apply_async",
    ".connect",
    ".delay",
    ".execute",
    ".ping",
    ".publish",
    ".send_task",
    ".subscribe",
    ".urlopen",
    ".write_bytes",
    ".write_text",
}


class ArchitectureError(RuntimeError):
    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True)
class SourceModule:
    path: str
    content: str


@dataclass(frozen=True)
class Finding:
    rule_id: str
    source_path: str
    imported_module: str
    symbol_or_call: str
    normalized_location: str
    severity: str
    detail: str
    disposition: str

    @property
    def fingerprint(self) -> tuple[str, str, str, str, str]:
        return (
            self.rule_id,
            self.source_path,
            self.imported_module,
            self.symbol_or_call,
            self.normalized_location,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "fingerprint": dict(zip(FINGERPRINT_FIELDS, self.fingerprint, strict=True)),
            "severity": self.severity,
            "detail": self.detail,
            "disposition": self.disposition,
        }


@dataclass(frozen=True)
class ModuleMetric:
    source_path: str
    lines: int
    functions: tuple[tuple[str, int], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "lines": self.lines,
            "functions": [
                {"qualified_name": name, "lines": lines} for name, lines in self.functions
            ],
        }


@dataclass(frozen=True)
class GateReport:
    existing: tuple[Finding, ...]
    introduced: tuple[Finding, ...]
    resolved: tuple[dict[str, str], ...]
    p0_total: int

    def as_dict(self) -> dict[str, Any]:
        all_findings = (*self.existing, *self.introduced)
        return {
            "status": "passed",
            "existing": len(self.existing),
            "introduced": len(self.introduced),
            "resolved": len(self.resolved),
            "p0_total": self.p0_total,
            "severity": {
                severity: sum(item.severity == severity for item in all_findings)
                for severity in sorted(SEVERITIES)
            },
        }


@dataclass(frozen=True)
class ImportRecord:
    imported_module: str
    symbol: str
    location: str


def load_contract(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            contract = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ArchitectureError([f"contract_toml_parse: {exc}"]) from None
    errors = validate_contract(contract)
    if errors:
        raise ArchitectureError(errors)
    return contract


def validate_contract(contract: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    _expect(contract, "schema_version", int, errors)
    _expect(contract, "contract_id", str, errors)
    _expect(contract, "baseline_commit", str, errors)
    for section in (
        "scope",
        "classification",
        "import_safety",
        "provider_substitution",
        "complexity",
        "gate",
        "tests",
        "stage_gate",
        "baseline",
    ):
        _expect(contract, section, dict, errors)
    layers = contract.get("layers")
    rules = contract.get("forbidden_dependency_rules")
    if not isinstance(layers, list) or not layers:
        errors.append("contract_schema_validation: layers must be a non-empty array")
        layers = []
    if not isinstance(rules, list) or not rules:
        errors.append(
            "contract_schema_validation: forbidden_dependency_rules must be a non-empty array"
        )
        rules = []
    layer_ids: list[str] = []
    for index, layer in enumerate(layers):
        if not isinstance(layer, dict):
            errors.append(f"contract_schema_validation: layers[{index}] must be an object")
            continue
        layer_id = layer.get("id")
        if not isinstance(layer_id, str) or not layer_id:
            errors.append(f"contract_schema_validation: layers[{index}].id is required")
        else:
            layer_ids.append(layer_id)
        if not _string_list(layer.get("paths")):
            errors.append(f"contract_schema_validation: layers[{index}].paths is invalid")
        if not _string_list(layer.get("forbidden_dependencies"), allow_empty=True):
            errors.append(
                f"contract_schema_validation: layers[{index}].forbidden_dependencies is invalid"
            )
    if len(layer_ids) != len(set(layer_ids)):
        errors.append("contract_semantic_validation: layer ids must be unique")
    order = contract.get("classification", {}).get("layer_match_order", [])
    if set(order) != set(layer_ids) or len(order) != len(layer_ids):
        errors.append(
            "contract_semantic_validation: layer_match_order must contain every layer exactly once"
        )
    rule_ids: list[str] = []
    rule_severity: dict[str, str] = {}
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            errors.append(
                f"contract_schema_validation: forbidden_dependency_rules[{index}] must be an object"
            )
            continue
        rule_id = rule.get("id")
        severity = rule.get("severity")
        patterns = [rule.get("source_glob"), *(rule.get("source_globs") or [])]
        patterns = [pattern for pattern in patterns if pattern is not None]
        if not isinstance(rule_id, str) or not rule_id:
            errors.append(
                f"contract_schema_validation: forbidden_dependency_rules[{index}].id is required"
            )
        else:
            rule_ids.append(rule_id)
            if isinstance(severity, str):
                rule_severity[rule_id] = severity
        if severity not in SEVERITIES:
            errors.append(
                "contract_schema_validation: forbidden_dependency_rules"
                f"[{index}].severity is invalid"
            )
        if not _string_list(patterns):
            errors.append(
                "contract_schema_validation: forbidden_dependency_rules"
                f"[{index}] needs source globs"
            )
        if not _string_list(rule.get("forbidden_import_prefixes")):
            errors.append(
                "contract_schema_validation: "
                f"forbidden_dependency_rules[{index}].forbidden_import_prefixes is invalid"
            )
    if len(rule_ids) != len(set(rule_ids)):
        errors.append("contract_semantic_validation: forbidden rule ids must be unique")
    gate = contract.get("gate", {})
    if set(gate.get("required_checks", [])) != REQUIRED_CHECKS:
        errors.append("contract_semantic_validation: gate.required_checks is incomplete")
    snapshot = gate.get("baseline_snapshot", {})
    if tuple(snapshot.get("fingerprint_fields", [])) != FINGERPRINT_FIELDS:
        errors.append("contract_semantic_validation: fingerprint fields changed")
    if snapshot.get("missing_snapshot_behavior") != "fail closed":
        errors.append("contract_semantic_validation: snapshot must fail closed")
    source_commit = snapshot.get("source_commit")
    if source_commit != contract.get("baseline_commit") or not _is_commit(source_commit):
        errors.append("contract_semantic_validation: baseline source commit is inconsistent")
    stage_gate = contract.get("stage_gate", {})
    if (
        stage_gate.get("total_p0_required") != 0
        or stage_gate.get("existing_p0_allowed") is not False
    ):
        errors.append("contract_semantic_validation: existing P0 must remain forbidden")
    baseline = contract.get("baseline", {})
    for finding in baseline.get("findings", []):
        if not isinstance(finding, dict):
            errors.append("contract_schema_validation: baseline finding must be an object")
            continue
        rule_id = finding.get("rule")
        severity = finding.get("severity")
        if severity not in SEVERITIES:
            errors.append("contract_schema_validation: baseline finding severity is invalid")
        if rule_id in rule_severity and rule_severity[rule_id] != severity:
            errors.append(
                "contract_semantic_validation: baseline finding severity conflicts with "
                f"rule {rule_id}"
            )
    ci = gate.get("ci", {})
    if ci.get("require_cancel_in_progress") is not True:
        errors.append("contract_semantic_validation: CI cancellation must be required")
    return errors


def generate_baseline(repo_root: Path, output: Path) -> dict[str, Any]:
    contract = load_contract(repo_root / "ARCHITECTURE.toml")
    source_commit = contract["baseline_commit"]
    modules = _git_modules(repo_root, source_commit)
    findings, metrics = scan_modules(modules, contract)
    p0 = [finding for finding in findings if finding.severity == "P0"]
    if p0:
        raise ArchitectureError(
            [
                "machine_baseline_snapshot: fixed baseline contains forbidden P0: "
                + ", ".join(_fingerprint_text(finding.fingerprint) for finding in p0)
            ]
        )
    snapshot = {
        "schema_version": 1,
        "source_commit": source_commit,
        "scan_scope": contract["gate"]["baseline_snapshot"]["scan_scope"],
        "fingerprint_fields": list(FINGERPRINT_FIELDS),
        "findings": [finding.as_dict() for finding in findings],
        "module_metrics": [metric.as_dict() for metric in metrics],
        "tracked_tests": _git_python_tests(repo_root, source_commit),
        "resolved_fingerprints": [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot


def check_architecture(repo_root: Path) -> GateReport:
    contract = load_contract(repo_root / "ARCHITECTURE.toml")
    snapshot_path = repo_root / contract["gate"]["baseline_snapshot"]["output_path"]
    snapshot = _load_snapshot(snapshot_path, contract)
    modules = _working_tree_modules(repo_root)
    current_findings, current_metrics = scan_modules(modules, contract)
    current_findings = _sort_findings(
        [*current_findings, *_complexity_growth(snapshot, current_metrics, contract)]
    )
    baseline_by_fingerprint = {
        _fingerprint_from_dict(item["fingerprint"]): item for item in snapshot["findings"]
    }
    current_by_fingerprint = {finding.fingerprint: finding for finding in current_findings}
    existing = tuple(
        finding
        for fingerprint, finding in current_by_fingerprint.items()
        if fingerprint in baseline_by_fingerprint
    )
    introduced = tuple(
        finding
        for fingerprint, finding in current_by_fingerprint.items()
        if fingerprint not in baseline_by_fingerprint
    )
    resolved = tuple(
        baseline_by_fingerprint[fingerprint]["fingerprint"]
        for fingerprint in sorted(set(baseline_by_fingerprint) - set(current_by_fingerprint))
    )
    errors: list[str] = []
    current_tests = set(_working_tree_python_tests(repo_root))
    missing_tests = sorted(set(snapshot["tracked_tests"]) - current_tests)
    if missing_tests:
        errors.append("preserve_existing_tests: missing " + ", ".join(missing_tests))
    p0 = [finding for finding in current_findings if finding.severity == "P0"]
    if p0:
        errors.append(f"stage_gate: total P0 is {len(p0)}, required 0")
    if introduced:
        errors.append(
            "baseline_delta: introduced findings: "
            + ", ".join(_fingerprint_text(finding.fingerprint) for finding in introduced)
        )
    resolved_ledger = {
        _fingerprint_from_dict(item) for item in snapshot.get("resolved_fingerprints", [])
    }
    regressed = resolved_ledger & set(current_by_fingerprint)
    if regressed:
        errors.append(
            "baseline_delta: resolved findings reappeared: "
            + ", ".join(_fingerprint_text(item) for item in sorted(regressed))
        )
    for finding in existing:
        baseline_item = baseline_by_fingerprint[finding.fingerprint]
        if finding.severity != baseline_item["severity"]:
            errors.append(
                "baseline_delta: severity changed for " + _fingerprint_text(finding.fingerprint)
            )
        if not baseline_item.get("disposition"):
            errors.append(
                "baseline_delta: existing finding has no disposition: "
                + _fingerprint_text(finding.fingerprint)
            )
    _validate_provider_substitution(modules, errors)
    _validate_ci(repo_root, contract, errors)
    if errors:
        raise ArchitectureError(errors)
    return GateReport(existing, introduced, resolved, len(p0))


def scan_modules(
    modules: Sequence[SourceModule], contract: Mapping[str, Any]
) -> tuple[list[Finding], list[ModuleMetric]]:
    parsed: dict[str, ast.Module] = {}
    errors: list[str] = []
    for module in modules:
        try:
            parsed[module.path] = ast.parse(module.content, filename=module.path)
        except SyntaxError as exc:
            errors.append(f"source_parse: {module.path}: {exc.msg}")
    if errors:
        raise ArchitectureError(errors)
    layers: dict[str, str] = {}
    for module in modules:
        layer = _assign_layer(module.path, parsed[module.path], contract)
        if layer is None:
            errors.append(f"layer_assignment: {module.path} has no unique layer")
        else:
            layers[module.path] = layer
    if errors:
        raise ArchitectureError(errors)
    module_layers = {_module_name(path): layer for path, layer in layers.items()}
    findings: list[Finding] = []
    metrics: list[ModuleMetric] = []
    for module in modules:
        tree = parsed[module.path]
        source_layer = layers[module.path]
        imports = _collect_imports(tree, _module_name(module.path))
        findings.extend(
            _import_findings(module.path, source_layer, imports, module_layers, contract)
        )
        findings.extend(_mutable_state_findings(module.path, tree))
        findings.extend(_import_time_findings(module.path, tree))
        findings.extend(_provider_port_location_findings(module.path, tree, source_layer))
        metric, complexity = _complexity_findings(module, tree, contract)
        metrics.append(metric)
        findings.extend(complexity)
    findings.extend(_responsibility_findings(modules, contract))
    return _sort_findings(findings), sorted(metrics, key=lambda item: item.source_path)


def _import_findings(
    source_path: str,
    source_layer: str,
    imports: Sequence[ImportRecord],
    module_layers: Mapping[str, str],
    contract: Mapping[str, Any],
) -> list[Finding]:
    findings: list[Finding] = []
    layer = next(item for item in contract["layers"] if item["id"] == source_layer)
    forbidden_layers = set(layer["forbidden_dependencies"])
    for record in imports:
        target_layer = _target_layer(record.imported_module, module_layers)
        if target_layer in forbidden_layers:
            findings.append(
                Finding(
                    "cross_layer_import",
                    source_path,
                    record.imported_module,
                    record.symbol,
                    record.location,
                    "P1",
                    f"{source_layer} imports forbidden layer {target_layer}",
                    _default_disposition("cross_layer_import", source_path, contract),
                )
            )
        for rule in contract["forbidden_dependency_rules"]:
            patterns = [rule.get("source_glob"), *(rule.get("source_globs") or [])]
            if not any(pattern and _glob_match(source_path, pattern) for pattern in patterns):
                continue
            if not any(
                _module_has_prefix(record.imported_module, prefix)
                for prefix in rule["forbidden_import_prefixes"]
            ):
                continue
            findings.append(
                Finding(
                    rule["id"],
                    source_path,
                    record.imported_module,
                    record.symbol,
                    record.location,
                    rule["severity"],
                    f"forbidden import from {record.imported_module}",
                    _default_disposition(rule["id"], source_path, contract),
                )
            )
    return findings


def _mutable_state_findings(source_path: str, tree: ast.Module) -> list[Finding]:
    findings: list[Finding] = []
    for node in tree.body:
        name = ""
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            name = _assigned_name(node.targets[0])
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            name = _assigned_name(node.target)
            value = node.value
        if not name or value is None or not _is_mutable_value(value):
            continue
        findings.append(
            Finding(
                "module_mutable_runtime_state",
                source_path,
                "",
                name,
                "module",
                "P1",
                f"module-level mutable value assigned to {name}",
                "Fixed-baseline module declaration; no new mutable global is allowed.",
            )
        )
    return findings


def _import_time_findings(source_path: str, tree: ast.Module) -> list[Finding]:
    findings: list[Finding] = []
    aliases = _import_aliases(tree)
    for statement in tree.body:
        calls = [node for node in ast.walk(statement) if isinstance(node, ast.Call)]
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            calls = _definition_time_calls(statement)
        for call in calls:
            name = _resolve_call_alias(_dotted_name(call.func), aliases)
            if not name or not _looks_external_call(name):
                continue
            findings.append(
                Finding(
                    "suspected_import_time_external_call",
                    source_path,
                    "",
                    name,
                    "module",
                    "P0",
                    f"suspected external operation at import time: {name}",
                    "P0 cannot be baselined; move the call behind an invoked operation.",
                )
            )
    return findings


def _provider_port_location_findings(
    source_path: str, tree: ast.Module, source_layer: str
) -> list[Finding]:
    required_ports = {
        "AnalysisProvider",
        "EmbeddingProvider",
        "AcquisitionBackend",
        "AcquisitionFetcher",
        "EventPublisher",
    }
    if source_layer == "domain_policy":
        return []
    return [
        Finding(
            "provider_port_location",
            source_path,
            "typing.Protocol",
            node.name,
            f"class:{node.name}",
            "P1",
            f"provider port {node.name} is outside domain_policy",
            "Fixed-baseline port location; move only in the admitted provider-seam phase.",
        )
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name in required_ports
        and any(_dotted_name(base).endswith("Protocol") for base in node.bases)
    ]


def _complexity_findings(
    module: SourceModule, tree: ast.Module, contract: Mapping[str, Any]
) -> tuple[ModuleMetric, list[Finding]]:
    settings = contract["complexity"]
    module_lines = len(module.content.splitlines())
    visitor = _FunctionVisitor()
    visitor.visit(tree)
    functions: list[tuple[str, int]] = []
    findings: list[Finding] = []
    for name, node in visitor.functions:
        lines = (node.end_lineno or node.lineno) - node.lineno + 1
        functions.append((name, lines))
        if lines >= settings["function_warning_lines"]:
            findings.append(
                Finding(
                    "complexity_function_warning",
                    module.path,
                    "",
                    name,
                    f"function:{name}",
                    "P2",
                    f"function has {lines} physical lines",
                    _complexity_disposition(module.path, contract),
                )
            )
    if module_lines >= settings["module_warning_lines"]:
        findings.append(
            Finding(
                "complexity_module_warning",
                module.path,
                "",
                "",
                "module",
                "P2",
                f"module has {module_lines} physical lines",
                _complexity_disposition(module.path, contract),
            )
        )
    return ModuleMetric(module.path, module_lines, tuple(sorted(functions))), findings


def _responsibility_findings(
    modules: Sequence[SourceModule], contract: Mapping[str, Any]
) -> list[Finding]:
    paths = {module.path for module in modules}
    threshold = contract["complexity"]["responsibility_warning_count"]
    findings: list[Finding] = []
    for module in contract["baseline"].get("modules", []):
        codes = module.get("responsibility_codes", [])
        path = module.get("path")
        if path not in paths or len(codes) <= threshold:
            continue
        findings.append(
            Finding(
                "responsibility_warning",
                path,
                "",
                ",".join(codes),
                "module",
                "P2",
                f"audited responsibility classes: {', '.join(codes)}",
                module["disposition"],
            )
        )
    return findings


def _complexity_growth(
    snapshot: Mapping[str, Any],
    current_metrics: Sequence[ModuleMetric],
    contract: Mapping[str, Any],
) -> list[Finding]:
    settings = contract["complexity"]
    baseline = {item["source_path"]: item for item in snapshot["module_metrics"]}
    findings: list[Finding] = []
    for metric in current_metrics:
        old = baseline.get(metric.source_path)
        if old is None:
            findings.extend(_new_complexity_findings(metric, settings))
            continue
        if old["lines"] >= settings["module_warning_lines"] and metric.lines > old["lines"]:
            findings.append(
                Finding(
                    "complexity_module_growth",
                    metric.source_path,
                    "",
                    "",
                    "module",
                    "P2",
                    f"baseline module grew from {old['lines']} to {metric.lines} lines",
                    _complexity_disposition(metric.source_path, contract),
                )
            )
        old_functions = {item["qualified_name"]: item["lines"] for item in old["functions"]}
        for name, lines in metric.functions:
            old_lines = old_functions.get(name)
            if (
                old_lines is not None
                and old_lines >= settings["function_warning_lines"]
                and lines > old_lines
            ):
                findings.append(
                    Finding(
                        "complexity_function_growth",
                        metric.source_path,
                        "",
                        name,
                        f"function:{name}",
                        "P2",
                        f"baseline function grew from {old_lines} to {lines} lines",
                        _complexity_disposition(metric.source_path, contract),
                    )
                )
    return findings


def _new_complexity_findings(metric: ModuleMetric, settings: Mapping[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if metric.lines >= settings["module_warning_lines"]:
        severity = "P1" if metric.lines >= settings["new_module_failure_lines"] else "P2"
        findings.append(
            Finding(
                "complexity_new_module_threshold",
                metric.source_path,
                "",
                "",
                "module",
                severity,
                f"new module has {metric.lines} physical lines",
                "Split only along evidenced responsibilities before adding the module.",
            )
        )
    for name, lines in metric.functions:
        if lines < settings["function_warning_lines"]:
            continue
        severity = "P1" if lines >= settings["new_function_failure_lines"] else "P2"
        findings.append(
            Finding(
                "complexity_new_function_threshold",
                metric.source_path,
                "",
                name,
                f"function:{name}",
                severity,
                f"new function has {lines} physical lines",
                "Extract only an evidenced responsibility before adding the function.",
            )
        )
    return findings


def _validate_provider_substitution(modules: Sequence[SourceModule], errors: list[str]) -> None:
    trees = {module.path: ast.parse(module.content) for module in modules}
    requirements = (
        (
            "backend/app/providers/analysis.py",
            "AnalysisProvider",
            "FakeAnalysisProvider",
            "OpenAICompatibleProvider",
            "analyze",
        ),
        (
            "backend/app/providers/embedding.py",
            "EmbeddingProvider",
            "FakeEmbeddingProvider",
            "OpenAICompatibleEmbeddingProvider",
            "embed",
        ),
    )
    for path, protocol, fake, production, method in requirements:
        tree = trees.get(path)
        if tree is None:
            errors.append(f"provider_substitutability: missing {path}")
            continue
        classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        for class_name in (protocol, fake, production):
            node = classes.get(class_name)
            if node is None or not any(
                isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method
                for child in node.body
            ):
                errors.append(
                    f"provider_substitutability: {class_name} must expose {method} in {path}"
                )
    acquisition = trees.get("backend/app/domains/acquisition_ports.py")
    port_methods = {
        "AcquisitionBackend": ("acquire",),
        "ContentFetcher": ("fetch",),
        "EventPublisher": ("publish",),
        "AcquisitionRunRepository": (
            "claim_run",
            "heartbeat",
            "finish_success",
            "finish_failure",
            "event_for",
        ),
    }
    for protocol, methods in port_methods.items():
        for method in methods:
            if acquisition is None or not _has_protocol_method(acquisition, protocol, method):
                errors.append(f"provider_substitutability: {protocol}.{method} is required")


def _validate_ci(repo_root: Path, contract: Mapping[str, Any], errors: list[str]) -> None:
    workflow = repo_root / ".github" / "workflows" / "backend.yml"
    if not workflow.is_file():
        errors.append("architecture_ci_step: missing .github/workflows/backend.yml")
        return
    content = workflow.read_text(encoding="utf-8")
    required_fragments = {
        "concurrency group": "group: backend-${{ github.workflow }}-${{ github.ref }}",
        "cancel-in-progress": "cancel-in-progress: true",
        "lint": "- name: Lint",
        "types": "- name: Types",
        "tests": "- name: Tests",
        "architecture": "- name: Architecture",
    }
    for label, fragment in required_fragments.items():
        if fragment not in content:
            errors.append(f"architecture_ci_step: missing {label}")
    required_steps = set(contract["gate"]["ci"]["required_backend_steps"])
    if required_steps != {"lint", "types", "tests", "architecture"}:
        errors.append("architecture_ci_step: contract backend steps changed")


def _load_snapshot(path: Path, contract: Mapping[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        raise ArchitectureError([f"machine_baseline_snapshot: missing required snapshot {path}"])
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArchitectureError([f"machine_baseline_snapshot: invalid snapshot: {exc}"]) from None
    errors: list[str] = []
    if snapshot.get("schema_version") != 1:
        errors.append("machine_baseline_snapshot: unsupported schema_version")
    if snapshot.get("source_commit") != contract["baseline_commit"]:
        errors.append("machine_baseline_snapshot: source_commit mismatch")
    if tuple(snapshot.get("fingerprint_fields", [])) != FINGERPRINT_FIELDS:
        errors.append("machine_baseline_snapshot: fingerprint fields mismatch")
    findings = snapshot.get("findings")
    metrics = snapshot.get("module_metrics")
    tracked_tests = snapshot.get("tracked_tests")
    if (
        not isinstance(findings, list)
        or not isinstance(metrics, list)
        or not _string_list(tracked_tests)
    ):
        errors.append(
            "machine_baseline_snapshot: findings, module_metrics, and tracked_tests are invalid"
        )
    else:
        seen: set[tuple[str, str, str, str, str]] = set()
        for item in findings:
            if not isinstance(item, dict) or not isinstance(item.get("fingerprint"), dict):
                errors.append("machine_baseline_snapshot: malformed finding")
                continue
            fingerprint = item["fingerprint"]
            if len(fingerprint) != len(FINGERPRINT_FIELDS) or set(fingerprint) != set(
                FINGERPRINT_FIELDS
            ):
                errors.append("machine_baseline_snapshot: finding fingerprint keys changed")
                continue
            key = _fingerprint_from_dict(fingerprint)
            if key in seen:
                errors.append("machine_baseline_snapshot: duplicate fingerprint")
            seen.add(key)
            if item.get("severity") not in SEVERITIES or not item.get("disposition"):
                errors.append("machine_baseline_snapshot: finding metadata is incomplete")
    if errors:
        raise ArchitectureError(errors)
    return snapshot


def _git_modules(repo_root: Path, commit: str) -> list[SourceModule]:
    names = _run_git(repo_root, "ls-tree", "-r", "--name-only", commit, "backend/app").splitlines()
    return [
        SourceModule(name, _run_git(repo_root, "show", f"{commit}:{name}"))
        for name in sorted(item for item in names if item.endswith(".py"))
    ]


def _working_tree_modules(repo_root: Path) -> list[SourceModule]:
    names = _run_git(repo_root, "ls-files", "backend/app/**/*.py", "backend/app/*.py")
    modules: list[SourceModule] = []
    for name in sorted(set(names.splitlines())):
        path = repo_root / PurePosixPath(name)
        if path.is_file():
            modules.append(SourceModule(name, path.read_text(encoding="utf-8")))
    return modules


def _git_python_tests(repo_root: Path, commit: str) -> list[str]:
    names = _run_git(
        repo_root, "ls-tree", "-r", "--name-only", commit, "backend/tests"
    ).splitlines()
    return sorted(name for name in names if name.endswith(".py"))


def _working_tree_python_tests(repo_root: Path) -> list[str]:
    names = _run_git(repo_root, "ls-files", "backend/tests/**/*.py", "backend/tests/*.py")
    return sorted(
        name for name in set(names.splitlines()) if (repo_root / PurePosixPath(name)).is_file()
    )


def _run_git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        raise ArchitectureError([f"git {' '.join(args)}: {result.stderr.strip()}"])
    return result.stdout


def _collect_imports(tree: ast.Module, module_name: str) -> list[ImportRecord]:
    visitor = _ImportVisitor(module_name)
    visitor.visit(tree)
    return visitor.records


class _ImportVisitor(ast.NodeVisitor):
    def __init__(self, module_name: str) -> None:
        self.module_name = module_name
        self.scopes: list[str] = []
        self.records: list[ImportRecord] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scopes.append(f"function:{node.name}")
        self.generic_visit(node)
        self.scopes.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scopes.append(f"class:{node.name}")
        self.generic_visit(node)
        self.scopes.pop()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.records.append(ImportRecord(alias.name, alias.asname or alias.name, self.location))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = _resolve_import(self.module_name, node.module or "", node.level)
        for alias in node.names:
            self.records.append(ImportRecord(module, alias.name, self.location))

    @property
    def location(self) -> str:
        return "/".join(self.scopes) if self.scopes else "module"


class _FunctionVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scopes: list[str] = []
        self.functions: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        name = ".".join([*self.scopes, node.name])
        self.functions.append((name, node))
        self.scopes.append(node.name)
        self.generic_visit(node)
        self.scopes.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scopes.append(node.name)
        self.generic_visit(node)
        self.scopes.pop()


def _assign_layer(path: str, tree: ast.Module, contract: Mapping[str, Any]) -> str | None:
    if _is_inert_package_marker(path, tree):
        return _package_marker_layer(path)
    layers = {item["id"]: item for item in contract["layers"]}
    matches: list[str] = []
    for layer_id in contract["classification"]["layer_match_order"]:
        layer = layers[layer_id]
        if any(_glob_match(path, pattern) for pattern in layer["paths"]) and not any(
            _glob_match(path, pattern) for pattern in layer.get("exclude_paths", [])
        ):
            matches.append(layer_id)
    return matches[0] if len(matches) == 1 else None


def _package_marker_layer(path: str) -> str | None:
    prefixes = (
        ("backend/app/api/", "api_adapters"),
        ("backend/app/schemas/", "api_adapters"),
        ("backend/app/services/", "application_services"),
        ("backend/app/domains/", "domain_policy"),
        ("backend/app/domain/", "domain_policy"),
        ("backend/app/models/", "models_persistence"),
        ("backend/app/db/", "models_persistence"),
        ("backend/app/providers/", "providers_infrastructure"),
        ("backend/app/adapters/", "providers_infrastructure"),
        ("backend/app/tasks/", "tasks"),
        ("backend/app/core/", "bootstrap_lifecycle"),
    )
    for prefix, layer in prefixes:
        if path.startswith(prefix):
            return layer
    return "bootstrap_lifecycle" if path == "backend/app/__init__.py" else None


def _is_inert_package_marker(path: str, tree: ast.Module) -> bool:
    if not path.endswith("/__init__.py"):
        return False
    return all(
        isinstance(node, (ast.Import, ast.ImportFrom))
        or (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))
        or (isinstance(node, ast.Assign) and _assigned_name(node.targets[0]) == "__all__")
        for node in tree.body
    )


def _target_layer(imported_module: str, module_layers: Mapping[str, str]) -> str | None:
    candidate = imported_module
    while candidate:
        if candidate in module_layers:
            return module_layers[candidate]
        candidate = candidate.rpartition(".")[0]
    return None


def _module_name(path: str) -> str:
    return (
        path.removeprefix("backend/")
        .removesuffix(".py")
        .replace("/", ".")
        .removesuffix(".__init__")
    )


def _resolve_import(current: str, module: str, level: int) -> str:
    if level == 0:
        return module
    package = current.rpartition(".")[0].split(".")
    keep = max(0, len(package) - level + 1)
    return ".".join([*package[:keep], *([module] if module else [])])


def _glob_match(path: str, pattern: str) -> bool:
    expression = re.escape(pattern)
    expression = expression.replace(r"\*\*/", "(?:.*/)?")
    expression = expression.replace(r"\*\*", ".*")
    expression = expression.replace(r"\*", "[^/]*")
    expression = expression.replace(r"\?", "[^/]")
    return re.fullmatch(expression, path) is not None


def _module_has_prefix(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def _assigned_name(node: ast.expr) -> str:
    return node.id if isinstance(node, ast.Name) else ""


def _is_mutable_value(node: ast.expr) -> bool:
    if isinstance(node, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)):
        return True
    return (
        isinstance(node, ast.Call)
        and _dotted_name(node.func).rpartition(".")[2] in MUTABLE_FACTORIES
    )


def _definition_time_calls(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> list[ast.Call]:
    expressions: list[ast.AST] = []
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        expressions.extend(node.decorator_list)
        expressions.extend(node.args.defaults)
        expressions.extend(item for item in node.args.kw_defaults if item is not None)
    else:
        expressions.extend(node.decorator_list)
        expressions.extend(node.bases)
        expressions.extend(node.keywords)
    return [
        child for item in expressions for child in ast.walk(item) if isinstance(child, ast.Call)
    ]


def _import_aliases(tree: ast.Module) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[0]] = item.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for item in node.names:
                aliases[item.asname or item.name] = f"{node.module}.{item.name}"
    return aliases


def _resolve_call_alias(name: str, aliases: Mapping[str, str]) -> str:
    root, separator, remainder = name.partition(".")
    resolved = aliases.get(root)
    if resolved is None:
        return name
    return f"{resolved}.{remainder}" if separator else resolved


def _dotted_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _looks_external_call(name: str) -> bool:
    return (
        name in IMPORT_TIME_EXTERNAL_CALLS
        or name in {"write_bytes", "write_text"}
        or any(name.endswith(suffix) for suffix in IMPORT_TIME_EXTERNAL_SUFFIXES)
    )


def _has_protocol_method(tree: ast.Module, class_name: str, method: str) -> bool:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return any(
                isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method
                for child in node.body
            )
    return False


def _default_disposition(rule_id: str, path: str, contract: Mapping[str, Any]) -> str:
    for finding in contract["baseline"].get("findings", []):
        location = str(finding.get("location", ""))
        if finding.get("rule") == rule_id and _location_mentions_path(location, path):
            return str(finding["detail"])
    return "Fixed-baseline dependency debt; the exact fingerprint may not grow."


def _location_mentions_path(location: str, path: str) -> bool:
    normalized = location.replace("{", "").replace("}", "")
    filename = PurePosixPath(path).name
    return path in location or filename in normalized or location.endswith("backend/app/api")


def _complexity_disposition(path: str, contract: Mapping[str, Any]) -> str:
    for module in contract["baseline"].get("modules", []):
        if module.get("path") == path:
            return str(module["disposition"])
    return "Fixed-baseline complexity warning; no growth is allowed without disposition."


def _sort_findings(findings: Iterable[Finding]) -> list[Finding]:
    unique = {finding.fingerprint: finding for finding in findings}
    return [unique[key] for key in sorted(unique)]


def _fingerprint_from_dict(value: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    result = tuple(str(value[field]) for field in FINGERPRINT_FIELDS)
    return result  # type: ignore[return-value]


def _fingerprint_text(value: tuple[str, str, str, str, str]) -> str:
    return hashlib.sha256("\0".join(value).encode()).hexdigest()[:12]


def _expect(container: Mapping[str, Any], key: str, expected: type[Any], errors: list[str]) -> None:
    if not isinstance(container.get(key), expected):
        errors.append(f"contract_schema_validation: {key} must be {expected.__name__}")


def _string_list(value: Any, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(isinstance(item, str) and item for item in value)
    )


def _is_commit(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None
