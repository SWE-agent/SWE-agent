from __future__ import annotations

import base64
import functools
import requests
import sys
from enum import Enum
from pathlib import Path

from flask import jsonify, request


class ScreenshotMode(Enum):
    SAVE = "save"  # saves screenshot to png file
    PRINT = "print"  # prints base64 encoded screenshot to stdout


def normalize_url(url: str) -> str:
    # if starts with http:// or https://, return as is
    # if starts with file://, return as is
    # elif local file path exists, return as file://
    # else: return as https://
    if any(url.startswith(prefix) for prefix in ["http://", "https://", "file://"]):
        return url
    elif Path(url).exists():
        return f"file://{Path(url).resolve()}"
    else:
        return "https://" + url


def validate_request(*required_keys):
    """Decorator to validate that all required keys are present in request JSON."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return jsonify({"status": "error", "message": "Request must be JSON"})
            
            request_data = request.get_json()
            if not request_data:
                return jsonify({"status": "error", "message": "Request body cannot be empty"})
            
            missing_keys = [key for key in required_keys if key not in request_data]
            if missing_keys:
                return jsonify({
                    "status": "error", 
                    "message": f"Missing required fields: {', '.join(missing_keys)}"
                })
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def catch_error(func):
    """Decorator to catch exceptions and return them as JSON."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
    return wrapper


def _print_error(message, error_type="ERROR"):
    """Print error message in a normalized format."""
    print(f"{error_type}: {message}", file=sys.stderr)


def _format_metadata_info(response):
    """Format metadata information from API response for display."""
    if "metadata" not in response or not response["metadata"]:
        return ""
    return "\n".join(f"{key}: {value}" for key, value in response["metadata"].items())


def send_request(port, endpoint, method="GET", data=None):
    url = f"http://localhost:{port}/{endpoint}"
    if method == "GET":
        response = requests.get(url)
    else:
        response = requests.post(url, json=data)
    if response.status_code != 200:
        _print_error(f"Internal error communicating with backend: {response.text}", "INTERNAL ERROR")
        return None
    data = response.json()
    if data["status"] == "error":
        metadata_info = _format_metadata_info(data)
        error_message = data['message']
        _print_error(f"ACTION ERROR:\n{error_message}")
        if metadata_info:
            print(f"\nMETADATA:\n{metadata_info}", file=sys.stderr)
        return None
    return data


def _print_response_with_metadata(response):
    """Print response message with formatted metadata information."""
    message = response.get("message", "")
    metadata_info = _format_metadata_info(response)
    print(f"ACTION RESPONSE:\n{message}")
    
    if metadata_info:
        print(f"\nMETADATA:\n{metadata_info}")


def _handle_screenshot(screenshot_data, mode):
    """Handle screenshot data according to the specified mode"""
    if mode == ScreenshotMode.SAVE:
        path = Path("latest_screenshot.png")
        path.write_bytes(base64.b64decode(screenshot_data))
        print(f"![Screenshot]({path})")
    elif mode == ScreenshotMode.PRINT:
        print(f"![Screenshot](data:image/png;base64,{screenshot_data})")
    else:
        raise ValueError(f"Invalid screenshot mode: {mode}")


def _autosave_screenshot_from_response(response, mode):
    """Handle screenshot from response data according to the specified mode"""
    if "screenshot" in response:
        _handle_screenshot(response["screenshot"], mode)
