"""Deny-only plain WS audit adapter; accepted CONNECT policy remains independent."""

from __future__ import annotations

import hashlib
import io
import json
import re
from urllib.parse import urlsplit


def denied_request(raw: bytes, phase: str) -> dict:
    if phase not in {"baseline", "enabled"}:
        raise ValueError("operator_phase_invalid")
    result = {
        "method": None,
        "host": None,
        "port": None,
        "fingerprint": None,
        "phase": phase,
        "decision": "deny",
        "status": 405,
        "reason": "request_invalid",
        "upstream_bytes": 0,
        "relay_bytes": 0,
    }
    if len(raw) > 16384 or not raw.endswith(b"\r\n\r\n"):
        return result
    try:
        lines = raw.decode("ascii", "strict").split("\r\n")
        parts = lines[0].split(" ")
        if len(parts) != 3 or not re.fullmatch(r"[A-Z]{1,16}", parts[0]):
            return result
        result["method"] = parts[0]
        if parts[2] not in {"HTTP/1.0", "HTTP/1.1"}:
            return result
        headers = {}
        if len(lines) > 67:
            return result
        for line in lines[1:-2]:
            if not line or len(line) > 4096 or line[0].isspace() or ":" not in line:
                return result
            key, value = line.split(":", 1)
            if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", key) or key.lower() in headers:
                return result
            value = value.strip()
            if any(ord(char) < 32 or ord(char) == 127 for char in value):
                return result
            headers[key.lower()] = value
        if parts[0] != "GET":
            result["reason"] = "connect_required"
            return result
        url = urlsplit(parts[1])
        if (
            url.scheme not in {"http", "ws"}
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.hostname != "websocket-r3.test"
            or url.port != 8443
            or not re.fullmatch(r"/dnr-(page|worker)-ws", url.path)
            or headers.get("host", "").lower() != "websocket-r3.test:8443"
            or headers.get("upgrade", "").lower() != "websocket"
            or headers.get("connection", "").lower() != "upgrade"
        ):
            return result
        result.update(
            host="websocket-r3.test",
            port=8443,
            fingerprint=hashlib.sha256(
                f"ws://websocket-r3.test:8443{url.path}".encode()
            ).hexdigest(),
            reason="plain_ws_default_deny",
        )
    except (UnicodeError, ValueError):
        pass  # fixed denial, never export raw parser input/error
    return result


def read_headers(stream) -> bytes:
    chunks, total = [], 0
    for _ in range(66):
        line = stream.readline(4097)
        total += len(line)
        if len(line) > 4096 or total > 16384 or not line:
            return b""
        chunks.append(line)
        if line == b"\r\n":
            return b"".join(chunks)
    return b""


def valid_connect(raw: bytes) -> bool:
    if len(raw) > 16384 or not raw.endswith(b"\r\n\r\n"):
        return False
    try:
        lines = raw.decode("ascii", "strict").split("\r\n")
        match = re.fullmatch(r"CONNECT ([a-z0-9-]+(?:\.[a-z0-9-]+)*):8443 HTTP/1\.[01]", lines[0])
        if not match or len(lines) > 67:
            return False
        seen = set()
        for line in lines[1:-2]:
            if not line or len(line) > 4096 or line[0].isspace() or ":" not in line:
                return False
            key, value = line.split(":", 1)
            if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", key) or key.lower() in seen:
                return False
            seen.add(key.lower())
            if any(ord(char) < 32 or ord(char) == 127 for char in value):
                return False
            if key.lower() == "host" and value.strip() != match[1] + ":8443":
                return False
        return True
    except UnicodeError:
        return False


def handler_type(accepted, audit, phase: str):
    """accepted is the explicitly mounted tracked R2C-A4 module, not r3_a2.

    Only controlled navigation host joins the accepted fixed-fixture target map.
    WS host remains absent/denied, so CONNECT retains independent 403 behavior.
    """
    if phase not in {"baseline", "enabled"}:
        raise ValueError("operator_phase_invalid")
    accepted.TARGET_ANSWERS["navigation-r3.test"] = (
        {"A": ("192.0.2.10",), "AAAA": ()},
        {"A": ("192.0.2.10",), "AAAA": ()},
    )

    class Handler(accepted.ProxyHandler):
        def handle(self):
            self.request.settimeout(2)
            raw = read_headers(self.rfile)
            # Validated bounded CONNECT syntax/authority only; delegation preserves
            # accepted double-pass/peer validation. Other methods never delegate.
            first = raw.split(b"\r\n", 1)[0]
            match = re.fullmatch(rb"CONNECT ([a-z0-9-]+(?:\.[a-z0-9-]+)*):8443 HTTP/1\.[01]", first)
            if match and valid_connect(raw):
                if match[1] == b"websocket-r3.test":
                    audit(
                        {
                            "method": "CONNECT",
                            "host": "websocket-r3.test",
                            "port": 8443,
                            "fingerprint": None,
                            "phase": phase,
                            "decision": "deny",
                            "status": 403,
                            "reason": "ws_connect_default_deny",
                            "upstream_bytes": 0,
                            "relay_bytes": 0,
                        }
                    )
                    self.wfile.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
                    self.wfile.flush()
                    return
                original = self.rfile
                try:
                    self.rfile = io.BytesIO(raw)
                    super().handle()
                finally:
                    self.rfile = original
                return
            audit(denied_request(raw, phase))
            self.wfile.write(b"HTTP/1.1 405 Method Not Allowed\r\nConnection: close\r\n\r\n")
            self.wfile.flush()

    return Handler


def serve(phase: str, audit):
    # No serve/main call is authorized in OFFLINE ONLY; no test calls this.
    import socketserver

    import accepted_proxy

    with socketserver.ThreadingTCPServer(
        ("0.0.0.0", 18080),  # noqa: S104 - isolated internal namespaces, no host ports
        handler_type(accepted_proxy, audit, phase),
    ) as server:
        server.serve_forever()


def safe_json(event: dict) -> str:
    return json.dumps(event, sort_keys=True, allow_nan=False)
