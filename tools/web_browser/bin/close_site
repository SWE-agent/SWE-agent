#!/root/python3.11/bin/python3
from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path

lib_path = str(Path(__file__).resolve().parent.parent / "lib")
sys.path.insert(0, lib_path)

from web_browser_config import ClientConfig
from web_browser_utils import _print_response_with_metadata, send_request

config = ClientConfig()


def close():
    """Close the currently open window."""
    response = send_request(config.port, "close", "POST")
    if response is None:
        return
    _print_response_with_metadata(response)


if __name__ == "__main__":
    parser = ArgumentParser()
    args = parser.parse_args()
    close()
