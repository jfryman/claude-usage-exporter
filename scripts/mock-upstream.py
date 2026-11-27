#!/usr/bin/env python3
"""Stand-in for the usage endpoint: answers every GET with a JSON file. For tests and the smoke test."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--port", type=int, default=18080)
p.add_argument("file")
a = p.parse_args()
body = Path(a.file).read_bytes()


class H(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        ok = self.headers.get("Authorization", "").startswith("Bearer ") and self.headers.get(
            "anthropic-beta"
        )
        self.send_response(200 if ok else 401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body if ok else b'{"error":"unauthorized"}')

    def log_message(self, *args):
        pass


ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
