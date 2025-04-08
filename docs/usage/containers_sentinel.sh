#!/bin/bash

while true; do
    echo "Checking for long-running containers..."
    # List all running containers with their uptime
    docker ps --format "{{.ID}} {{.RunningFor}}" | while read -r id running_for; do
        # Extract the number and unit from the running time
        if [[ $running_for =~ ([0-9]+)\ (hour|hours) ]]; then
            hours=${BASH_REMATCH[1]}
            if (( hours >= 2 )); then
                echo "Killing container $id (running for $running_for)..."
                docker kill "$id"
            fi
        elif [[ $running_for =~ ([0-9]+)\ (day|days) ]]; then
            # If it's running for at least a day, it's definitely over 2 hours
            echo "Killing container $id (running for $running_for)..."
            docker kill "$id"
        fi
    done
    echo "Sleeping for 10 minutes..."
    sleep 600  # Wait 600 seconds (10 minutes) before running again
done