from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

FORMAT = "flowtracer-runtime-identity-v2"
VERSION = 2
EXCLUDED = {
    "/.dockerenv",
    "/dev",
    "/proc",
    "/run",
    "/sys",
    "/tmp",  # noqa: S108 - volatile container tmpfs is intentionally excluded
    "/etc/hostname",
    "/etc/hosts",
    "/etc/resolv.conf",
}


def excluded(path: str) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in EXCLUDED)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def describe(path: Path) -> dict[str, Any]:
    info = path.lstat()
    value: dict[str, Any] = {
        "gid": info.st_gid,
        "mode": f"{stat.S_IMODE(info.st_mode):04o}",
        "path": str(path),
        "uid": info.st_uid,
    }
    if stat.S_ISDIR(info.st_mode):
        value["type"] = "directory"
    elif stat.S_ISREG(info.st_mode):
        value.update({"sha256": file_sha256(path), "type": "file"})
    elif stat.S_ISLNK(info.st_mode):
        value.update({"target": os.readlink(path), "type": "symlink"})
    else:
        raise RuntimeError(f"unsupported filesystem entry: {path}")
    return value


def main() -> None:
    paths: list[Path] = [Path("/")]
    for root, directories, files in os.walk("/", topdown=True, followlinks=False):
        directories[:] = sorted(name for name in directories if not excluded(str(Path(root, name))))
        paths.extend(Path(root, name) for name in directories)
        paths.extend(Path(root, name) for name in sorted(files))
    entries = [
        describe(path)
        for path in sorted(paths, key=lambda item: str(item))
        if not excluded(str(path))
    ]
    payload = b"".join(
        json.dumps(entry, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        + b"\n"
        for entry in entries
    )
    print(
        json.dumps(
            {
                "entry_count": len(entries),
                "entries": entries,
                "excluded_volatile_paths": sorted(EXCLUDED),
                "format": FORMAT,
                "payload_bytes": len(payload),
                "payload_sha256": hashlib.sha256(payload).hexdigest(),
                "version": VERSION,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
