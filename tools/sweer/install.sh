#!/usr/bin/env bash

pip install flask requests playwright

playwright install-deps chromium

if [ -f /usr/bin/google-chrome ]; then
    export SWEER_CHROMIUM_EXECUTABLE_PATH=/usr/bin/google-chrome
elif [ -f /usr/bin/chromium ]; then
    export SWEER_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium
elif [ -f /usr/bin/google-chrome-stable ]; then
    export SWEER_CHROMIUM_EXECUTABLE_PATH=/usr/bin/google-chrome-stable
else
    playwright install chromium
fi

export SWEER_SCREENSHOT_MODE=print

export SWEER_PORT=19321

mkdir -p /root/.sweer_logs

run_sweer_server &> /root/.sweer_logs/sweer-server.log &
