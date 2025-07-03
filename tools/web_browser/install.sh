#!/usr/bin/env bash

# Install dependencies for web browser automation
/root/python3.11/bin/python3 -m pip install flask requests playwright
/root/python3.11/bin/python3 -m playwright install-deps chromium

# Set up browser executable path
if [ -f /usr/bin/google-chrome ]; then
    export BROWSER_CHROMIUM_EXECUTABLE_PATH=/usr/bin/google-chrome
elif [ -f /usr/bin/chromium ]; then
    export BROWSER_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium
elif [ -f /usr/bin/google-chrome-stable ]; then
    export BROWSER_CHROMIUM_EXECUTABLE_PATH=/usr/bin/google-chrome-stable
else
    /root/python3.11/bin/python3 -m playwright install chromium
fi

# Configure environment for web browser tool
export BROWSER_SCREENSHOT_MODE=print
export BROWSER_PORT=19321

# Create log directory
mkdir -p /root/.browser_logs

# Start the browser server in the background for web_browser tool to use
# We reuse the same browser server since web_browser uses the same backend
if ! pgrep -f "run_browser_server" > /dev/null; then
    # Check if we have the browser server available
    if command -v run_browser_server &> /dev/null; then
        run_browser_server &> /root/.browser_logs/browser-server.log &
    else
        echo "Warning: run_browser_server not found. Web browser functionality may not work."
        echo "Make sure the browser tool bundle is also installed or available."
    fi
fi