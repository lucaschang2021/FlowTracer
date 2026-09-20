from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

FORMAT = "flowtracer-runtime-identity-v2"
VERSION = 2
EXCLUDED = {
    "/.dockerenv",
    "/dev",
    "/proc",
    "/run",
    "/sys",
    "/tmp",  # noqa: S108 - must match the generator's volatile-path exclusion
    "/etc/hostname",
    "/etc/hosts",
    "/etc/resolv.conf",
}
SHA256 = re.compile(r"[0-9a-f]{64}")
MODE = re.compile(r"[0-7]{4}")


def excluded(path: str) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in EXCLUDED)


def canonical_payload(entries: list[dict[str, Any]]) -> bytes:
    return b"".join(
        json.dumps(entry, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        + b"\n"
        for entry in entries
    )


def validate_entry(entry: object) -> str:
    if not isinstance(entry, dict):
        raise RuntimeError("identity entry is not an object")
    entry_type = entry.get("type")
    required = {"gid", "mode", "path", "type", "uid"}
    if entry_type == "file":
        required.add("sha256")
    elif entry_type == "symlink":
        required.add("target")
    elif entry_type != "directory":
        raise RuntimeError(f"unsupported identity entry type: {entry_type!r}")
    if set(entry) != required:
        raise RuntimeError(f"identity entry fields do not match {entry_type}: {entry!r}")

    path = entry["path"]
    if (
        not isinstance(path, str)
        or not path.startswith("/")
        or str(PurePosixPath(path)) != path
        or excluded(path)
    ):
        raise RuntimeError(f"invalid or excluded identity path: {path!r}")
    if not isinstance(entry["uid"], int) or entry["uid"] < 0:
        raise RuntimeError(f"invalid UID for {path}")
    if not isinstance(entry["gid"], int) or entry["gid"] < 0:
        raise RuntimeError(f"invalid GID for {path}")
    if not isinstance(entry["mode"], str) or MODE.fullmatch(entry["mode"]) is None:
        raise RuntimeError(f"invalid mode for {path}")
    if entry_type == "file" and (
        not isinstance(entry["sha256"], str) or SHA256.fullmatch(entry["sha256"]) is None
    ):
        raise RuntimeError(f"invalid file hash for {path}")
    if entry_type == "symlink" and not isinstance(entry["target"], str):
        raise RuntimeError(f"invalid symlink target for {path}")
    return path


def validate(raw: bytes) -> dict[str, int | str]:
    document = json.loads(raw)
    expected_fields = {
        "entry_count",
        "entries",
        "excluded_volatile_paths",
        "format",
        "payload_bytes",
        "payload_sha256",
        "version",
    }
    if not isinstance(document, dict) or set(document) != expected_fields:
        raise RuntimeError("identity document fields do not match the v2 schema")
    if document["format"] != FORMAT or document["version"] != VERSION:
        raise RuntimeError("identity format/version mismatch")
    if document["excluded_volatile_paths"] != sorted(EXCLUDED):
        raise RuntimeError("identity volatile-path exclusions mismatch")
    entries = document["entries"]
    if not isinstance(entries, list):
        raise RuntimeError("identity entries is not a list")
    paths = [validate_entry(entry) for entry in entries]
    if not paths or paths[0] != "/" or paths != sorted(paths) or len(paths) != len(set(paths)):
        raise RuntimeError("identity paths are incomplete, unsorted, or duplicated")
    payload = canonical_payload(entries)
    summary = {
        "entry_count": len(entries),
        "payload_bytes": len(payload),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
    }
    if any(document[key] != value for key, value in summary.items()):
        raise RuntimeError("identity count, payload bytes, or payload hash mismatch")
    canonical_document = (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    if raw != canonical_document:
        raise RuntimeError("identity document encoding is not canonical UTF-8/LF")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    arguments = parser.parse_args()
    summary = validate(arguments.manifest.read_bytes())
    print(json.dumps({"status": "PASS", **summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
