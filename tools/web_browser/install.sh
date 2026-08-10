#!/usr/bin/env bash

STANDALONE_DIR=${SWE_AGENT_PYTHON_STANDALONE_DIR:-/usr/local}

"$STANDALONE_DIR/bin/python3" -m pip install flask requests playwright || true
"$STANDALONE_DIR/bin/python3" -m playwright install-deps chromium || true

if [ -f /usr/bin/google-chrome ]; then
    export WEB_BROWSER_CHROMIUM_EXECUTABLE_PATH=/usr/bin/google-chrome
elif [ -f /usr/bin/chromium ]; then
    export WEB_BROWSER_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium
elif [ -f /usr/bin/google-chrome-stable ]; then
    export WEB_BROWSER_CHROMIUM_EXECUTABLE_PATH=/usr/bin/google-chrome-stable
else
    "$STANDALONE_DIR/bin/python3" -m playwright install chromium || true
fi

export WEB_BROWSER_SCREENSHOT_MODE=print
export WEB_BROWSER_PORT=19321

WEB_BROWSER_LOG_DIR=${SWE_AGENT_ROOT_PATH:-/tmp}/.web_browser_logs
mkdir -p "$WEB_BROWSER_LOG_DIR"

run_web_browser_server &> "$WEB_BROWSER_LOG_DIR/web-browser-server.log" &
