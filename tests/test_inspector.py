"""Tests for the trajectory inspector HTTP server, focusing on the
path-traversal protection of the ``/trajectory/`` endpoint (issue #1472)."""

from __future__ import annotations

import json
import socket
import socketserver
import threading
from functools import partial
from http.client import HTTPConnection
from pathlib import Path

import pytest

from sweagent.inspector.server import Handler, resolve_traj_path


def _write_traj(path: Path, marker: str) -> None:
    """Write a minimal trajectory-shaped JSON file to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "history": [{"role": "user", "content": marker}],
                "trajectory": [],
                "info": {},
            }
        )
    )


# --------------------------------------------------------------------------- #
# Unit tests for resolve_traj_path
# --------------------------------------------------------------------------- #


def test_resolve_traj_path_allows_file_inside_dir(tmp_path: Path) -> None:
    (tmp_path / "run.traj").write_text("{}")
    resolved = resolve_traj_path(tmp_path, "run.traj")
    assert resolved == (tmp_path / "run.traj").resolve()


def test_resolve_traj_path_allows_nested_file(tmp_path: Path) -> None:
    nested = tmp_path / "sub" / "run.traj"
    nested.parent.mkdir()
    nested.write_text("{}")
    resolved = resolve_traj_path(tmp_path, "sub/run.traj")
    assert resolved == nested.resolve()


@pytest.mark.parametrize(
    "escape",
    [
        "../secret.json",
        "../../secret.json",
        "..%2Fsecret.json",  # percent-encoded slash
        "%2e%2e/secret.json",  # percent-encoded dots
        "sub/../../secret.json",
        "/etc/passwd",  # absolute path escape
    ],
)
def test_resolve_traj_path_rejects_escapes(tmp_path: Path, escape: str) -> None:
    served = tmp_path / "served"
    served.mkdir()
    # A sensitive file living *outside* the served directory.
    (tmp_path / "secret.json").write_text("{}")
    assert resolve_traj_path(served, escape) is None


def test_resolve_traj_path_strips_query_string(tmp_path: Path) -> None:
    (tmp_path / "run.traj").write_text("{}")
    resolved = resolve_traj_path(tmp_path, "run.traj?foo=bar")
    assert resolved == (tmp_path / "run.traj").resolve()


# --------------------------------------------------------------------------- #
# Integration test: boot the real server and send raw requests
# --------------------------------------------------------------------------- #


def _raw_get(host: str, port: int, raw_path: str) -> tuple[int, dict[str, str], bytes]:
    """Send a GET whose request-line path is *raw_path* verbatim.

    Using a raw socket (instead of a normalizing HTTP client) ensures literal
    ``..`` segments reach the server, mirroring ``curl --path-as-is``.
    """
    with socket.create_connection((host, port), timeout=5) as sock:
        request = f"GET {raw_path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        sock.sendall(request.encode())
        chunks = []
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
    raw = b"".join(chunks)
    header_blob, _, body = raw.partition(b"\r\n\r\n")
    lines = header_blob.decode("latin-1").split("\r\n")
    status = int(lines[0].split(" ")[1])
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            key, _, value = line.partition(":")
            headers[key.strip().lower()] = value.strip()
    return status, headers, body


@pytest.fixture
def running_inspector(tmp_path: Path):
    served = tmp_path / "served"
    served.mkdir()
    _write_traj(served / "good.traj", "public-content")
    # Trajectory-shaped secret sitting outside the served directory.
    _write_traj(tmp_path / "secret.json", "TOP-SECRET-API-KEY")

    handler = partial(Handler, directory=str(served), gold_patches={}, test_patches={})

    class _Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    httpd = _Server(("127.0.0.1", 0), handler)
    host, port = httpd.server_address
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield host, port
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_server_serves_valid_trajectory(running_inspector) -> None:
    host, port = running_inspector
    conn = HTTPConnection(host, port, timeout=5)
    conn.request("GET", "/trajectory/good.traj")
    response = conn.getresponse()
    assert response.status == 200
    body = response.read()
    conn.close()
    assert b"public-content" in body


def test_server_blocks_path_traversal(running_inspector) -> None:
    host, port = running_inspector
    status, _headers, body = _raw_get(host, port, "/trajectory/../secret.json")
    assert status == 403
    assert b"TOP-SECRET-API-KEY" not in body


def test_server_does_not_send_wildcard_cors(running_inspector) -> None:
    host, port = running_inspector
    status, headers, _body = _raw_get(host, port, "/trajectory/good.traj")
    assert status == 200
    assert headers.get("access-control-allow-origin") != "*"
