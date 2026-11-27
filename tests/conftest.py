import json
import os
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

# The mock upstream is local. Debian builds point http_proxy at a dead port to block network
# access during tests, and urllib honours it, so keep loopback off the proxy.
os.environ["no_proxy"] = os.environ["NO_PROXY"] = "127.0.0.1,localhost"


@pytest.fixture
def usage_doc():
    return json.loads((FIXTURES / "usage.json").read_text())


@pytest.fixture
def creds(tmp_path):
    path = tmp_path / ".credentials.json"
    shutil.copy(FIXTURES / "credentials.json", path)
    return path


class MockUpstream:
    """A local stand-in for the usage endpoint: records requests, answers with `body`/`status`."""

    def __init__(self):
        self.body: bytes = (FIXTURES / "usage.json").read_bytes()
        self.status = 200
        self.requests: list[dict] = []
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                mock.requests.append({"path": self.path, "headers": dict(self.headers)})
                self.send_response(mock.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(mock.body)))
                self.end_headers()
                self.wfile.write(mock.body)

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/api/oauth/usage"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def upstream():
    mock = MockUpstream()
    yield mock
    mock.close()
