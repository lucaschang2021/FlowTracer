from __future__ import annotations

import errno
import json
import os
import shutil
import socket
import time
from pathlib import Path

from scrapling.fetchers import DynamicFetcher

PROXY_ADDRESS = ("198.51.100.20", 18080)
PROXY_URL = "http://198.51.100.20:18080"
REDIS = ("198.51.100.30", 6379)
EXECUTABLE = "/opt/browser-r1c/chromium-1234/chrome-linux64/chrome"
TMP_ROOT = Path("/tmp")  # noqa: S108 - dedicated container tmpfs
HOME_DIR = TMP_ROOT / "flowtracer-r2c-home"
CONFIG_DIR = TMP_ROOT / "flowtracer-r2c-config"
CACHE_DIR = TMP_ROOT / "flowtracer-r2c-cache"
PROFILES = {
    "dynamic": TMP_ROOT / "flowtracer-r2c-dynamic-profile",
    "redirect": TMP_ROOT / "flowtracer-r2c-redirect-profile",
    "failure": TMP_ROOT / "flowtracer-r2c-failure-profile",
}
RUNTIME_ENV = {
    "HOME": str(HOME_DIR),
    "XDG_CONFIG_HOME": str(CONFIG_DIR),
    "XDG_CACHE_HOME": str(CACHE_DIR),
}


def _must_connect(address: tuple[str, int]) -> socket.socket:
    return socket.create_connection(address, timeout=2)


def _must_not_connect(address: tuple[str, int]) -> dict[str, object]:
    try:
        connection = socket.create_connection(address, timeout=1)
    except OSError as error:
        if error.errno != errno.ENETUNREACH:
            raise RuntimeError(
                f"inconclusive network denial for {address[0]}:{address[1]}: errno={error.errno}"
            ) from error
        return {
            "address": address[0],
            "errno": error.errno,
            "outcome": "unreachable",
            "port": address[1],
        }
    connection.close()
    raise RuntimeError(f"unexpected direct connection to {address[0]}:{address[1]}")


def _connect_status(host: str, port: int) -> int:
    with _must_connect(PROXY_ADDRESS) as connection:
        request = f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n"
        connection.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response and len(response) < 8192:
            chunk = connection.recv(4096)
            if not chunk:
                break
            response += chunk
        return int(response.split(b" ", 2)[1])


def _absolute_form_status() -> int:
    with _must_connect(PROXY_ADDRESS) as connection:
        connection.sendall(
            b"GET http://fixture-r2c.test:8443/ HTTP/1.1\r\n"
            b"Host: fixture-r2c.test\r\nConnection: close\r\n\r\n"
        )
        response = connection.recv(256)
    return int(response.split(b" ", 2)[1])


def _browser_processes() -> list[int]:
    result: list[int] = []
    for candidate in Path("/proc").iterdir():
        if not candidate.name.isdigit():
            continue
        try:
            command = (candidate / "cmdline").read_bytes().replace(b"\0", b" ").decode()
        except (OSError, UnicodeDecodeError):
            continue
        if EXECUTABLE in command:
            result.append(int(candidate.name))
    return sorted(result)


def _wait_for_browser_exit() -> list[int]:
    deadline = time.monotonic() + 5
    remaining = _browser_processes()
    while remaining and time.monotonic() < deadline:
        time.sleep(0.05)
        remaining = _browser_processes()
    return remaining


def _assert_read_only_root() -> None:
    probe = Path("/r2c-rootfs-write-probe")
    try:
        probe.write_text("forbidden", encoding="utf-8")
    except OSError as error:
        if error.errno not in {errno.EROFS, errno.EACCES, errno.EPERM}:
            raise
    else:
        probe.unlink(missing_ok=True)
        raise RuntimeError("root filesystem is writable")


