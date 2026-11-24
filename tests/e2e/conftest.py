"""Serve the site folder over HTTP for browser tests (pages load their data with fetch())."""

from __future__ import annotations

import functools
import http.server
import threading
from collections.abc import Iterator

import pytest

from tests.conftest import ROOT


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture(scope="session")
def site_url() -> Iterator[str]:
    handler = functools.partial(_Quiet, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
