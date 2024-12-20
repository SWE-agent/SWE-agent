#!/usr/bin/env bash

set -euo pipefail
set -x

# Mark setup as started
./.devcontainer/setup_status.sh start

# Run from repo root
sudo usermod -aG docker vscode
sudo chmod 666 /var/run/docker.sock

# Install dependencies and setup environment
{
    pip install -e '.' && \
    cp .devcontainer/sample_keys.cfg keys.cfg && \
    cat .devcontainer/bashrc_epilog.sh >> ~/.bashrc && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && \
    sudo apt-get install -y nodejs && \
    ./.devcontainer/show_docs.sh && \
    ./.devcontainer/setup_status.sh complete
} || {
    ./.devcontainer/setup_status.sh failed
    exit 1
}
