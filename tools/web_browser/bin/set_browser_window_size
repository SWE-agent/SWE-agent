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
    _print_response_with_metadata,
    send_request,
)

config = ClientConfig()


def set_window_size(width, height):
    """Set the browser window size to the specified width and height."""
    response = send_request(
        config.port,
        "set_window_size",
        "POST",
        {"width": width, "height": height, "return_screenshot": config.autoscreenshot},
    )
    if response is None:
        return
    _print_response_with_metadata(response)
    _autosave_screenshot_from_response(response, config.screenshot_mode)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("width", type=int, help="The new width of the browser window")
    parser.add_argument("height", type=int, help="The new height of the browser window")
    args = parser.parse_args()
    set_window_size(args.width, args.height)
