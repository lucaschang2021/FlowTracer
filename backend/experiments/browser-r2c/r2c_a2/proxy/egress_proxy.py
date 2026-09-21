from __future__ import annotations

import ipaddress
import json
import os
import selectors
import socket
import socketserver
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

PROXY_PORT = 18080
FIXTURE_PORT = 8443
FIXTURE_IP = "192.0.2.10"
EVENTS_PATH = Path(os.environ.get("R2C_PROXY_EVENTS", "/evidence/proxy-events.jsonl"))

# Every declared host has two deterministic resolution passes. A and AAAA are
# explicit even when one family is empty, proving both families were inspected.
Resolution = dict[str, tuple[str, ...]]
TARGET_ANSWERS: dict[str, tuple[Resolution, Resolution]] = {
    host: (
        {"A": (FIXTURE_IP,), "AAAA": ()},
        {"A": (FIXTURE_IP,), "AAAA": ()},
    )
    for host in (
        "dynamic-r2c.test",
        "fixture-r2c.test",
        "redirect-r2c.test",
        "redirect-target-r2c.test",
    )
}
TARGET_ANSWERS.update(
    {
        "rebind-r2c.test": (
            {"A": (FIXTURE_IP,), "AAAA": ()},
            {"A": ("169.254.169.254",), "AAAA": ()},
        ),
        "mixed-r2c.test": (
            {"A": (FIXTURE_IP,), "AAAA": ("fe80::1",)},
            {"A": (FIXTURE_IP,), "AAAA": ("fe80::1",)},
        ),
        "loopback-r2c.test": (
            {"A": ("127.0.0.1",), "AAAA": ("::1",)},
            {"A": ("127.0.0.1",), "AAAA": ("::1",)},
        ),
        "private-r2c.test": (
            {"A": ("10.0.0.8",), "AAAA": ("fd00::8",)},
            {"A": ("10.0.0.8",), "AAAA": ("fd00::8",)},
        ),
        "linklocal-r2c.test": (
            {"A": ("169.254.1.8",), "AAAA": ("fe80::8",)},
            {"A": ("169.254.1.8",), "AAAA": ("fe80::8",)},
        ),
        "metadata-r2c.test": (
            {"A": ("169.254.169.254",), "AAAA": ()},
            {"A": ("169.254.169.254",), "AAAA": ()},
        ),
        "multicast-r2c.test": (
            {"A": ("224.0.0.1",), "AAAA": ("ff02::1",)},
            {"A": ("224.0.0.1",), "AAAA": ("ff02::1",)},
        ),
        "reserved-r2c.test": (
            {"A": ("240.0.0.8",), "AAAA": ()},
            {"A": ("240.0.0.8",), "AAAA": ()},
        ),
        "unspecified-r2c.test": (
            {"A": ("0.0.0.0",), "AAAA": ("::",)},  # noqa: S104 - denial fixture
            {"A": ("0.0.0.0",), "AAAA": ("::",)},  # noqa: S104 - denial fixture
        ),
        "undeclared-r2c.test": (
            {
                "A": ("198.51.100.99",),
                "AAAA": ("2001:db8::99",),
            },
            {
                "A": ("198.51.100.99",),
                "AAAA": ("2001:db8::99",),
            },
        ),
    }
)

_event_lock = Lock()


def _record(
    *,
    host: str,
    port: int,
    decision: str,
    reason: str,
    passes: tuple[Resolution, ...] = (),
    peer_ip: str | None = None,
) -> None:
    event = {
        "decision": decision,
        "host": host,
        "occurred_at": datetime.now(UTC).isoformat(),
        "peer_ip": peer_ip,
        "port": port,
        "reason": reason,
        "resolution_passes": [
            {family: list(answers) for family, answers in sorted(resolution.items())}
            for resolution in passes
        ],
    }
    with _event_lock:
        with EVENTS_PATH.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, sort_keys=True) + "\n")


