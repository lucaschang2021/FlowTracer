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
EVENTS_PATH = Path(os.environ.get("R2_PROXY_EVENTS", "/evidence/proxy-events.jsonl"))

TARGET_ANSWERS: dict[str, tuple[tuple[str, ...], ...]] = {
    "fixture-r2.test": ((FIXTURE_IP,), (FIXTURE_IP,)),
    "rebind-r2.test": ((FIXTURE_IP,), ("169.254.169.254",)),
    "mixed-r2.test": ((FIXTURE_IP, "fe80::1"),),
    "loopback-r2.test": (("127.0.0.1",),),
    "private-r2.test": (("10.0.0.8",),),
    "linklocal-r2.test": (("169.254.1.8",),),
    "metadata-r2.test": (("169.254.169.254",),),
    "multicast-r2.test": (("224.0.0.1",),),
    "reserved-r2.test": (("240.0.0.8",),),
    "unspecified-r2.test": (("0.0.0.0",),),  # noqa: S104 - denial fixture
    "undeclared-r2.test": (("93.184.216.34",),),
}

_event_lock = Lock()


def _record(*, host: str, port: int, decision: str, reason: str, answers: tuple[str, ...]) -> None:
    event = {
        "answers": list(answers),
        "decision": decision,
        "host": host,
        "occurred_at": datetime.now(UTC).isoformat(),
        "port": port,
        "reason": reason,
    }
    with _event_lock:
        with EVENTS_PATH.open("a", encoding="utf-8") as stream:
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


def _resolve(host: str, pass_number: int) -> tuple[str, ...]:
    answers = TARGET_ANSWERS.get(host)
    if answers is None:
        return ()
    return answers[min(pass_number, len(answers) - 1)]


def _validated_target(host: str, port: int) -> tuple[str | None, str, tuple[str, ...]]:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return None, "direct_ip", ()
    if port != FIXTURE_PORT:
        return None, "dangerous_port", ()
    first = _resolve(host, 0)
    if not first:
        return None, "undeclared_host", ()
    unsafe_reasons = [reason for answer in first if (reason := _address_reason(answer))]
    if unsafe_reasons:
        return None, "mixed_answer" if len(first) > 1 else unsafe_reasons[0], first
    second = _resolve(host, 1)
    if set(first) != set(second):
        return None, "dns_rebinding", (*first, *second)
    for answer in second:
        reason = _address_reason(answer)
        if reason is not None:
            return None, reason, second
    return second[0], "validated", second


def _relay(client: socket.socket, upstream: socket.socket) -> None:
    selector = selectors.DefaultSelector()
    selector.register(client, selectors.EVENT_READ, upstream)
    selector.register(upstream, selectors.EVENT_READ, client)
    try:
        while selector.get_map():
            for key, _mask in selector.select(timeout=5):
                source = key.fileobj
                destination = key.data
                data = source.recv(65536)
                if not data:
                    return
                destination.sendall(data)
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
            _record(host="invalid", port=0, decision="deny", reason="connect_required", answers=())
            return
        authority = parts[1]
        try:
            host, raw_port = authority.rsplit(":", 1)
            port = int(raw_port)
        except (ValueError, TypeError):
            self.wfile.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            _record(host="invalid", port=0, decision="deny", reason="invalid_authority", answers=())
            return
        final_ip, reason, answers = _validated_target(host.lower().rstrip("."), port)
        if final_ip is None:
            self.wfile.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
            _record(host=host, port=port, decision="deny", reason=reason, answers=answers)
            return
        try:
            upstream = socket.create_connection((final_ip, port), timeout=3)
            peer_ip = upstream.getpeername()[0]
            if peer_ip not in answers or peer_ip != FIXTURE_IP:
                upstream.close()
                raise RuntimeError("final_ip_mismatch")
        except (OSError, RuntimeError):
            self.wfile.write(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n")
            _record(
                host=host, port=port, decision="deny", reason="final_ip_mismatch", answers=answers
            )
            return
        _record(host=host, port=port, decision="allow", reason=reason, answers=answers)
        self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        self.wfile.flush()
        with upstream:
            _relay(self.connection, upstream)


class ThreadedProxy(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Container has only the two internal R2 networks and publishes no port.
    with ThreadedProxy(("0.0.0.0", PROXY_PORT), ProxyHandler) as server:  # noqa: S104
        server.serve_forever()
