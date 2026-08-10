#!/usr/bin/env bash

# Define variables to exclude
EXCLUDE_VARS="PWD|LANG|PYTHONPATH|ROOT|PS0|PS1|PS2|_|OLDPWD|LC_ALL|LANG|LSCOLORS|SHLVL"


echo "Original Environment Variables:"
env | sort

# Only add Python 3.11 to PATH if no python exists
if ! command -v python &> /dev/null; then
    echo -e "\nNo Python found in system, adding Python 3.11 to PATH"
    STANDALONE_DIR=${SWE_AGENT_PYTHON_STANDALONE_DIR:-/usr/local}
    export PATH="$STANDALONE_DIR/bin:$PATH"

    # Create python/pip aliases if they don't already exist
    if [ -x "$STANDALONE_DIR/bin/python3" ] && [ ! -e "$STANDALONE_DIR/bin/python" ]; then
        ln -s "$STANDALONE_DIR/bin/python3" "$STANDALONE_DIR/bin/python"
    fi
    if [ -x "$STANDALONE_DIR/bin/pip3" ] && [ ! -e "$STANDALONE_DIR/bin/pip" ]; then
        ln -s "$STANDALONE_DIR/bin/pip3" "$STANDALONE_DIR/bin/pip"
    fi
    echo "Using standalone python dir: $STANDALONE_DIR"
else
    echo -e "\nPython already exists in system, skipping Python 3.11 setup"
fi

# Attempt to read and set process 1 environment
echo -e "\nSetting environment variables from /proc/1/environ..."
if [ -r "/proc/1/environ" ]; then
    while IFS= read -r -d '' var; do
        # Skip excluded variables
        if ! echo "$var" | grep -qE "^(${EXCLUDE_VARS})="; then
            # If the variable is PATH, append and deduplicate
            if [[ "$var" =~ ^PATH= ]]; then
                # Combine paths and remove duplicates while preserving order
                export PATH="$(echo "${PATH}:${var#PATH=}" | tr ':' '\n' | awk '!seen[$0]++' | tr '\n' ':' | sed 's/:$//')"
            else
                export "$var"
            fi
        fi
    done < /proc/1/environ
    echo "Successfully imported environment from /proc/1/environ"
else
    echo "Cannot access /proc/1/environ - Permission denied"
fi

# Print updated environment variables
echo -e "\nUpdated Environment Variables:"
env | sort
