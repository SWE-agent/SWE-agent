#!/usr/bin/env bash

# This script manages the setup status for GitHub Codespaces
# It creates and updates a status file that can be checked by the CLI

set -euo pipefail

STATUS_FILE="${HOME}/.swe_agent_setup_status"

function mark_setup_started() {
    echo "setup_started" > "${STATUS_FILE}"
    chmod 644 "${STATUS_FILE}"  # Ensure file is readable by all users
}

function mark_setup_complete() {
    echo "setup_complete" > "${STATUS_FILE}"
    chmod 644 "${STATUS_FILE}"  # Ensure file is readable by all users
}

function mark_setup_failed() {
    echo "setup_failed" > "${STATUS_FILE}"
    chmod 644 "${STATUS_FILE}"  # Ensure file is readable by all users
}

# Create status file if it doesn't exist
touch "${STATUS_FILE}"
chmod 644 "${STATUS_FILE}"  # Ensure file is readable by all users

case "${1:-}" in
    "start")
        mark_setup_started
        ;;
    "complete")
        mark_setup_complete
        ;;
    "failed")
        mark_setup_failed
        ;;
    *)
        echo "Usage: $0 {start|complete|failed}"
        exit 1
        ;;
esac
