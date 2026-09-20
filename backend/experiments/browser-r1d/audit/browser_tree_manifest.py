from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

BROWSER_ROOT = Path("/opt/browser-r1c")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def entry(path: Path) -> dict[str, Any]:
    info = path.lstat()
    result: dict[str, Any] = {
        "gid": info.st_gid,
        "mode": f"{stat.S_IMODE(info.st_mode):04o}",
        "path": path.relative_to(BROWSER_ROOT).as_posix(),
        "uid": info.st_uid,
    }
    if stat.S_ISDIR(info.st_mode):
        result["type"] = "directory"
    elif stat.S_ISREG(info.st_mode):
        result.update({"sha256": sha256(path), "type": "file"})
    elif stat.S_ISLNK(info.st_mode):
        result.update({"target": os.readlink(path), "type": "symlink"})
    else:
        raise RuntimeError(f"unsupported browser tree entry: {path}")
    return result


def manifest() -> dict[str, Any]:
    entries = [entry(BROWSER_ROOT)]
    for root, directories, files in os.walk(BROWSER_ROOT, topdown=True, followlinks=False):
        current = Path(root)
        directories.sort()
        files.sort()
        entries.extend(entry(current / name) for name in directories)
        entries.extend(entry(current / name) for name in files)
    return {"entries": entries, "root": str(BROWSER_ROOT), "schema_version": 1}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", type=Path)
    arguments = parser.parse_args()
    actual = manifest()
    if arguments.verify is None:
        print(json.dumps(actual, indent=2, sort_keys=True))
        return 0
    expected = json.loads(arguments.verify.read_text(encoding="utf-8"))
    if actual != expected:
        print("R1C_BROWSER_TREE_MISMATCH", file=sys.stderr)
        return 78
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
