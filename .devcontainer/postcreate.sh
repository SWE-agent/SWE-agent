#!/usr/bin/env bash

set -euo pipefail
set -x

./.devcontainer/setup_status.sh start

{
    pip install -e '.' && \
    ./.devcontainer/setup_status.sh complete
} || {
    ./.devcontainer/setup_status.sh failed
    exit 1
}