def _prepare(profile: Path) -> dict[str, bool]:
    paths = (HOME_DIR, CONFIG_DIR, CACHE_DIR, profile)
    before = {str(path): not path.exists() for path in paths}
    if not all(before.values()) or TMP_ROOT.resolve(strict=True) != TMP_ROOT:
        raise RuntimeError("runtime paths pre-exist or tmpfs root is unsafe")
    for path in paths:
        if path.parent != TMP_ROOT:
            raise RuntimeError(f"runtime path escaped tmpfs: {path}")
        path.mkdir(mode=0o700)
        info = path.lstat()
        if (
            path.is_symlink()
            or path.resolve(strict=True).parent != TMP_ROOT
            or info.st_uid != 10001
            or info.st_gid != 10001
            or info.st_mode & 0o777 != 0o700
        ):
            raise RuntimeError(f"unsafe runtime directory identity: {path}")
    return before


def _crashpad(profile: Path) -> dict[str, object]:
    candidates: list[Path] = []
    for root in (HOME_DIR, CONFIG_DIR, CACHE_DIR, profile):
        for path in root.rglob("*"):
            if path.is_symlink():
                raise RuntimeError(f"runtime created a symlink: {path}")
            if path.is_dir() and path.name == "Crash Reports":
                candidates.append(path)
    if len(candidates) != 1:
        raise RuntimeError(f"expected one Crashpad database, found {candidates}")
    value = candidates[0]
    info = value.lstat()
    if info.st_uid != 10001 or info.st_gid != 10001 or info.st_mode & 0o077:
        raise RuntimeError("unsafe Crashpad database identity")
    return {
        "gid": info.st_gid,
        "mode": f"{info.st_mode & 0o777:04o}",
        "path": str(value),
        "uid": info.st_uid,
    }


def _cleanup(profile: Path) -> dict[str, bool]:
    paths = (profile, CACHE_DIR, CONFIG_DIR, HOME_DIR)
    for path in paths:
        if path.is_symlink():
            raise RuntimeError(f"refusing to clean symlink runtime path: {path}")
        if path.exists():
            shutil.rmtree(path)
    result = {str(path): not path.exists() for path in paths}
    if not all(result.values()):
        raise RuntimeError("runtime directory cleanup failed")
    return result


def _dynamic_fetch(
    name: str, url: str, selector: str, expected: str
) -> dict[str, object]:
    profile = PROFILES[name]
    before = _prepare(profile)
    started = time.monotonic()
    try:
        response = DynamicFetcher.fetch(
            url,
            headless=True,
            proxy=PROXY_URL,
            retries=1,
            timeout=8000,
            wait_selector=selector,
            google_search=False,
            disable_resources=False,
            network_idle=True,
            executable_path=EXECUTABLE,
            user_data_dir=str(profile),
            additional_args={"ignore_https_errors": True},
            extra_flags=[
                "--ignore-certificate-errors",
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-sync",
            ],
        )
        remaining = _wait_for_browser_exit()
        if remaining:
            raise RuntimeError(f"DynamicFetcher left browser processes: {remaining}")
        crashpad = _crashpad(profile)
        rendered = response.css(f"{selector}::text").get()
        if rendered != expected:
            raise RuntimeError(f"unexpected DynamicFetcher render: {rendered!r}")
    finally:
        after = _cleanup(profile)
    return {
        "crashpad_database": crashpad,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "rendered": rendered,
        "runtime_directories_absent_after": after,
        "runtime_directories_absent_before": before,
        "terminal_browser_processes": [],
    }


def _safe_failure() -> dict[str, object]:
    profile = PROFILES["failure"]
    before = _prepare(profile)
    started = time.monotonic()
    failure_type = ""
    crashpad: dict[str, object] | None = None
    try:
        try:
            DynamicFetcher.fetch(
                "https://metadata-r2c.test:8443/blocked",
                headless=True,
                proxy=PROXY_URL,
                retries=1,
                timeout=3000,
                google_search=False,
                executable_path=EXECUTABLE,
                user_data_dir=str(profile),
                additional_args={"ignore_https_errors": True},
                extra_flags=[
                    "--ignore-certificate-errors",
                    "--disable-background-networking",
                ],
            )
        except Exception as error:
            failure_type = type(error).__name__
        if not failure_type:
            raise RuntimeError("unsafe DynamicFetcher target did not fail")
        remaining = _wait_for_browser_exit()
        if remaining:
            raise RuntimeError(f"failure path left browser processes: {remaining}")
        crashpad = _crashpad(profile)
    finally:
        after = _cleanup(profile)
    return {
        "crashpad_database": crashpad,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "failure_type": failure_type,
        "runtime_directories_absent_after": after,
        "runtime_directories_absent_before": before,
        "terminal_browser_processes": [],
    }


