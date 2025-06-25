from __future__ import annotations

import os
from dataclasses import dataclass, field

from sweer_utils import ScreenshotMode


@dataclass
class ClientConfig:
    """Configuration for the sweer client"""
    port: int = int(os.getenv("SWEER_PORT", "8009"))
    autoscreenshot: bool = os.getenv("SWEER_AUTOSCREENSHOT", "1") == "1"
    screenshot_mode: ScreenshotMode = ScreenshotMode(
        os.getenv("SWEER_SCREENSHOT_MODE", ScreenshotMode.SAVE.value)
    )


@dataclass
class ServerConfig:
    """Configuration for the sweer server"""
    port: int = int(os.getenv("SWEER_PORT", "8009"))
    window_width: int = int(os.getenv("SWEER_WINDOW_WIDTH", 1024))
    window_height: int = int(os.getenv("SWEER_WINDOW_HEIGHT", 768))
    headless: bool = os.getenv("SWEER_HEADLESS", "1") != "0"
    screenshot_delay: float = float(os.getenv("SWEER_SCREENSHOT_DELAY", 0.2))
    browser_type: str = os.getenv("SWEER_BROWSER_TYPE", "chromium")
    reconnect_timeout: float = float(os.getenv("SWEER_RECONNECT_TIMEOUT", 15))
    chromium_executable_path: str | None = os.getenv("SWEER_CHROMIUM_EXECUTABLE_PATH")
    firefox_executable_path: str | None = os.getenv("SWEER_FIREFOX_EXECUTABLE_PATH")
    crosshair_id: str = "__sweer_crosshair__"
