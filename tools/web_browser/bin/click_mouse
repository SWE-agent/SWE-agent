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


def click(x, y, button):
    """Click at the specified coordinates (x, y)."""
    response = send_request(
        config.port,
        "click",
        "POST",
        {"x": x, "y": y, "button": button, "return_screenshot": config.autoscreenshot},
    )
    if response is None:
        return
    _print_response_with_metadata(response)
    _autosave_screenshot_from_response(response, config.screenshot_mode)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("x", type=int)
    parser.add_argument("y", type=int)
    parser.add_argument("button", nargs="?", default="left", choices=["left", "right"])
    args = parser.parse_args()
    click(args.x, args.y, args.button)
