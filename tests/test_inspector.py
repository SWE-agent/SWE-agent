from __future__ import annotations

import pytest

from sweagent.inspector import server


class _NoServeTCPServer:
    """Drop-in replacement for ``socketserver.TCPServer`` that never binds a socket."""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def serve_forever(self):
        return


@pytest.fixture
def trajectory_dir(tmp_path):
    """A trajectory directory as written by ``sweagent run``/``sweagent run-batch``."""
    (tmp_path / "args.yaml").write_text(
        "environment:\n  data_path: tests/test_data/data_sources/does-not-exist.json\n"
    )
    return tmp_path


def test_missing_dataset_is_skipped(trajectory_dir, monkeypatch):
    """A dataset referenced by args.yaml may be gone; that must not abort the inspector."""
    monkeypatch.setattr(server.socketserver, "TCPServer", _NoServeTCPServer)
    server.main(data_path=None, directory=str(trajectory_dir), port=0)
