from __future__ import annotations

import io
import subprocess
import sys
import tarfile
from pathlib import Path


def package_names() -> list[str]:
    output = subprocess.run(
        ["/usr/bin/dpkg-query", "-W", "-f=${binary:Package}\n"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return sorted(output.splitlines())


def add_bytes(archive: tarfile.TarFile, name: str, value: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(value)
    info.mode = 0o644
    archive.addfile(info, io.BytesIO(value))


def main() -> None:
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as archive:
        for name in package_names():
            source = Path("/usr/share/doc") / name.split(":", 1)[0] / "copyright"
            add_bytes(
                archive, f"debian-notices/{name.replace(':', '__')}.copyright", source.read_bytes()
            )
        add_bytes(
            archive,
            "notices/chromium-ABOUT",
            Path("/opt/browser-r1c/chromium-1234/chrome-linux64/ABOUT").read_bytes(),
        )
        add_bytes(
            archive,
            "notices/ffmpeg-COPYING.LGPLv2.1",
            Path("/opt/browser-r1c/ffmpeg-1011/COPYING.LGPLv2.1").read_bytes(),
        )


if __name__ == "__main__":
    main()
