from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class DecoyHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, _format: str, *_args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9090), DecoyHandler).serve_forever()  # noqa: S104
