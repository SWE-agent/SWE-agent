#!/root/python3.11/bin/python3
from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path

lib_path = str(Path(__file__).resolve().parent.parent / "lib")
sys.path.insert(0, lib_path)

from web_browser_config import ClientConfig
from web_browser_utils import (
    ScreenshotMode,
    _handle_screenshot,
    _print_response_with_metadata,
    send_request,
)

config = ClientConfig()


def screenshot():
    """Capture a screenshot and handle it according to the default config.screenshot_mode."""
    response = send_request(config.port, "screenshot", "GET")
    if response is None:
        return
    screenshot_data = response["screenshot"]
    _print_response_with_metadata(response)
    if config.screenshot_mode == ScreenshotMode.SAVE:
        _handle_screenshot(screenshot_data, ScreenshotMode.SAVE)
    else:
        _handle_screenshot(screenshot_data, ScreenshotMode.PRINT)


if __name__ == "__main__":
    parser = ArgumentParser()
    args = parser.parse_args()
    screenshot()
