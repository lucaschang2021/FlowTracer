from __future__ import annotations

import json
import os
import socketserver
import struct
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

EVENTS_PATH = Path(os.environ.get("R2C_DNS_EVENTS", "/evidence/dns-events.jsonl"))
_event_lock = Lock()


def _question(packet: bytes) -> tuple[str, str]:
    labels: list[str] = []
    offset = 12
    while offset < len(packet):
        length = packet[offset]
        offset += 1
        if length == 0:
            if offset + 2 > len(packet):
                raise ValueError("truncated DNS question type")
            query_type = struct.unpack("!H", packet[offset : offset + 2])[0]
            return ".".join(labels).lower(), {1: "A", 28: "AAAA"}.get(
                query_type, f"TYPE{query_type}"
            )
        if length > 63 or offset + length > len(packet):
            raise ValueError("invalid DNS question")
        labels.append(packet[offset : offset + length].decode("ascii"))
        offset += length
    raise ValueError("truncated DNS question")


def _nxdomain(packet: bytes) -> bytes:
    if len(packet) < 12:
        raise ValueError("truncated DNS packet")
    # QR=1, AA=1, RD preserved, RA=0, RCODE=NXDOMAIN.
    return packet[:2] + b"\x85\x03" + packet[4:6] + b"\x00\x00\x00\x00\x00\x00" + packet[12:]


def _record(name: str, query_type: str) -> None:
    event = {
        "authoritative": True,
        "decision": "nxdomain",
        "name": name,
        "occurred_at": datetime.now(UTC).isoformat(),
        "qtype": query_type,
        "recursion_available": False,
        "source": "browser-system-resolver",
        "upstream_queries": 0,
    }
    with _event_lock:
        with EVENTS_PATH.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, sort_keys=True) + "\n")


class UDPHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        packet, connection = self.request
        try:
            name, query_type = _question(packet)
            response = _nxdomain(packet)
        except ValueError:
            return
        _record(name, query_type)
        connection.sendto(response, self.client_address)


class TCPHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        length_data = self.rfile.read(2)
        if len(length_data) != 2:
            return
        packet = self.rfile.read(struct.unpack("!H", length_data)[0])
        try:
            name, query_type = _question(packet)
            response = _nxdomain(packet)
        except ValueError:
            return
        _record(name, query_type)
        self.wfile.write(struct.pack("!H", len(response)) + response)


class ThreadedUDPServer(socketserver.ThreadingUDPServer):
    daemon_threads = True


class ThreadedTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    import threading

    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    udp_server = ThreadedUDPServer(("0.0.0.0", 53), UDPHandler)  # noqa: S104
    tcp_server = ThreadedTCPServer(("0.0.0.0", 53), TCPHandler)  # noqa: S104
    threading.Thread(target=tcp_server.serve_forever, daemon=True).start()
    udp_server.serve_forever()
