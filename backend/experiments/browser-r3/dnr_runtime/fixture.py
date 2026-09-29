"""Single local navigation + HTTP(S) Dedicated Worker script, no WS upstream."""

from __future__ import annotations

import hashlib
import os
import ssl
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WORKER = """'use strict';
const nativeDateNow = Date.now.bind(Date);
self.onmessage = event => {
  if (event.data.kind === 'ping') {self.postMessage({kind:'pong'}); return;}
  if (event.data.kind !== 'start') return;
  const scheme = event.data.scheme;
  const start_ms = nativeDateNow();
  const socket = new WebSocket(scheme + '://websocket-r3.test:8443/dnr-worker-' + scheme);
  let ended = false;
  const finish = kind => {if (!ended) {ended=true;
    const terminal_ms = nativeDateNow();
    self.postMessage({kind, actor:'worker', scheme, start_ms, terminal_ms,
      end_ms:nativeDateNow(), timestamp_source:'controlled_fixture_native_date_now_epoch_ms'});}};
  const timer = setTimeout(() => finish('timeout'), 5000);
  socket.onopen = () => {clearTimeout(timer); finish('open'); socket.close();};
  socket.onerror = () => {clearTimeout(timer); finish('error');};
  socket.onclose = () => {clearTimeout(timer); finish('close');};
}; self.postMessage({kind:'ready'});
"""
PAGE = """<!doctype html><meta charset='utf-8'><title>R3 fixture</title><script>
const nativeDateNow = Date.now.bind(Date);
window.r3Fixture = {
  page: scheme => new Promise(resolve => {
    const start_ms = nativeDateNow();
    const socket = new WebSocket(scheme + '://websocket-r3.test:8443/dnr-page-' + scheme);
    let done=false;
    const finish=kind=>{if(!done){done=true;const terminal_ms=nativeDateNow();
      resolve({kind, actor:'page', scheme, start_ms, terminal_ms, end_ms:nativeDateNow(),
        timestamp_source:'controlled_fixture_native_date_now_epoch_ms'});}};
    const timer=setTimeout(()=>finish('timeout'),5000);
    socket.onopen=()=>{clearTimeout(timer);finish('open');socket.close();};
    socket.onerror=()=>{clearTimeout(timer);finish('error');};
    socket.onclose=()=>{clearTimeout(timer);finish('close');};
  }),
  worker: () => new Worker('/dnr-worker.js')
};</script>"""


def response(path: str, upgrade: bool = False) -> tuple[int, bytes, str]:
    if upgrade:
        return 403, b"", "text/plain"
    if path == "/dnr":
        return 200, PAGE.encode(), "text/html"
    if path == "/dnr-worker.js":
        return 200, WORKER.encode(), "application/javascript"
    return 404, b"", "text/plain"


def create_tls(directory: Path):
    """Fixed local fixture trust mode, never invoked by offline tests/entrypoint."""
    if os.getuid() != 10001 or directory != Path("/tmp/r3-tls"):  # noqa: S108 - exclusive container tmpfs
        raise RuntimeError("tls_location_or_uid_invalid")
    directory.mkdir(mode=0o700, exist_ok=False)
    cert, key = directory / "fixture.crt", directory / "fixture.key"
    args = [
        "/usr/bin/openssl",
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-days",
        "1",
        "-subj",
        "/CN=navigation-r3.test",
        "-keyout",
        str(key),
        "-out",
        str(cert),
    ]
    try:
        subprocess.run(  # noqa: S603 - fixed image-local argv; not called offline
            args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15
        )
        key.chmod(0o600)
        return (
            cert,
            key,
            {
                "certificate_sha256": hashlib.sha256(cert.read_bytes()).hexdigest(),
                "key_path": str(key),
                "key_mode": "0600",
                "key_content_exported": False,
            },
        )
    except Exception:
        raise RuntimeError("tls_generation_unknown") from None


def serve(cert: str, key: str, audit):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # never log URI/headers/secret/body

        def do_GET(self):
            is_ws = self.headers.get("Upgrade", "").lower() == "websocket"
            status, body, content_type = response(self.path, is_ws)
            audit(
                {
                    "route": self.path if self.path in {"/dnr", "/dnr-worker.js"} else "unknown",
                    "ws_received": int(is_ws),
                    "status": status,
                }
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    with ThreadingHTTPServer(("0.0.0.0", 8443), Handler) as server:  # noqa: S104 - dedicated internal fixture namespace
        server.socket = context.wrap_socket(server.socket, server_side=True)
        server.serve_forever()


if __name__ == "__main__":
    raise SystemExit("NO_GO: real_session_not_authorized")
