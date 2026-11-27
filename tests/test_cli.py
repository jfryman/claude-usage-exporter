import os
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from claude_usage_exporter import __version__
from claude_usage_exporter.cli import make_handler, parse_args
from claude_usage_exporter.exporter import Cache

# Run the module the way the tests import it (src/ checkout or an installed build tree).
ENV = {**os.environ, "PYTHONPATH": os.pathsep.join(p for p in sys.path if p)}


def test_version():
    out = subprocess.run(
        [sys.executable, "-m", "claude_usage_exporter", "--version"],
        capture_output=True,
        text=True,
        check=True,
        env=ENV,
    ).stdout
    assert out.strip() == f"claude-usage-exporter {__version__}"


def test_defaults(monkeypatch):
    for name in (
        "CLAUDE_USAGE_BIND",
        "CLAUDE_USAGE_PORT",
        "CLAUDE_USAGE_CACHE",
        "CLAUDE_USAGE_CREDENTIALS",
        "CLAUDE_USAGE_URL",
        "CLAUDE_CONFIG_DIR",
    ):
        monkeypatch.delenv(name, raising=False)
    cfg, once = parse_args([])
    assert (cfg.bind, cfg.port, cfg.cache_seconds) == ("127.0.0.1", 9101, 300)
    assert cfg.credentials == "~/.claude/.credentials.json"
    assert cfg.url == "https://api.anthropic.com/api/oauth/usage"
    assert once is False


def test_env_then_flags(monkeypatch):
    monkeypatch.setenv("CLAUDE_USAGE_BIND", "0.0.0.0")
    monkeypatch.setenv("CLAUDE_USAGE_PORT", "9200")
    monkeypatch.setenv("CLAUDE_USAGE_CACHE", "60")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/srv/claude")
    cfg, _ = parse_args([])
    assert (cfg.bind, cfg.port, cfg.cache_seconds) == ("0.0.0.0", 9200, 60)
    assert cfg.credentials == "/srv/claude/.credentials.json"
    monkeypatch.setenv("CLAUDE_USAGE_CREDENTIALS", "/x/creds.json")
    cfg, once = parse_args(["--port", "9300", "--bind", "::1", "--once"])
    assert (cfg.bind, cfg.port, cfg.credentials, once) == ("::1", 9300, "/x/creds.json", True)


def test_empty_env_means_default(monkeypatch):
    monkeypatch.setenv("CLAUDE_USAGE_BIND", "")
    monkeypatch.setenv("CLAUDE_USAGE_PORT", "")
    cfg, _ = parse_args([])
    assert (cfg.bind, cfg.port) == ("127.0.0.1", 9101)


@pytest.mark.parametrize("argv", [["--port", "0"], ["--cache-seconds", "-1"]])
def test_rejects_bad_values(argv):
    with pytest.raises(SystemExit):
        parse_args(argv)


def test_bad_env_int(monkeypatch):
    monkeypatch.setenv("CLAUDE_USAGE_PORT", "abc")
    with pytest.raises(SystemExit, match="CLAUDE_USAGE_PORT"):
        parse_args([])


def test_once(creds, upstream):
    out = subprocess.run(
        [
            sys.executable,
            "-m",
            "claude_usage_exporter",
            "--once",
            "--credentials",
            str(creds),
            "--url",
            upstream.url,
        ],
        capture_output=True,
        text=True,
        check=True,
        env=ENV,
    ).stdout
    assert "claude_usage_up 1" in out
    assert 'claude_usage_percent{window="seven_day"} 42.0' in out


def test_http_server(creds, upstream):
    cfg, _ = parse_args(["--credentials", str(creds), "--url", upstream.url])
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Cache(cfg)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(base + "/metrics") as r:
            assert r.headers["Content-Type"].startswith("text/plain; version=0.0.4")
            assert b"claude_usage_up 1" in r.read()
        with urllib.request.urlopen(base + "/metrics?x=1") as r:
            r.read()
        assert len(upstream.requests) == 1  # cached
        with urllib.request.urlopen(base + "/healthz") as r:
            assert r.read() == b"ok\n"
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base + "/other")
        assert e.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
