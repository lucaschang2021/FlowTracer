from __future__ import annotations

import errno
import json
import os
import shutil
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from scrapling.fetchers import DynamicFetcher

EXECUTABLE = "/opt/browser-r1c/chromium-1234/chrome-linux64/chrome"
TMP_ROOT = Path("/tmp")  # noqa: S108 - dedicated container tmpfs required by R1C
HOME_DIR = TMP_ROOT / "flowtracer-r1c-home"
CONFIG_DIR = TMP_ROOT / "flowtracer-r1c-config"
CACHE_DIR = TMP_ROOT / "flowtracer-r1c-cache"
RENDER_PROFILE = TMP_ROOT / "flowtracer-r1c-render-profile"
FAILURE_PROFILE = TMP_ROOT / "flowtracer-r1c-failure-profile"
RUNTIME_ENV = {
    "HOME": str(HOME_DIR),
    "XDG_CONFIG_HOME": str(CONFIG_DIR),
    "XDG_CACHE_HOME": str(CACHE_DIR),
}


class FixtureHandler(BaseHTTPRequestHandler):
    requests = 0

    def do_GET(self) -> None:
        type(self).requests += 1
        body = b"<title>r1c-offline</title><main id='result'>dynamic-rendered</main>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def assert_read_only_root() -> None:
    probe = Path("/r1c-rootfs-write-probe")
    try:
        probe.write_text("forbidden", encoding="utf-8")
    except OSError as error:
        if error.errno not in {errno.EROFS, errno.EACCES, errno.EPERM}:
            raise
    else:
        probe.unlink(missing_ok=True)
        raise RuntimeError("root filesystem is writable")


def browser_processes() -> list[int]:
    result: list[int] = []
    for candidate in Path("/proc").iterdir():
        if not candidate.name.isdigit():
            continue
        try:
            command = (candidate / "cmdline").read_bytes().replace(b"\0", b" ").decode()
        except (OSError, UnicodeDecodeError):
            continue
        if "/opt/browser-r1c/chromium-1234/chrome-linux64/chrome" in command:
            result.append(int(candidate.name))
    return sorted(result)


def wait_for_browser_exit() -> list[int]:
    deadline = time.monotonic() + 5
    remaining = browser_processes()
    while remaining and time.monotonic() < deadline:
        time.sleep(0.05)
        remaining = browser_processes()
    return remaining


def assert_controlled_path(path: Path) -> None:
    if path.parent != TMP_ROOT or path == TMP_ROOT or path.exists():
        raise RuntimeError(f"unsafe or pre-existing runtime path: {path}")
    if TMP_ROOT.resolve(strict=True) != TMP_ROOT:
        raise RuntimeError("runtime tmpfs root does not resolve to /tmp")


def prepare_runtime_directories(profile: Path) -> dict[str, bool]:
    paths = (HOME_DIR, CONFIG_DIR, CACHE_DIR, profile)
    absent_before = {str(path): not path.exists() for path in paths}
    for path in paths:
        assert_controlled_path(path)
        path.mkdir(mode=0o700)
        stat = path.lstat()
        if (
            path.is_symlink()
            or path.resolve(strict=True).parent != TMP_ROOT
            or stat.st_uid != 10001
            or stat.st_gid != 10001
            or stat.st_mode & 0o777 != 0o700
        ):
            raise RuntimeError(f"unsafe runtime directory identity: {path}")
    return absent_before


def cleanup_runtime_directories(profile: Path) -> dict[str, bool]:
    paths = (profile, CACHE_DIR, CONFIG_DIR, HOME_DIR)
    for path in paths:
        if path.is_symlink():
            raise RuntimeError(f"refusing to clean symlink runtime path: {path}")
        if path.exists():
            shutil.rmtree(path)
    absent_after = {str(path): not path.exists() for path in paths}
    if not all(absent_after.values()):
        raise RuntimeError("runtime directory cleanup failed")
    return absent_after


def capture_crashpad_database(profile: Path) -> dict[str, object]:
    roots = (HOME_DIR, CONFIG_DIR, CACHE_DIR, profile)
    candidates: list[Path] = []
    for root in roots:
        for path in root.rglob("*"):
            if path.is_symlink():
                raise RuntimeError(f"runtime created a symlink: {path}")
            if path.is_dir() and path.name == "Crash Reports":
                candidates.append(path)
    if len(candidates) != 1:
        raise RuntimeError(f"expected one Crashpad database, found: {candidates}")
    database = candidates[0]
    resolved = database.resolve(strict=True)
    controlled_roots = [root.resolve(strict=True) for root in roots]
    if not any(resolved.is_relative_to(root) for root in controlled_roots):
        raise RuntimeError(f"Crashpad database escaped controlled tmpfs: {database}")
    stat = database.lstat()
    mode = stat.st_mode & 0o777
    if stat.st_uid != 10001 or stat.st_gid != 10001 or mode & 0o077:
        raise RuntimeError(f"unsafe Crashpad database identity: {database}")
    return {
        "gid": stat.st_gid,
        "mode": f"{mode:04o}",
        "path": str(database),
        "uid": stat.st_uid,
    }


