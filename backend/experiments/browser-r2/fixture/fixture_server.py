from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/redirect-safe":
            self.send_response(302)
            self.send_header("Location", "https://fixture-r2.test:8443/ok")
            self.end_headers()
            return
        if self.path == "/redirect-unsafe":
            self.send_response(302)
            self.send_header("Location", "https://metadata-r2.test:8443/blocked")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, _format: str, *_args: object) -> None:
        return


if __name__ == "__main__":
    # Container has only the isolated fixture network and publishes no port.
    ThreadingHTTPServer(("0.0.0.0", 8443), FixtureHandler).serve_forever()  # noqa: S104
