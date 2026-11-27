"""Command line and HTTP server.

Every setting has a flag and an environment variable; flags win. The packaged systemd units load
the variables from /etc/default/claude-usage-exporter (and a per-user file, see the README).
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__
from .exporter import DEFAULT_URL, Cache, Config, log, render

CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def default_credentials() -> str:
    # Claude Code keeps its config in $CLAUDE_CONFIG_DIR when that is set, ~/.claude otherwise.
    base = os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude"
    return os.path.join(base, ".credentials.json")


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(f"claude-usage-exporter: {name} must be an integer, got {raw!r}") from None


def parse_args(argv: list[str] | None = None) -> tuple[Config, bool]:
    env = os.environ
    p = argparse.ArgumentParser(
        prog="claude-usage-exporter",
        description="Prometheus exporter for Claude plan usage limits (reads the Claude CLI login).",
    )
    p.add_argument(
        "--bind",
        default=env.get("CLAUDE_USAGE_BIND") or "127.0.0.1",
        help="address to listen on (env CLAUDE_USAGE_BIND, default 127.0.0.1)",
    )
    p.add_argument(
        "--port",
        type=int,
        default=env_int("CLAUDE_USAGE_PORT", 9101),
        help="port to listen on (env CLAUDE_USAGE_PORT, default 9101)",
    )
    p.add_argument(
        "--cache-seconds",
        type=int,
        default=env_int("CLAUDE_USAGE_CACHE", 300),
        help="query the usage endpoint at most this often (env CLAUDE_USAGE_CACHE, default 300)",
    )
    p.add_argument(
        "--credentials",
        default=env.get("CLAUDE_USAGE_CREDENTIALS") or default_credentials(),
        help="Claude CLI credentials file (env CLAUDE_USAGE_CREDENTIALS, default "
        "$CLAUDE_CONFIG_DIR/.credentials.json or ~/.claude/.credentials.json)",
    )
    p.add_argument(
        "--url",
        default=env.get("CLAUDE_USAGE_URL") or DEFAULT_URL,
        help="usage endpoint (env CLAUDE_USAGE_URL; for testing against a mock)",
    )
    p.add_argument("--once", action="store_true", help="print the metrics once and exit")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    a = p.parse_args(argv)
    if not 0 < a.port < 65536:
        p.error("--port must be 1-65535")
    if a.cache_seconds < 0:
        p.error("--cache-seconds must be >= 0")
    cfg = Config(
        bind=a.bind, port=a.port, cache_seconds=a.cache_seconds, credentials=a.credentials, url=a.url
    )
    return cfg, a.once


def make_handler(cache: Cache):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = f"claude-usage-exporter/{__version__}"

        def _send(self, code: int, body: bytes, ctype: str = "text/plain; charset=utf-8") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - http.server API
            path = self.path.split("?", 1)[0]
            if path == "/metrics":
                with lock:
                    body = cache.get().encode()
                self._send(200, body, CONTENT_TYPE)
            elif path == "/healthz":
                self._send(200, b"ok\n")
            elif path == "/":
                self._send(200, b"claude-usage-exporter: metrics at /metrics\n")
            else:
                self._send(404, b"not found\n")

        do_HEAD = do_GET  # noqa: N815

        def log_message(self, *args) -> None:
            pass

    return Handler


def serve(cfg: Config) -> None:
    server = ThreadingHTTPServer((cfg.bind, cfg.port), make_handler(Cache(cfg)))
    server.daemon_threads = True
    log(f"claude-usage-exporter {__version__} listening on {cfg.bind}:{cfg.port}, cache {cfg.cache_seconds}s")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    cfg, once = parse_args(argv)
    if once:
        sys.stdout.write(render(cfg))
        return 0
    serve(cfg)
    return 0
