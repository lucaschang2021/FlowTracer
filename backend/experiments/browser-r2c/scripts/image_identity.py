from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

EXCLUDED = {
    "/etc/hostname",
    "/etc/hosts",
    "/etc/resolv.conf",
    "/dev",
    "/proc",
    "/run",
    "/sys",
    "/tmp",  # noqa: S108 - volatile container path is intentionally excluded
    "/work",
}


def excluded(path: str) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in EXCLUDED)


def main() -> None:
    digest = hashlib.sha256()
    entries: list[Path] = []
    for root, directories, files in os.walk("/", topdown=True, followlinks=False):
        directories[:] = sorted(item for item in directories if not excluded(str(Path(root, item))))
        entries.extend(Path(root, item) for item in directories)
        entries.extend(Path(root, item) for item in sorted(files))

    for path in sorted(entries, key=lambda item: str(item)):
        value = str(path)
        if excluded(value):
            continue
        info = path.lstat()
        kind = "l" if stat.S_ISLNK(info.st_mode) else "f" if stat.S_ISREG(info.st_mode) else "o"
        digest.update(
            f"{kind}\0{value}\0{stat.S_IMODE(info.st_mode):o}\0{info.st_uid}\0{info.st_gid}\0".encode()
        )
        if kind == "l":
            digest.update(os.readlink(path).encode())
        elif kind == "f":
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        digest.update(b"\0")
    print(digest.hexdigest())


if __name__ == "__main__":
    main()
