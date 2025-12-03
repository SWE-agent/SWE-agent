from __future__ import annotations

import os
from dataclasses import dataclass, field

from web_browser_utils import ScreenshotMode


@dataclass
class ClientConfig:
    """Configuration for the web_browser client"""
    port: int = int(os.getenv("WEB_BROWSER_PORT", "8009"))
    autoscreenshot: bool = os.getenv("WEB_BROWSER_AUTOSCREENSHOT", "1") == "1"
    screenshot_mode: ScreenshotMode = ScreenshotMode(
        os.getenv("WEB_BROWSER_SCREENSHOT_MODE", ScreenshotMode.SAVE.value)
    )


@dataclass
class ServerConfig:
    """Configuration for the web_browser server"""
    port: int = int(os.getenv("WEB_BROWSER_PORT", "8009"))
    window_width: int = int(os.getenv("WEB_BROWSER_WINDOW_WIDTH", 1024))
    window_height: int = int(os.getenv("WEB_BROWSER_WINDOW_HEIGHT", 768))
    headless: bool = os.getenv("WEB_BROWSER_HEADLESS", "1") != "0"
    screenshot_delay: float = float(os.getenv("WEB_BROWSER_SCREENSHOT_DELAY", 0.2))
    browser_type: str = os.getenv("WEB_BROWSER_BROWSER_TYPE", "chromium")
    reconnect_timeout: float = float(os.getenv("WEB_BROWSER_RECONNECT_TIMEOUT", 15))
    chromium_executable_path: str | None = os.getenv("WEB_BROWSER_CHROMIUM_EXECUTABLE_PATH")
    firefox_executable_path: str | None = os.getenv("WEB_BROWSER_FIREFOX_EXECUTABLE_PATH")
    crosshair_id: str = "__web_browser_crosshair__"
