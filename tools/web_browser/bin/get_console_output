#!/root/python3.11/bin/python3
from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path

lib_path = str(Path(__file__).resolve().parent.parent / "lib")
sys.path.insert(0, lib_path)

from web_browser_config import ClientConfig
from web_browser_utils import (
    _print_response_with_metadata,
    send_request,
)

config = ClientConfig()


def get_console_output():
    """Get console output from the browser."""
    response = send_request(config.port, "console", "GET", {})
    if response is None:
        return
    _print_response_with_metadata(response)
    if "console_messages" in response:
        console_messages = response["console_messages"]
        if console_messages:
            print("\n--- Console Messages ---")
            for ix, msg in enumerate(console_messages):
                # timestamp = msg.get("timestamp", 0)
                msg_type = msg.get("type", "log")
                text = msg.get("text", "")
                location = msg.get("location", {})
                print(f"[{ix + 1}] {msg_type.upper()}: {text}")
                if location:
                    url = location.get("url", "")
                    line_number = location.get("lineNumber", "")
                    column_number = location.get("columnNumber", "")
                    if url:
                        print(f"    Location: {url}:{line_number}:{column_number}")
            print("Console buffer cleared.")


if __name__ == "__main__":
    parser = ArgumentParser()
    args = parser.parse_args()
    get_console_output()
