"""Single local navigation + HTTP(S) Dedicated Worker script, no WS upstream."""

from __future__ import annotations

import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WORKER = """'use strict';
self.onmessage = event => {
  if (event.data.kind === 'ping') {self.postMessage({kind:'pong'}); return;}
  if (event.data.kind !== 'start') return;
  const scheme = event.data.scheme;
  const socket = new WebSocket(scheme + '://websocket-r3.test:8443/dnr-worker-' + scheme);
  let ended = false;
  const finish = kind => {if (!ended) {ended=true; self.postMessage({kind});}};
  const timer = setTimeout(() => finish('timeout'), 5000);
  socket.onopen = () => {clearTimeout(timer); finish('open'); socket.close();};
  socket.onerror = () => {clearTimeout(timer); finish('error');};
  socket.onclose = () => {clearTimeout(timer); finish('close');};
}; self.postMessage({kind:'ready'});
"""
PAGE = """<!doctype html><meta charset='utf-8'><title>R3 fixture</title><script>
window.r3Fixture = {
  page: scheme => new Promise(resolve => {
    const socket = new WebSocket(scheme + '://websocket-r3.test:8443/dnr-page-' + scheme);
    let done=false;
    const finish=kind=>{if(!done){done=true;resolve({kind});}};
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
