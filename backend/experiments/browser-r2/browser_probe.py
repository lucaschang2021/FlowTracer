from __future__ import annotations

import errno
import json
import os
import socket
from pathlib import Path
from urllib.parse import urlsplit

PROXY = ("198.51.100.20", 18080)
REDIS = ("198.51.100.30", 6379)


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


def _connect(host: str, port: int, path: str | None = None) -> tuple[int, bytes]:
    with _must_connect(PROXY) as connection:
        request = f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n"
        connection.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            response += connection.recv(4096)
        status = int(response.split(b" ", 2)[1])
        if status != 200 or path is None:
            return status, response
        connection.sendall(
            f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode()
        )
        body = b""
        while chunk := connection.recv(4096):
            body += chunk
        return status, body


def _redirect_target(response: bytes) -> tuple[str, int]:
    headers = response.split(b"\r\n\r\n", 1)[0].decode("ascii")
    location = next(
        line[10:].strip() for line in headers.split("\r\n") if line.lower().startswith("location:")
    )
    parsed = urlsplit(location)
    if parsed.scheme != "https" or parsed.hostname is None or parsed.port is None:
        raise RuntimeError("fixture redirect is invalid")
    return parsed.hostname, parsed.port


def main() -> None:
    if os.getuid() != 10001:
        raise RuntimeError("unexpected browser namespace uid")
    resolv_conf = Path("/etc/resolv.conf").read_text(encoding="utf-8")
    nameservers = {
        line.split()[1]
        for line in resolv_conf.splitlines()
        if line.startswith("nameserver ") and len(line.split()) >= 2
    }
    if not nameservers or not nameservers <= {"127.0.0.11", "198.51.100.40"}:
        raise RuntimeError("browser namespace DNS is not controlled")
    try:
        socket.getaddrinfo("fixture-r2.test", 8443)
    except socket.gaierror:
        pass
    else:
        raise RuntimeError("browser namespace resolved a target directly")
    with _must_connect(REDIS) as redis:
        redis.sendall(b"*1\r\n$4\r\nPING\r\n")
        if b"PONG" not in redis.recv(64):
            raise RuntimeError("declared Redis did not answer")
    status, response = _connect("fixture-r2.test", 8443, "/ok")
    if status != 200 or b"\r\n\r\nok" not in response:
        raise RuntimeError("allowed CONNECT fixture path failed")
    _, safe_redirect = _connect("fixture-r2.test", 8443, "/redirect-safe")
    if _connect(*_redirect_target(safe_redirect))[0] != 200:
        raise RuntimeError("safe redirect target was not revalidated")
    _, unsafe_redirect = _connect("fixture-r2.test", 8443, "/redirect-unsafe")
    if _connect(*_redirect_target(unsafe_redirect))[0] != 403:
        raise RuntimeError("unsafe redirect target was allowed")
    denied_hosts = (
        "rebind-r2.test",
        "mixed-r2.test",
        "loopback-r2.test",
        "private-r2.test",
        "linklocal-r2.test",
        "metadata-r2.test",
        "multicast-r2.test",
        "reserved-r2.test",
        "unspecified-r2.test",
        "undeclared-r2.test",
    )
    for host in denied_hosts:
        if _connect(host, 8443)[0] != 403:
            raise RuntimeError(f"unsafe target allowed: {host}")
    if _connect("fixture-r2.test", 22)[0] != 403:
        raise RuntimeError("dangerous port allowed")
    if _connect("192.0.2.10", 8443)[0] != 403:
        raise RuntimeError("direct IP through proxy allowed")
    with _must_connect(PROXY) as proxy:
        proxy.sendall(b"GET http://fixture-r2.test/ HTTP/1.1\r\nHost: fixture-r2.test\r\n\r\n")
        if b" 405 " not in proxy.recv(256):
            raise RuntimeError("proxy bypass method allowed")
    host_canary_ip = socket.gethostbyname("host-canary-r2.test")
    network_denials = []
    for address in (
        ("192.0.2.10", 8443),
        ("192.0.2.30", 9090),
        (host_canary_ip, 49175),
        ("203.0.113.10", 49175),
    ):
        network_denials.append(_must_not_connect(address))
    if Path("/var/run/docker.sock").exists():
        raise RuntimeError("Docker socket is present")
    print(
        json.dumps(
            {
                "allowed": ["proxy", "redis", "fixture_via_connect"],
                "connect_revalidations": 3,
                "denied_policy_cases": len(denied_hosts) + 3,
                "direct_network_denials": 4,
                "direct_network_results": network_denials,
                "docker_socket": "absent",
                "host_gateway_endpoint": {"address": host_canary_ip, "port": 49175},
                "system_dns": "authoritative_nxdomain",
                "uid": os.getuid(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