def main() -> None:
    if os.getuid() != 10001:
        raise RuntimeError("unexpected browser namespace uid")
    if {key: os.environ.get(key) for key in RUNTIME_ENV} != RUNTIME_ENV:
        raise RuntimeError("unexpected runtime HOME/XDG environment")
    _assert_read_only_root()
    if _browser_processes():
        raise RuntimeError("unexpected initial browser processes")

    resolvers = {
        line.split()[1]
        for line in Path("/etc/resolv.conf").read_text(encoding="utf-8").splitlines()
        if line.startswith("nameserver ") and len(line.split()) >= 2
    }
    if not resolvers or not resolvers <= {"127.0.0.11", "198.51.100.40"}:
        raise RuntimeError("browser namespace DNS is not controlled")
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.getaddrinfo("fixture-r2c.test", 8443, family)
        except socket.gaierror:
            pass
        else:
            raise RuntimeError("browser namespace resolved a target directly")

    with _must_connect(REDIS) as redis:
        redis.sendall(b"*1\r\n$4\r\nPING\r\n")
        if b"PONG" not in redis.recv(64):
            raise RuntimeError("declared Redis did not answer")

    denied_hosts = (
        "rebind-r2c.test",
        "mixed-r2c.test",
        "loopback-r2c.test",
        "private-r2c.test",
        "linklocal-r2c.test",
        "metadata-r2c.test",
        "multicast-r2c.test",
        "reserved-r2c.test",
        "unspecified-r2c.test",
        "undeclared-r2c.test",
    )
    denial_statuses = {host: _connect_status(host, 8443) for host in denied_hosts}
    if set(denial_statuses.values()) != {403}:
        raise RuntimeError(f"unsafe target allowed: {denial_statuses}")
    extra_denials = {
        "dangerous_port": _connect_status("fixture-r2c.test", 22),
        "direct_ip": _connect_status("192.0.2.10", 8443),
        "unknown_host": _connect_status("unknown-r2c.test", 8443),
        "absolute_form": _absolute_form_status(),
    }
    if extra_denials != {
        "dangerous_port": 403,
        "direct_ip": 403,
        "unknown_host": 403,
        "absolute_form": 405,
    }:
        raise RuntimeError(f"proxy bypass matrix failed: {extra_denials}")

    host_gateway_ip = socket.gethostbyname("host-canary-r2c.test")
    direct = [
        _must_not_connect(address)
        for address in (
            ("192.0.2.10", 8443),
            ("192.0.2.30", 9090),
            (host_gateway_ip, 49263),
            ("203.0.113.10", 49263),
        )
    ]
    if Path("/var/run/docker.sock").exists():
        raise RuntimeError("Docker socket is present")

    dynamic = _dynamic_fetch(
        "dynamic",
        "https://dynamic-r2c.test:8443/dynamic",
        "#dynamic-result",
        "dynamic-rendered",
    )
    redirect = _dynamic_fetch(
        "redirect",
        "https://redirect-r2c.test:8443/start",
        "#redirect-result",
        "redirect-rendered",
    )
    failure = _safe_failure()

    print(
        json.dumps(
            {
                "call_contract": {
                    "executable_path": EXECUTABLE,
                    "proxy": PROXY_URL,
                    "retries": 1,
                },
                "declared_redis": "PONG",
                "direct_network_results": direct,
                "docker_socket": "absent",
                "dynamic_fetcher": dynamic,
                "failure": failure,
                "host_gateway_endpoint": {"address": host_gateway_ip, "port": 49263},
                "proxy_denials": {**denial_statuses, **extra_denials},
                "read_only_rootfs": True,
                "redirect": redirect,
                "runtime_environment": RUNTIME_ENV,
                "system_dns": "authoritative_nxdomain_a_aaaa",
                "terminal_browser_processes": _browser_processes(),
                "uid": os.getuid(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
