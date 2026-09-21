from __future__ import annotations

import socketserver


class CanaryHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        self.request.sendall(b"R2C_HOST_CANARY\n")


class ThreadedCanary(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with ThreadedCanary(("0.0.0.0", 49273), CanaryHandler) as server:  # noqa: S104
        server.serve_forever()
