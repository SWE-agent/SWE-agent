"""Regression tests for the trajectory inspector web server.

Covers the path-traversal disclosure reported in
https://github.com/SWE-agent/SWE-agent/issues/1472 :

- requests that escape the trajectory directory (plain `..`, absolute
  paths, percent-encoded `..`, symlinks pointing outside) are rejected
  with 404 and the off-path content is never returned;
- in-directory trajectories are still served;
- the server no longer sends a wildcard CORS header;
- the server binds loopback by default, with an explicit `--host` opt-in
  for the deliberate all-interfaces case.
"""

from __future__ import annotations

import http.client
import json
import socket
import socketserver
import threading
from functools import partial
from pathlib import Path

import pytest

from sweagent.inspector.server import Handler, get_parser, main, resolve_traj_path


def _traj_json(marker: str) -> dict:
    return {
        "history": [{"role": "user", "content": "x"}],
        "trajectory": [],
        "info": {
            "exit_status": "submitted",
            "model_stats": {"api_calls": 1, "instance_cost": 0.1, "tokens_sent": 10, "tokens_received": 10},
            "submission": marker,
        },
    }


@pytest.fixture()
def traj_dirs(tmp_path):
    served = tmp_path / "served"
    outside = tmp_path / "outside"
    served.mkdir()
    outside.mkdir()
    (served / "ok.traj").write_text(json.dumps(_traj_json("MARKER-INSIDE-TRAJ")))
    (outside / "victim.traj").write_text(json.dumps(_traj_json("MARKER-OUTSIDE-TRAJ")))
    return served, outside


@pytest.fixture()
def live_server(traj_dirs):
    served, _ = traj_dirs
    handler = partial(Handler, directory=str(served), gold_patches={}, test_patches={})
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def _get(port: int, path: str) -> tuple[int, dict, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", path)
    resp = conn.getresponse()
    body = resp.read()
    headers = dict(resp.getheaders())
    status = resp.status
    conn.close()
    return status, headers, body


def test_in_directory_trajectory_served(live_server):
    status, headers, body = _get(live_server, "/trajectory/ok.traj")
    assert status == 200
    assert b"MARKER-INSIDE-TRAJ" in body


def test_parent_traversal_rejected(live_server):
    status, _headers, body = _get(live_server, "/trajectory/../outside/victim.traj")
    assert status == 404
    assert b"MARKER-OUTSIDE-TRAJ" not in body


def test_absolute_path_rejected(live_server, traj_dirs):
    _, outside = traj_dirs
    status, _headers, body = _get(live_server, f"/trajectory/{outside / 'victim.traj'}")
    assert status == 404
    assert b"MARKER-OUTSIDE-TRAJ" not in body


def test_percent_encoded_traversal_rejected(live_server):
    status, _headers, body = _get(live_server, "/trajectory/%2e%2e/outside/victim.traj")
    assert status == 404
    assert b"MARKER-OUTSIDE-TRAJ" not in body


def test_traversal_with_query_string_rejected(live_server):
    status, _headers, body = _get(live_server, "/trajectory/../outside/victim.traj?x=1")
    assert status == 404
    assert b"MARKER-OUTSIDE-TRAJ" not in body


def test_no_wildcard_cors_header(live_server):
    _status, headers, _body = _get(live_server, "/trajectory/ok.traj")
    assert "Access-Control-Allow-Origin" not in headers


def test_raw_literal_dotdot_request_rejected(live_server):
    """Same check as the traversal test, but sent as a raw request line so
    no client-side path normalisation can hide the `..` segments."""
    sock = socket.create_connection(("127.0.0.1", live_server), timeout=10)
    sock.sendall(b"GET /trajectory/../../../../outside/victim.traj HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
    raw = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        raw += chunk
    sock.close()
    assert raw.startswith(b"HTTP/1.1 404") or raw.startswith(b"HTTP/1.0 404")
    assert b"MARKER-OUTSIDE-TRAJ" not in raw


def test_resolve_traj_path_unit(traj_dirs, tmp_path):
    served, outside = traj_dirs
    assert resolve_traj_path(served, "ok.traj").name == "ok.traj"
    assert resolve_traj_path(served, "sub/../ok.traj").name == "ok.traj"
    with pytest.raises(ValueError):
        resolve_traj_path(served, "../outside/victim.traj")
    with pytest.raises(ValueError):
        resolve_traj_path(served, str(outside / "victim.traj"))
    with pytest.raises(FileNotFoundError):
        resolve_traj_path(served, "missing.traj")
    # A symlink inside the directory that points outside must not smuggle
    # the target in.
    link = served / "escape.traj"
    link.symlink_to(outside / "victim.traj")
    with pytest.raises(ValueError):
        resolve_traj_path(served, "escape.traj")


def test_default_host_is_loopback():
    assert get_parser().parse_args([]).host == "127.0.0.1"
    assert get_parser().parse_args([]).port == 8000


def test_host_flag_allows_explicit_override():
    assert get_parser().parse_args(["--host", "0.0.0.0"]).host == "0.0.0.0"


class _StopServer(Exception):
    pass


class _CaptureTCPServer:
    captured_address = None

    def __init__(self, address, _handler):
        type(self).captured_address = address

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def serve_forever(self):
        raise _StopServer


def test_main_binds_loopback_by_default(tmp_path, monkeypatch):
    """main() must pass 127.0.0.1 (not "") to TCPServer unless --host says so."""
    monkeypatch.setattr(socketserver, "TCPServer", _CaptureTCPServer)
    with pytest.raises(_StopServer):
        main(None, str(tmp_path), 8231)
    assert _CaptureTCPServer.captured_address == ("127.0.0.1", 8231)
