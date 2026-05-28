from __future__ import annotations

import io
import json
import socket
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sweagent.inspector.server import Handler


class MockRequest:
    def __init__(self, data: bytes = b""):
        self.rfile = io.BytesIO(data)
        self.wfile = io.BytesIO()
        self.client_address = ("127.0.0.1", 12345)


def make_handler(traj_dir: Path, path: str) -> Handler:
    request = MockRequest()
    server = MagicMock()
    handler = Handler(request, request.client_address, server, directory=str(traj_dir))
    handler.path = path
    handler.request_version = "HTTP/1.1"
    handler.command = "GET"
    handler.headers = {}
    return handler


def test_trajectory_path_traversal_blocked(tmp_path: Path):
    traj_dir = tmp_path / "trajectories"
    traj_dir.mkdir()
    secret_dir = tmp_path / "secret"
    secret_dir.mkdir()
    secret_file = secret_dir / "secret.txt"
    secret_file.write_text("secret data")

    handler = make_handler(traj_dir, "/trajectory/../secret/secret.txt")
    handler.do_GET()

    response = handler.request.wfile.getvalue()
    assert b"403" in response or b"Access denied" in response


def test_trajectory_valid_file_allowed(tmp_path: Path):
    traj_dir = tmp_path / "trajectories"
    traj_dir.mkdir()
    traj_file = traj_dir / "test.traj"
    traj_file.write_text(json.dumps({"trajectory": [], "history": []}))

    handler = make_handler(traj_dir, "/trajectory/test.traj")
    handler.do_GET()

    response = handler.request.wfile.getvalue()
    assert b"403" not in response
    assert b"Access denied" not in response
