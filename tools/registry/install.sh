#!/usr/bin/env bash

# script_dir=$(dirname "$(readlink -f "$0")")
bundle_dir=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# Tool entrypoints add registry/lib to sys.path locally. Avoid exporting
# PYTHONPATH here — it breaks editable installs in agent containers (#1249).
export SWE_AGENT_REGISTRY_LIB="$bundle_dir/lib"