def main() -> None:
    if os.getuid() != 10001:
        raise RuntimeError("unexpected runtime uid")
    if {key: os.environ.get(key) for key in RUNTIME_ENV} != RUNTIME_ENV:
        raise RuntimeError("unexpected runtime HOME/XDG environment")
    assert_read_only_root()
    initial_processes = browser_processes()
    if initial_processes:
        raise RuntimeError(f"unexpected initial Browser processes: {initial_processes}")

    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    thread = Thread(target=server.serve_forever, name="r1c-fixture", daemon=True)
    thread.start()
    port = server.server_address[1]
    started = time.monotonic()
    render_absent_before = prepare_runtime_directories(RENDER_PROFILE)
    try:
        response = DynamicFetcher.fetch(
            f"http://127.0.0.1:{port}/deterministic",
            headless=True,
            disable_resources=False,
            google_search=False,
            network_idle=True,
            retries=1,
            timeout=8000,
            wait_selector="#result",
            extra_flags=["--disable-background-networking"],
            executable_path=EXECUTABLE,
            user_data_dir=str(RENDER_PROFILE),
        )
        remaining_after_render = wait_for_browser_exit()
        if remaining_after_render:
            raise RuntimeError(f"DynamicFetcher render left processes: {remaining_after_render}")
        render_crashpad = capture_crashpad_database(RENDER_PROFILE)
    finally:
        render_absent_after = cleanup_runtime_directories(RENDER_PROFILE)
    render_elapsed_ms = round((time.monotonic() - started) * 1000)
    rendered = response.css("#result::text").get()
    if rendered != "dynamic-rendered" or FixtureHandler.requests < 1:
        raise RuntimeError("DynamicFetcher deterministic render failed")

    server.shutdown()
    server.server_close()
    thread.join(timeout=2)
    if thread.is_alive():
        raise RuntimeError("in-process fixture did not terminate")

    failure_started = time.monotonic()
    failure_type = ""
    failure_absent_before = prepare_runtime_directories(FAILURE_PROFILE)
    try:
        try:
            DynamicFetcher.fetch(
                f"http://127.0.0.1:{port}/closed",
                headless=True,
                google_search=False,
                retries=1,
                timeout=2500,
                extra_flags=["--disable-background-networking"],
                executable_path=EXECUTABLE,
                user_data_dir=str(FAILURE_PROFILE),
            )
        except Exception as error:
            failure_type = type(error).__name__
        remaining_after_failure = wait_for_browser_exit()
        if remaining_after_failure:
            raise RuntimeError(f"DynamicFetcher failure left processes: {remaining_after_failure}")
        failure_crashpad = capture_crashpad_database(FAILURE_PROFILE)
    finally:
        failure_absent_after = cleanup_runtime_directories(FAILURE_PROFILE)
    if not failure_type:
        raise RuntimeError("DynamicFetcher closed fixture did not fail safely")
    if failure_type in {"TypeError", "ValidationError"}:
        raise RuntimeError(f"DynamicFetcher failed during argument validation: {failure_type}")
    failure_elapsed_ms = round((time.monotonic() - failure_started) * 1000)
    if failure_elapsed_ms >= 8000:
        raise RuntimeError("DynamicFetcher safe failure exceeded hard budget")

    print(
        json.dumps(
            {
                "browser_revision": 1234,
                "dynamic_fetcher": {
                    "call_contract": {
                        "executable_path": EXECUTABLE,
                        "failure": {
                            "headless": True,
                            "retries": 1,
                            "timeout": 2500,
                            "user_data_dir": str(FAILURE_PROFILE),
                        },
                        "render": {
                            "disable_resources": False,
                            "headless": True,
                            "network_idle": True,
                            "retries": 1,
                            "timeout": 8000,
                            "user_data_dir": str(RENDER_PROFILE),
                        },
                    },
                    "failure_elapsed_ms": failure_elapsed_ms,
                    "failure_type": failure_type,
                    "crashpad_databases": {
                        "failure": failure_crashpad,
                        "render": render_crashpad,
                    },
                    "fixture_requests": FixtureHandler.requests,
                    "fixture_scope": "in-process-loopback",
                    "render_elapsed_ms": render_elapsed_ms,
                    "rendered": rendered,
                    "runtime_directories_absent_after": {
                        "failure": failure_absent_after,
                        "render": render_absent_after,
                    },
                    "runtime_directories_absent_before": {
                        "failure": failure_absent_before,
                        "render": render_absent_before,
                    },
                    "runtime_environment": RUNTIME_ENV,
                    "terminal_browser_processes": [],
                    "terminal_fixture_thread": "stopped",
                },
                "engine_channel": "chromium",
                "engine_version": "151.0.7922.34",
                "executable": "/opt/browser-r1c/chromium-1234/chrome-linux64/chrome",
                "network": "none",
                "read_only_rootfs": True,
                "uid": os.getuid(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
