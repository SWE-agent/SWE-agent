#!/usr/bin/env bash

bundle_dir=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

export PYTHONPATH=$PYTHONPATH:"$bundle_dir/lib"

# _write_env "AZURE_OPENAI_API_KEY" "$AZURE_OPENAI_API_KEY"
# _write_env "AZURE_OPENAI_ENDPOINT" "$AZURE_OPENAI_ENDPOINT"

# install browser-use
pip install browser-use
playwright install-deps
playwright install