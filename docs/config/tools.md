# Configuring tools

Tools are one one of the ways to configure and extend the agent.

Typically, there is

* The `bash` tool, allowing the agent to run shell commands (including invoking python scripts)
* Specific tools for the agent to inspect the code (file viewer, etc)
* Code editors (for example with search and replace or line range based methods)

With SWE-agent, these tools are organized in _tool bundles_.

Each tool bundle is a folder with the following structure:

```
bundle/
├── bin/
│   └── <tool executable>
│   └── <state executable>
├── config.yaml
├── install.sh
├── README.md
└── pyproject.toml
```

The `bin/` folder contains the actual tool implementation as executables.

Here's an example of a tool bundle config:

```yaml
tools:
  filemap:
    signature: "filemap <file_path>"
    docstring: "Print the contents of a Python file, skipping lengthy function and method definitions."
    arguments:
      - name: file_path
        type: string
        description: The path to the file to be read
        required: true
```

Another important key is the `state` field.
The `state` command is a special command that is executed after every action and returns a json string that we parse.
The resulting dictionary can be used to format prompt templates.
For example, for the classical SWE-agent tools, we extract the working directory and the currently open file like so:

```python title="tools/windowed/bin/_state"
#!/usr/bin/env python3

import json
import os
from pathlib import Path

from registry import registry  # type: ignore


def main():
    current_file = registry.get("CURRENT_FILE")
    open_file = "n/a" if not current_file else str(Path(current_file).resolve())
    state = {"open_file": open_file, "working_dir": os.getcwd()}

    print(json.dumps(state))

if __name__ == "__main__":
    main()
```

TO use it, we set the following config key

```yaml
tools:
    ...
state_command: "_state"
```

To see the full specification of the state command, see the [tool config documentation](../reference/bundle_config.md).