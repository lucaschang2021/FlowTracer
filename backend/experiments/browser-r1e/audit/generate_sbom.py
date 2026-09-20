from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from license_policy import expression_for_debian_headers

TOOL_NAME = "flowtracer-r1c-sbom"
TOOL_VERSION = "1.0.0"
BROWSER_NOTICE = Path("/opt/browser-r1c/chromium-1234/chrome-linux64/ABOUT")
BROWSER_EXECUTABLE = Path("/opt/browser-r1c/chromium-1234/chrome-linux64/chrome")
FFMPEG_NOTICE = Path("/opt/browser-r1c/ffmpeg-1011/COPYING.LGPLv2.1")
FFMPEG_EXECUTABLE = Path("/opt/browser-r1c/ffmpeg-1011/ffmpeg-linux")
LICENSE_HEADER = re.compile(r"^License:\s*(?P<label>[^\n]*)$", re.MULTILINE)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def python_components() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    distributions = sorted(
        importlib.metadata.distributions(), key=lambda item: item.metadata["Name"].lower()
    )
    for distribution in distributions:
        name = distribution.metadata["Name"]
        expression = distribution.metadata.get("License-Expression")
        if not expression:
            expression = distribution.metadata.get("License")
        if not expression or "\n" in expression:
            classifiers = [
                value.removeprefix("License :: OSI Approved :: ")
                for value in distribution.metadata.get_all("Classifier", [])
                if value.startswith("License :: OSI Approved :: ")
            ]
            expression = " OR ".join(classifiers) if classifiers else "SEE-DISTRIBUTION-METADATA"
        result.append(
            {
                "bom-ref": f"pkg:pypi/{name.lower()}@{distribution.version}",
                "licenses": [{"expression": expression}],
                "name": name,
                "purl": f"pkg:pypi/{name.lower()}@{distribution.version}",
                "type": "library",
                "version": distribution.version,
            }
        )
    return result


def debian_records() -> list[dict[str, Any]]:
    output = subprocess.run(
        ["/usr/bin/dpkg-query", "-W", "-f=${binary:Package}\t${Version}\n"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    records: list[dict[str, Any]] = []
    for line in sorted(output.splitlines()):
        name, version = line.split("\t", 1)
        source = Path("/usr/share/doc") / name.split(":", 1)[0] / "copyright"
        if not source.is_file():
            raise RuntimeError(f"missing Debian copyright notice for {name}")
        notice_hash = sha256(source)
        labels = sorted(
            {
                match.group("label").strip()
                for match in LICENSE_HEADER.finditer(source.read_text(errors="replace"))
            }
        )
        records.append(
            {
                "license_expression": expression_for_debian_headers(labels, notice_hash),
                "license_notice_file": f"debian-notices/{name.replace(':', '__')}.copyright",
                "license_notice_sha256": notice_hash,
                "license_raw_headers": labels,
                "name": name,
                "version": version,
            }
        )
    return records


def debian_components(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for record in records:
        result.append(
            {
                "bom-ref": f"pkg:deb/debian/{record['name']}@{record['version']}",
                "licenses": [{"expression": record["license_expression"]}],
                "name": record["name"],
                "properties": [
                    {
                        "name": "flowtracer:persistent-license-notice",
                        "value": record["license_notice_file"],
                    },
                    {
                        "name": "flowtracer:license-notice-sha256",
                        "value": record["license_notice_sha256"],
                    },
                    {
                        "name": "flowtracer:license-raw-headers",
                        "value": json.dumps(record["license_raw_headers"]),
                    },
                ],
                "purl": f"pkg:deb/debian/{record['name']}@{record['version']}",
                "type": "library",
                "version": record["version"],
            }
        )
    return result


def browser_components() -> list[dict[str, Any]]:
    return [
        {
            "bom-ref": "browser:chromium-full@151.0.7922.34-r1234",
            "hashes": [{"alg": "SHA-256", "content": sha256(BROWSER_EXECUTABLE)}],
            "licenses": [{"expression": "BSD-3-Clause AND LicenseRef-Chromium-Third-Party"}],
            "name": "chromium-full",
            "properties": [
                {"name": "flowtracer:executable-path", "value": str(BROWSER_EXECUTABLE)},
                {"name": "flowtracer:persistent-notice", "value": "notices/chromium-ABOUT"},
                {"name": "flowtracer:notice-sha256", "value": sha256(BROWSER_NOTICE)},
            ],
            "type": "application",
            "version": "151.0.7922.34-r1234",
        },
        {
            "bom-ref": "binary:ffmpeg@playwright-r1011",
            "hashes": [{"alg": "SHA-256", "content": sha256(FFMPEG_EXECUTABLE)}],
            "licenses": [{"expression": "LGPL-2.1-or-later"}],
            "name": "ffmpeg",
            "properties": [
                {
                    "name": "flowtracer:persistent-notice",
                    "value": "notices/ffmpeg-COPYING.LGPLv2.1",
                },
                {"name": "flowtracer:notice-sha256", "value": sha256(FFMPEG_NOTICE)},
            ],
            "type": "application",
            "version": "playwright-r1011",
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--debian-license-inventory", action="store_true")
    arguments = parser.parse_args()
    records = debian_records()
    if arguments.debian_license_inventory:
        print(json.dumps({"components": records, "schema_version": 1}, indent=2, sort_keys=True))
        return
    components = python_components() + debian_components(records) + browser_components()
    print(
        json.dumps(
            {
                "bomFormat": "CycloneDX",
                "components": sorted(components, key=lambda item: str(item["bom-ref"])),
                "metadata": {
                    "tools": {
                        "components": [
                            {"name": TOOL_NAME, "type": "application", "version": TOOL_VERSION}
                        ]
                    }
                },
                "specVersion": "1.6",
                "version": 1,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
