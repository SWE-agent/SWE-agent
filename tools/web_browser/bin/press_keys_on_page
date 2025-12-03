#!/root/python3.11/bin/python3
from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path

lib_path = str(Path(__file__).resolve().parent.parent / "lib")
sys.path.insert(0, lib_path)

from web_browser_config import ClientConfig
from web_browser_utils import (
    _autosave_screenshot_from_response,
    _print_error,
    _print_response_with_metadata,
    send_request,
)

config = ClientConfig()


def keypress(keys):
    """Press the specified keys. Keys should be a JSON string like '["ctrl", "c"]'."""
    import json

    try:
        keys_data = json.loads(keys)
    except json.JSONDecodeError:
        _print_error("Keys must be valid JSON")
        return
    response = send_request(
        config.port,
        "keypress",
        "POST",
        {"keys": keys_data, "return_screenshot": config.autoscreenshot},
    )
    if response is None:
        return
    _print_response_with_metadata(response)
    _autosave_screenshot_from_response(response, config.screenshot_mode)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "keys",
        type=str,
        help='The keys to press (JSON string like \'["ctrl", "c"]\')',
    )
    args = parser.parse_args()
    keypress(args.keys)
