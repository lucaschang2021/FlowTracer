from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from license_policy import (
    EXACT_SPDX_BY_RAW_HEADER,
    expression_for_debian_headers,
    notice_license_ref,
)

SHA256 = re.compile(r"^[0-9a-f]{64}$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_license_policy_contract() -> None:
    """Prevent known lossy Debian-header mappings from reappearing."""

    notice_hash = "0" * 64
    expected_ref = notice_license_ref(notice_hash)
    notice_only_cases = {
        "BSD-1 variant": ["BSD-1-clause"],
        "BSD-4/UC variant": ["BSD-4-clause-UC"],
        "composite OR": ["GPL-2.0 OR Artistic-1.0"],
        "with exception": ["GPL-3+ with Bison exception"],
        "version suffix": ["GPL-2+"],
        "unknown label": ["Unreviewed-Custom-License"],
        "multiple file-set labels": ["MIT", "BSD-3-Clause"],
    }
    for case, headers in notice_only_cases.items():
        expression = expression_for_debian_headers(headers, notice_hash)
        if expression != expected_ref:
            raise SystemExit(f"lossy license-policy mapping for {case}: {expression}")
    for raw_header, spdx_expression in EXACT_SPDX_BY_RAW_HEADER.items():
        expression = expression_for_debian_headers([raw_header], notice_hash)
        if expression != spdx_expression:
            raise SystemExit(f"exact license-policy mapping failed: {raw_header}")


def properties(component: dict[str, Any]) -> dict[str, str]:
    return {item["name"]: item["value"] for item in component.get("properties", [])}


def raw_headers(values: dict[str, str], component_name: str) -> list[str]:
    serialized = values.get("flowtracer:license-raw-headers")
    if serialized is None:
        raise SystemExit(f"missing Debian raw license headers: {component_name}")
    try:
        headers = json.loads(serialized)
    except json.JSONDecodeError as error:
        raise SystemExit(f"invalid Debian raw license headers: {component_name}") from error
    if not isinstance(headers, list) or not all(isinstance(header, str) for header in headers):
        raise SystemExit(f"invalid Debian raw license header type: {component_name}")
    return sorted(set(headers))


def validate_debian_license(component: dict[str, Any], evidence_root: Path) -> None:
    values = properties(component)
    notice_hash = values.get("flowtracer:license-notice-sha256", "")
    notice_path = values.get("flowtracer:persistent-license-notice", "")
    if not SHA256.fullmatch(notice_hash):
        raise SystemExit(f"missing Debian notice hash: {component['name']}")
    if not notice_path:
        raise SystemExit(f"missing persistent Debian notice: {component['name']}")
    persisted_notice = evidence_root / notice_path
    if not persisted_notice.is_file():
        raise SystemExit(f"missing persisted Debian notice: {component['name']}")
    if sha256(persisted_notice) != notice_hash:
        raise SystemExit(f"Debian notice hash mismatch: {component['name']}")
    headers = raw_headers(values, component["name"])
    expression = component["licenses"][0].get("expression")
    expected = expression_for_debian_headers(headers, notice_hash)
    if expression != expected:
        raise SystemExit(f"lossy Debian license expression: {component['name']}")
    exact_single = len(headers) == 1 and headers[0] in EXACT_SPDX_BY_RAW_HEADER
    if not exact_single and expression != notice_license_ref(notice_hash):
        raise SystemExit(f"non-exact Debian label lost raw semantics: {component['name']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sbom", type=Path)
    arguments = parser.parse_args()
    validate_license_policy_contract()
    bom = json.loads(arguments.sbom.read_text(encoding="utf-8"))
    if bom.get("bomFormat") != "CycloneDX" or bom.get("specVersion") != "1.6":
        raise SystemExit("invalid CycloneDX document")
    components = bom.get("components", [])
    debian = [component for component in components if component["bom-ref"].startswith("pkg:deb/")]
    if len(debian) != 206:
        raise SystemExit(f"expected 206 Debian components, got {len(debian)}")
    evidence_root = arguments.sbom.parent
    for component in debian:
        if not component.get("licenses"):
            raise SystemExit(f"missing Debian license: {component['name']}")
        validate_debian_license(component, evidence_root)
    for reference in (
        "browser:chromium-headless-shell@151.0.7922.34-r1234",
        "binary:ffmpeg@playwright-r1011",
    ):
        component = next(item for item in components if item["bom-ref"] == reference)
        binary_hash = component["hashes"][0]["content"]
        values = properties(component)
        notice_hash = values.get("flowtracer:notice-sha256", "")
        if not SHA256.fullmatch(binary_hash) or not SHA256.fullmatch(notice_hash):
            raise SystemExit(f"invalid binary or notice hash: {reference}")
        if binary_hash == notice_hash:
            raise SystemExit(f"notice hash used as binary hash: {reference}")
    print(f"SBOM_STATIC_VALIDATION=PASS components={len(components)} debian={len(debian)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
