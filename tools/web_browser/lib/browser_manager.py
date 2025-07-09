from __future__ import annotations

import base64
import contextlib
from pathlib import Path
import threading
import time
from typing import Any

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from web_browser_config import ServerConfig

config = ServerConfig()

SUPPORTED_BROWSERS = {"chromium", "firefox"}

CROSSHAIR_JS = """
([x, y, id]) => {
    const size = 20;
    const thickness = 3;
    const hId = id + '_h';
    const vId = id + '_v';
    
    const createLine = (elementId, styles) => {
        let line = document.getElementById(elementId);
        if (!line) {
            line = document.createElement('div');
            line.id = elementId;
            Object.assign(line.style, {
                position: 'fixed',
                pointerEvents: 'none',
                zIndex: '2147483647',
                backgroundColor: 'red',
                boxSizing: 'border-box',
                margin: '0',
                padding: '0',
                border: 'none',
                outline: 'none',
                transform: 'translateZ(0)',
                ...styles
            });
            document.body.appendChild(line);
        }
        return line;
    };
    
    const hLine = createLine(hId, {
        width: `${size}px`,
        height: `${thickness}px`,
        left: `${Math.round(x - size / 2)}px`,
        top: `${Math.round(y - thickness / 2)}px`
    });
    
    const vLine = createLine(vId, {
        width: `${thickness}px`,
        height: `${size}px`,
        left: `${Math.round(x - thickness / 2)}px`,
        top: `${Math.round(y - size / 2)}px`
    });
}
"""


REMOVE_CROSSHAIR_JS = """
(id) => {
    const hEl = document.getElementById(id + '_h');
    const vEl = document.getElementById(id + '_v');
    if (hEl) hEl.remove();
    if (vEl) vEl.remove();
}
"""


KEY_MAP = {    
    # Function keys
    "f1": "F1", "f2": "F2", "f3": "F3", "f4": "F4", "f5": "F5", "f6": "F6",
    "f7": "F7", "f8": "F8", "f9": "F9", "f10": "F10", "f11": "F11", "f12": "F12",

    # Number keys (top row)
    "0": "Digit0", "1": "Digit1", "2": "Digit2", "3": "Digit3", "4": "Digit4",
    "5": "Digit5", "6": "Digit6", "7": "Digit7", "8": "Digit8", "9": "Digit9",
    
    # Letter keys
    "a": "KeyA", "b": "KeyB", "c": "KeyC", "d": "KeyD", "e": "KeyE", "f": "KeyF",
    "g": "KeyG", "h": "KeyH", "i": "KeyI", "j": "KeyJ", "k": "KeyK", "l": "KeyL",
    "m": "KeyM", "n": "KeyN", "o": "KeyO", "p": "KeyP", "q": "KeyQ", "r": "KeyR",
    "s": "KeyS", "t": "KeyT", "u": "KeyU", "v": "KeyV", "w": "KeyW", "x": "KeyX",
    "y": "KeyY", "z": "KeyZ",
    
    # Arrow keys
    "up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft", "right": "ArrowRight",
    "arrow_up": "ArrowUp", "arrow_down": "ArrowDown", "arrow_left": "ArrowLeft", "arrow_right": "ArrowRight",
    
    # Navigation keys
    "home": "Home", "end": "End", "page_up": "PageUp", "page_down": "PageDown",
    "pageup": "PageUp", "pagedown": "PageDown",
    
    # Editing keys
    "backspace": "Backspace", "delete": "Delete", "insert": "Insert",
    "enter": "Enter", "return": "Enter", "tab": "Tab", "escape": "Escape", "esc": "Escape",
    
    # Modifier keys
    "shift": "Shift", "ctrl": "Control", "control": "Control", "alt": "Alt", "meta": "Meta",
    "shift_left": "ShiftLeft", "ctrl_or_meta": "ControlOrMeta", "control_or_meta": "ControlOrMeta",
    
    # Punctuation and symbols
    "space": " ", "spacebar": " ",
    "backquote": "Backquote", "`": "Backquote", "backtick": "Backquote",
    "minus": "Minus", "-": "Minus", "dash": "Minus",
    "equal": "Equal", "=": "Equal", "equals": "Equal",
    "backslash": "Backslash", "\\": "Backslash",
    "bracket_left": "BracketLeft", "[": "BracketLeft",
    "bracket_right": "BracketRight", "]": "BracketRight",
    "semicolon": "Semicolon", ";": "Semicolon",
    "quote": "Quote", "'": "Quote", "apostrophe": "Quote",
    "comma": "Comma", ",": "Comma",
    "period": "Period", ".": "Period", "dot": "Period",
    "slash": "Slash", "/": "Slash",
    
    # Numpad keys
    "numpad_0": "Numpad0", "numpad_1": "Numpad1", "numpad_2": "Numpad2", "numpad_3": "Numpad3",
    "numpad_4": "Numpad4", "numpad_5": "Numpad5", "numpad_6": "Numpad6", "numpad_7": "Numpad7",
    "numpad_8": "Numpad8", "numpad_9": "Numpad9",
    "numpad_add": "NumpadAdd", "numpad_subtract": "NumpadSubtract",
    "numpad_multiply": "NumpadMultiply", "numpad_divide": "NumpadDivide",
    "numpad_decimal": "NumpadDecimal", "numpad_enter": "NumpadEnter",
    
    # Lock keys
    "caps_lock": "CapsLock", "capslock": "CapsLock",
    "num_lock": "NumLock", "numlock": "NumLock",
    "scroll_lock": "ScrollLock", "scrolllock": "ScrollLock",
    
    # Common combinations (case-insensitive aliases)
    "ENTER": "Enter", "ESCAPE": "Escape", "BACKSPACE": "Backspace", "DELETE": "Delete",
    "TAB": "Tab", "SPACE": " ", "UP": "ArrowUp", "DOWN": "ArrowDown", 
    "LEFT": "ArrowLeft", "RIGHT": "ArrowRight", "HOME": "Home", "END": "End",
}


