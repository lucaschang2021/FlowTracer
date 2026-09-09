from __future__ import annotations

import socketserver


class CanaryHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        self.request.sendall(b"R2_HOST_CANARY\n")


class ThreadedCanary(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    # Exposed only on a unique, short-lived loopback host port by Compose.
    with ThreadedCanary(("0.0.0.0", 49175), CanaryHandler) as server:  # noqa: S104
        server.serve_forever()
