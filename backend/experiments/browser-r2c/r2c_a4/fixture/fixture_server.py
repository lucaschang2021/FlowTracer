from __future__ import annotations

import json
import os
import ssl
import subprocess
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

EVENTS_PATH = Path(os.environ.get("R2C_FIXTURE_EVENTS", "/evidence/fixture-events.jsonl"))
CERT = Path("/tmp/r2c-fixture.crt")  # noqa: S108 - dedicated container tmpfs
KEY = Path("/tmp/r2c-fixture.key")  # noqa: S108 - dedicated container tmpfs
_event_lock = Lock()


def _record(handler: BaseHTTPRequestHandler) -> None:
    event = {
        "host": handler.headers.get("Host", "").split(":", 1)[0].lower(),
        "method": handler.command,
        "occurred_at": datetime.now(UTC).isoformat(),
        "path": handler.path.split("?", 1)[0],
    }
    with _event_lock:
        with EVENTS_PATH.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, sort_keys=True) + "\n")


class FixtureHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        _record(self)
        host = self.headers.get("Host", "").split(":", 1)[0].lower()
        path = self.path.split("?", 1)[0]
        if host == "redirect-r2c.test" and path == "/start":
            self.send_response(302)
            self.send_header("Location", "https://redirect-target-r2c.test:8443/final")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if host == "redirect-target-r2c.test":
            self._send(
                200,
                b"<title>r2c-redirect</title><main id='redirect-result'>redirect-rendered</main>",
                "text/html; charset=utf-8",
            )
            return
        if host == "dynamic-r2c.test":
            self._send(
                200,
                b"<title>r2c-dynamic</title><main id='dynamic-result'>dynamic-rendered</main>",
                "text/html; charset=utf-8",
            )
            return
        self._send(200, b"ok", "text/plain; charset=utf-8")

    def log_message(self, _format: str, *_args: object) -> None:
        return


def _create_certificate() -> None:
    subprocess.run(  # noqa: S603 - fixed image-local executable and arguments
        [
            "/usr/bin/openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=fixture-r2c.test",
            "-keyout",
            str(KEY),
            "-out",
            str(CERT),
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )


if __name__ == "__main__":
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _create_certificate()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(CERT, KEY)
    server = ThreadingHTTPServer(("0.0.0.0", 8443), FixtureHandler)  # noqa: S104
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()
