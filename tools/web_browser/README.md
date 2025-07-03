# Web Browser Tool Bundle

A unified web browser automation tool that consolidates all browser functionality into a single command with subcommands, following the design pattern of `str_replace_editor`.

## Overview

The `web_browser` tool provides a single entry point for all browser automation tasks, replacing the multiple individual executables from the `browser` bundle with a unified command interface.

## Usage

Instead of using separate commands like `click_mouse`, `type_text`, etc., you now use:

```bash
web_browser <command> [options...]
```

## Available Commands

- `open_site` - Open a website URL or local file
- `close_site` - Close the current browser window
- `screenshot_site` - Take a screenshot of the current page
- `click_mouse` - Click at specified coordinates on the page
- `double_click_mouse` - Double-click at specified coordinates
- `move_mouse` - Move mouse cursor to specified coordinates
- `drag_mouse` - Drag mouse along a path of coordinates
- `type_text` - Type text at the currently focused element
- `scroll_on_page` - Scroll the page by specified pixel amounts
- `execute_script_on_page` - Execute custom JavaScript on the page
- `navigate_back` - Go back in browser history
- `navigate_forward` - Go forward in browser history
- `reload_page` - Refresh the current page
- `wait_time` - Wait for specified milliseconds
- `press_keys_on_page` - Press key combinations
- `set_browser_window_size` - Resize the browser window
- `get_console_output` - Get browser console logs and errors

## Examples

```bash
# Open a website
web_browser open_site --url "https://example.com"

# Click at coordinates
web_browser click_mouse --x 100 --y 200 --button left

# Type text
web_browser type_text --text "Hello World"

# Execute JavaScript
web_browser execute_script_on_page --script "console.log('Hello')"

# Scroll the page
web_browser scroll_on_page --scroll_x 0 --scroll_y 300

# Take a screenshot
web_browser screenshot_site

# Press key combinations
web_browser press_keys_on_page --keys '["ctrl", "c"]'

# Drag mouse along a path
web_browser drag_mouse --path '[[100,100],[200,200],[300,150]]'
```

## Dependencies

This tool reuses the backend infrastructure from the `browser` tool bundle:

- Flask server for HTTP API
- Playwright for browser automation
- Browser manager for state and session management

## Installation

The tool automatically installs required dependencies and starts the browser server if needed. It reuses the same server instance as the browser bundle to avoid conflicts.

## Architecture

- **Frontend**: Single `web_browser` executable with argument parsing
- **Backend**: Reuses browser's Flask server and browser management
- **Libraries**: Copies of browser's library files for configuration and utilities
- **State**: Maintains browser state across command calls