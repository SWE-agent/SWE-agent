from __future__ import annotations

import os
from dataclasses import dataclass, field

from browser_utils import ScreenshotMode


@dataclass
class ClientConfig:
    """Configuration for the browser client"""
    port: int = int(os.getenv("BROWSER_PORT", "8009"))
    autoscreenshot: bool = os.getenv("BROWSER_AUTOSCREENSHOT", "1") == "1"
    screenshot_mode: ScreenshotMode = ScreenshotMode(
        os.getenv("BROWSER_SCREENSHOT_MODE", ScreenshotMode.SAVE.value)
    )


@dataclass
class ServerConfig:
    """Configuration for the browser server"""
    port: int = int(os.getenv("BROWSER_PORT", "8009"))
    window_width: int = int(os.getenv("BROWSER_WINDOW_WIDTH", 1024))
    window_height: int = int(os.getenv("BROWSER_WINDOW_HEIGHT", 768))
    headless: bool = os.getenv("BROWSER_HEADLESS", "1") != "0"
    screenshot_delay: float = float(os.getenv("BROWSER_SCREENSHOT_DELAY", 0.2))
    browser_type: str = os.getenv("BROWSER_BROWSER_TYPE", "chromium")
    reconnect_timeout: float = float(os.getenv("BROWSER_RECONNECT_TIMEOUT", 15))
    chromium_executable_path: str | None = os.getenv("BROWSER_CHROMIUM_EXECUTABLE_PATH")
    firefox_executable_path: str | None = os.getenv("BROWSER_FIREFOX_EXECUTABLE_PATH")
    crosshair_id: str = "__browser_crosshair__"