def _address_reason(value: str) -> str | None:
    address = ipaddress.ip_address(value)
    if value == FIXTURE_IP:
        return None
    if value == "169.254.169.254":
        return "metadata"
    if address.is_unspecified:
        return "unspecified"
    if address.is_loopback:
        return "loopback"
    if address.is_link_local:
        return "link_local"
    if address.is_multicast:
        return "multicast"
    if address.is_reserved:
        return "reserved"
    if address.is_private:
        return "private"
    return "not_declared_fixture"


def _all_answers(resolution: Resolution) -> tuple[str, ...]:
    return tuple(answer for family in ("A", "AAAA") for answer in resolution[family])


def _validated_target(
    host: str, port: int
) -> tuple[str | None, str, tuple[Resolution, ...]]:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return None, "direct_ip", ()
    if port != FIXTURE_PORT:
        return None, "dangerous_port", ()
    configured = TARGET_ANSWERS.get(host)
    if configured is None:
        return None, "undeclared_host", ()
    first, second = configured
    if host == "undeclared-r2c.test":
        return None, "not_declared_fixture", (first,)
    first_answers = _all_answers(first)
    unsafe = [reason for answer in first_answers if (reason := _address_reason(answer))]
    if unsafe:
        reason = (
            "mixed_answer"
            if any(_address_reason(value) is None for value in first_answers)
            else unsafe[0]
        )
        return None, reason, (first,)
    if first != second:
        return None, "dns_rebinding", (first, second)
    second_answers = _all_answers(second)
    unsafe = [reason for answer in second_answers if (reason := _address_reason(answer))]
    if unsafe:
        return None, unsafe[0], (first, second)
    if not first["A"]:
        return None, "no_ipv4_fixture", (first, second)
    return first["A"][0], "validated", (first, second)


def _relay(client: socket.socket, upstream: socket.socket) -> None:
    selector = selectors.DefaultSelector()
    selector.register(client, selectors.EVENT_READ, upstream)
    selector.register(upstream, selectors.EVENT_READ, client)
    try:
        while selector.get_map():
            ready = selector.select(timeout=10)
            if not ready:
                return
            for key, _mask in ready:
                data = key.fileobj.recv(65536)
                if not data:
                    return
                key.data.sendall(data)
    finally:
        selector.close()


class ProxyHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        request_line = self.rfile.readline(4096).decode("ascii", "replace").strip()
        while self.rfile.readline(4096) not in {b"\r\n", b"\n", b""}:
            pass
        parts = request_line.split()
        if len(parts) != 3 or parts[0] != "CONNECT":
            self.wfile.write(b"HTTP/1.1 405 Method Not Allowed\r\nConnection: close\r\n\r\n")
            _record(host="invalid", port=0, decision="deny", reason="connect_required")
            return
        try:
            host, raw_port = parts[1].rsplit(":", 1)
            host = host.lower().rstrip(".")
            port = int(raw_port)
        except (TypeError, ValueError):
            self.wfile.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            _record(host="invalid", port=0, decision="deny", reason="invalid_authority")
            return
        final_ip, reason, passes = _validated_target(host, port)
        if final_ip is None:
            self.wfile.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
            _record(host=host, port=port, decision="deny", reason=reason, passes=passes)
            return
        try:
            upstream = socket.create_connection((final_ip, port), timeout=3)
            peer_ip = upstream.getpeername()[0]
            allowed = set(_all_answers(passes[-1]))
            if peer_ip not in allowed or peer_ip != FIXTURE_IP:
                upstream.close()
                raise RuntimeError("final_peer_mismatch")
        except (OSError, RuntimeError):
            self.wfile.write(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n")
            _record(
                host=host,
                port=port,
                decision="deny",
                reason="final_peer_mismatch",
                passes=passes,
            )
            return
        _record(
            host=host,
            port=port,
            decision="allow",
            reason=reason,
            passes=passes,
            peer_ip=peer_ip,
        )
        self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        self.wfile.flush()
        with upstream:
            _relay(self.connection, upstream)


class ThreadedProxy(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ThreadedProxy(("0.0.0.0", PROXY_PORT), ProxyHandler) as server:  # noqa: S104
        server.serve_forever()