class BrowserManager:
    """Manages Playwright browser instance with proper resource cleanup."""
    
    def __init__(self):
        self.headless = config.headless
        self.browser_type = self._validate_browser_type(config.browser_type)
        self.page: Page | None = None
        self.screenshot_index = 0
        self.mouse_x = 0
        self.mouse_y = 0
        self._lock = threading.RLock()
        self.window_width = config.window_width
        self.window_height = config.window_height
        self.screenshot_delay = config.screenshot_delay
        self.reconnect_timeout = config.reconnect_timeout
        self.crosshair_id = config.crosshair_id
        self.console_messages: list[dict[str, Any]] = []
        self._init_browser()
    
    def _validate_browser_type(self, browser_type: str) -> str:
        """Validate and return the browser type."""
        browser_type = browser_type.lower()
        if browser_type not in SUPPORTED_BROWSERS:
            msg = (
                f"Unsupported browser type: {browser_type}. "
                f"Supported browsers: {', '.join(sorted(SUPPORTED_BROWSERS))}"
            )
            raise ValueError(msg)
        return browser_type
    
    def _init_browser(self):
        self.playwright: Playwright = sync_playwright().start()
        browser_launcher = getattr(self.playwright, self.browser_type)
        executable_path = None
        if self.browser_type == "chromium" and config.chromium_executable_path:
            executable_path = config.chromium_executable_path
        elif self.browser_type == "firefox" and config.firefox_executable_path:
            executable_path = config.firefox_executable_path
        launch_options = {"headless": self.headless}
        if executable_path and Path(executable_path).exists():
            launch_options["executable_path"] = executable_path
        elif executable_path:
            print(
                f"Warning: Executable path '{executable_path}' does not exist, using default browser"
            )
        self.browser: Browser = browser_launcher.launch(**launch_options)
    
    @property
    def browser_name(self) -> str:
        """Get the name of the browser."""
        return self.browser.browser_type.name
    
    @contextlib.contextmanager
    def _browser_lock(self):
        """Context manager for thread-safe browser operations."""
        with self._lock:
            yield self._ensure_browser()
    
    def _ensure_browser(self) -> Page:
        """Launch Chromium lazily and move cursor to (0,0) once."""
        if self.page is not None:
            return self.page
        ctx = self.browser.new_context(
            viewport={"width": self.window_width, "height": self.window_height}
        )
        self.page = ctx.new_page()
        self._setup_console_listener(self.page)
        self.page.mouse.move(0, 0)
        self.mouse_x = self.mouse_y = 0
        return self.page
    
    def is_website_open(self) -> bool:
        """Check if a website is currently open."""
        return self.page is not None and self.page.url not in (None, "about:blank", "")
    
    def cleanup(self):
        """Clean up browser resources safely."""
        with self._lock:
            for resource, name in [
                (self.page, "page"),
                (self.browser, "browser"), 
                (self.playwright, "playwright")
            ]:
                if resource is not None:
                    try:
                        if name == "playwright":
                            resource.stop()
                        else:
                            resource.close()
                    except Exception:
                        pass  # Ignore cleanup errors
            
            self.browser = self.page = self.playwright = None
    
    def _inject_crosshair(self, page: Page, x: int, y: int) -> bool:
        """Inject crosshair at given coordinates. Returns True if successful."""
        try:
            page.evaluate(CROSSHAIR_JS, [x, y, self.crosshair_id])
            return True
        except Exception:
            return False
    
    def _remove_crosshair(self, page: Page) -> None:
        """Remove crosshair elements from the page."""
        try:
            page.evaluate(REMOVE_CROSSHAIR_JS, self.crosshair_id)
        except Exception:
            pass
    
    def take_screenshot(self) -> dict[str, Any]:
        """Capture screenshot with crosshair."""
        with self._browser_lock() as page:
            # this retry logic is a hack to ensure the page is loaded
            # (at least enough to inject the crosshair)
            timeout = time.time() + self.reconnect_timeout
            while time.time() < timeout:
                if self._inject_crosshair(page, self.mouse_x, self.mouse_y):
                    break
                time.sleep(max(0.3, self.screenshot_delay))
            time.sleep(self.screenshot_delay)
            screenshot_data = page.screenshot(type="png")
            self._remove_crosshair(page)
            self.screenshot_index += 1
            return {
                "screenshot": base64.b64encode(screenshot_data).decode(),
                "screenshot_index": self.screenshot_index,
            }
    
    def validate_coordinates(self, x: int, y: int) -> tuple[bool, bool]:
        x_is_valid = 0 <= x <= self.window_width
        y_is_valid = 0 <= y <= self.window_height
        return (x_is_valid, y_is_valid)
    
    def constrain_mouse_position(self, page: Page) -> bool:
        """Constrain mouse position to window bounds and move if needed.
        """
        if self.window_width <= 0 or self.window_height <= 0:
            return False
        if self.mouse_x >= self.window_width or self.mouse_y >= self.window_height:
            self.mouse_x = min(self.mouse_x, self.window_width - 1)
            self.mouse_y = min(self.mouse_y, self.window_height - 1)
            self.mouse_x = max(0, self.mouse_x)
            self.mouse_y = max(0, self.mouse_y)
            page.mouse.move(self.mouse_x, self.mouse_y)
            return True
        return False

    def get_key(self, key: str) -> str:
        """Get the key from the key map."""
        if key.lower() in KEY_MAP:
            return KEY_MAP[key.lower()]
        msg = f"Key {key} not found. Supported keys: {', '.join(KEY_MAP.keys())}"
        raise ValueError(msg)

    def key_down(self, key: str):
        """Press and hold a key."""
        playwright_key = self.get_key(key)
        self.page.keyboard.down(playwright_key)

    def key_press(self, key: str):
        """Press a key."""
        playwright_key = self.get_key(key)
        self.page.keyboard.press(playwright_key)

    def key_up(self, key: str):
        """Release a key."""
        playwright_key = self.get_key(key)
        self.page.keyboard.up(playwright_key)

    def _setup_console_listener(self, page: Page):
        """Set up console message listener for the page."""
        def on_console(msg):
            self.console_messages.append({
                "type": msg.type,
                "text": msg.text,
                "timestamp": time.time(),
                "location": msg.location
            })
        page.on("console", on_console)
    
    def get_console_output(self) -> list[dict[str, Any]]:
        """Get all console messages and clear the buffer."""
        with self._lock:
            messages = self.console_messages.copy()
            self.console_messages.clear()
            return messages
