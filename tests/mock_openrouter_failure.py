"""Tiny local OpenRouter stand-in that always returns HTTP 429.

Used only for the optional browser failure-state check:
    python tests/mock_openrouter_failure.py
"""

from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        time.sleep(1.2)
        body = json.dumps(
            {"error": {"message": "simulated rate limit for UI verification"}}
        ).encode("utf-8")
        self.send_response(429)
        self.send_header("Content-Type", "application/json")
        self.send_header("Retry-After", "0")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("Mock OpenRouter failure server on http://127.0.0.1:8765", flush=True)
    server.serve_forever()
