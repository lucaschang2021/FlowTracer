from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_tree_identity(root: Path) -> dict[str, int | str]:
    entries: list[tuple[str, Path]] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"package tree contains a symlink: {path}")
        if path.is_file():
            entries.append((path.relative_to(root).as_posix(), path))
        elif not path.is_dir():
            raise RuntimeError(f"package tree contains an unsupported entry: {path}")
    entries.sort(key=lambda item: item[0])
    payload = b"".join(
        relative.encode("utf-8") + b" " + sha256(path).encode("ascii") + b"\n"
        for relative, path in entries
    )
    return {
        "files": len(entries),
        "payload_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--expected-files", type=int)
    parser.add_argument("--expected-payload-bytes", type=int)
    parser.add_argument("--expected-sha256")
    arguments = parser.parse_args()
    actual = package_tree_identity(arguments.root)
    expected_values = (
        arguments.expected_files,
        arguments.expected_payload_bytes,
        arguments.expected_sha256,
    )
    if any(value is not None for value in expected_values):
        if any(value is None for value in expected_values):
            raise RuntimeError("all expected package-tree values are required together")
        expected = {
            "files": arguments.expected_files,
            "payload_bytes": arguments.expected_payload_bytes,
            "sha256": arguments.expected_sha256,
        }
        if actual != expected:
            raise RuntimeError(f"package tree identity mismatch: {actual} != {expected}")
    print(json.dumps(actual, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
