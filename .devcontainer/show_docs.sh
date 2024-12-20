#!/usr/bin/env bash

set -euo pipefail

# Open key documentation files in VS Code
code -r README.md CONTRIBUTING.md docs/installation/codespaces.md docs/dev/contribute.md

# Wait for VS Code to open the files
sleep 2

# Arrange editor layout for better visibility
code --goto README.md:1
