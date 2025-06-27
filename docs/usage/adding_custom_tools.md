# Adding Custom Tools

!!! abstract "Adding custom tools to SWE-agent"
    This tutorial walks you through creating and integrating custom tools into SWE-agent.
    We'll create a fun `print_cat` command that prints ASCII art of a cat for morale boost!

    Please read our [hello world](hello_world.md) and [command line basics](cl_tutorial.md) tutorials before proceeding.

## Understanding Tool Structure

Every SWE-agent tool is organized as a "bundle" - a directory containing:

1. **`config.yaml`** - Defines the tool's interface and documentation
2. **`bin/`** directory - Contains the executable scripts
3. **`install.sh`** (optional) - Sets up dependencies
4. **`lib/`** (optional) - Contains shared libraries or utilities

Let's look at the simple `submit` tool structure:

```
tools/submit/
├── config.yaml
└── bin/
    └── submit
```

## Step 1: Write the Command Script

First, let's create our `morale_boost` tool bundle:

```bash
mkdir -p tools/morale_boost/bin
```

Create the executable script that will be called when the agent runs your command:

```bash title="tools/morale_boost/bin/print_cat"
#!/bin/bash

# print_cat - A morale-boosting ASCII cat printer!

echo "🐱 Here's a cat to boost your morale! 🐱"
echo ""
cat << 'EOF'
 /\_/\
( o.o )
 > ^ <
 _) (_
(_____)
EOF
echo ""
echo "You're doing great! Keep coding! 💪"
```

If you're wondering about the strange `EOF` construct, those are called
[heredocs](https://linuxize.com/post/bash-heredoc/) and enable multiline
arguments in bash.

## Step 2: Define the Tool Configuration

Create the `config.yaml` file that tells SWE-agent about your tool:

```yaml title="tools/morale_boost/config.yaml"
tools:
  print_cat:
    signature: "print_cat"
    docstring: "Prints an ASCII art cat for morale boost. Use when you need encouragement!"
    arguments: []
```

!!! tip "Tool Configuration Options"

    The `config.yaml` supports various options:

    - **`signature`**: How the command should be called (including arguments)
    - **`docstring`**: Description that helps the AI understand when to use this tool
    - **`arguments`**: List of arguments with types, descriptions, and whether they're required

For a tool with arguments, it would look like this:

```yaml title="Example with arguments"
tools:
  print_animal:
    signature: "print_animal <animal_type> [--size=<size>]"
    docstring: "Prints ASCII art of the specified animal"
    arguments:
      - name: animal_type
        type: string
        description: "Type of animal to print (cat, dog, elephant)"
        required: true
      - name: size
        type: string
        description: "Size of the art (small, medium, large)"
        required: false
```

## Step 3: Tell the agent to use the new tool

Now you need to tell SWE-agent to use your new tool. Copy `config/default.yaml` to `config/my_custom_config.yaml`
and make the following modification

```yaml title="config/my_custom_config.yaml"
agent:
  templates:
    instance_template: |-
      (...)

      Don't forget to use `print_cat` when you need encouragement!

      Your thinking should be thorough and so it's fine if it's very long.
    bundles:
      - path: tools/registry
      - path: tools/edit_anthropic
      - path: tools/review_on_submit_m
      - path: tools/morale_boost  # Add our custom tool bundle!
    # everything else stays the same
```

## Step 4: Let's test it

Now you can test your tool by running SWE-agent with your custom configuration:

```bash
sweagent run \
  --config config/my_custom_config.yaml \
  --agent.model.name=gpt-4o \
  --env.repo.github_url=https://github.com/SWE-agent/test-repo \
  --problem_statement.text="Add a simple hello world function to the repository. Feel free to use print_cat for morale!"
```

The agent should now have access to your `print_cat` command and may use it during execution!

## Advanced Tool Features

### Multiple Commands in One Bundle

You can define multiple commands in a single tool bundle:

```yaml title="tools/morale_boost/config.yaml - Extended version"
tools:
  print_cat:
    signature: "print_cat"
    docstring: "Prints an ASCII art cat for morale boost"
    arguments: []
  print_dog:
    signature: "print_dog"
    docstring: "Prints an ASCII art dog for variety"
    arguments: []
  motivate:
    signature: "motivate <message>"
    docstring: "Prints a motivational message with ASCII art"
    arguments:
      - name: message
        type: string
        description: "The motivational message to display"
        required: true
```

Don't forget to create the corresponding scripts in the `bin/` directory!

### Using Python Libraries

If you prefer Python, you can create Python-based tools:

```python title="tools/morale_boost/bin/print_cat"
#!/usr/bin/env python3
"""
A morale-boosting cat printer in Python!
"""

print("🐱 Here's a cat to boost your morale! 🐱")
```

If your Python tool needs additional dependencies, create an `install.sh` script:

```bash title="tools/morale_boost/install.sh"
#!/bin/bash
# This script runs when the tool bundle is installed

# Example: Install Python packages
pip install cowsay
pip install colorama

echo "Morale boost tools installed! Ready to spread joy! 🎉"
```

### Environment Variables and Context

Your tools can access environment variables and the current working context:

```bash title="Example using environment variables"
#!/bin/bash

echo "Current working directory: $PWD"
echo "Repository root: $ROOT"
echo "My custom variable: $MY_CUSTOM_VAR"
```

Adding environment variables in your config file can be a simple way of customizing your tools

```yaml title="config/my_custom_config.yaml"
agent:
  tools:
    env_variables:
      PAGER: cat
      MY_CUSTOM_VAR: "Hello from config!"
      DEBUG_MODE: "true"
    # ... rest of config
```

For sensitive data like API keys, you can propagate environment variables from your host system:

```yaml title="config/my_custom_config.yaml"
agent:
  tools:
    propagate_env_variables:
      - "OPENAI_API_KEY"
      - "GITHUB_TOKEN"
      - "MY_SECRET_KEY"
    # ... rest of config
```

Your tools can then access these variables:

```bash title="tools/morale_boost/bin/print_cat_with_api"
#!/bin/bash

if [ -n "$GITHUB_TOKEN" ]; then
    echo "🐱 Connected to GitHub! Ready to boost morale across repos!"
else
    echo "🐱 Just a local morale booster today!"
fi
```

However, we mostly recommend to use the python bindings of the `registry` bundle for keeping internal
state (instead of using environment variables).

### Using the Registry Bundle

The registry bundle provides a persistent key-value store that survives across tool calls. This is better than environment variables because
you can store complex data structures (lists, dictionaries) as JSON.

**Setting registry variables in your config:**

```yaml title="config/my_custom_config.yaml"
agent:
  tools:
    registry_variables:
      MY_CUSTOM_SETTING: "hello world"
      MORALE_MESSAGES:
        - "You're doing great!"
        - "Keep up the good work!"
        - "Almost there!"
      DEBUG_MODE: true
    bundles:
      - path: tools/registry  # Always include this first!
      - path: tools/morale_boost
```

**Accessing registry variables in your Python tools:**

```python title="tools/morale_boost/bin/print_motivational_cat"
#!/usr/bin/env python3

from registry import registry

def main():
    # Get a simple value with a fallback
    setting = registry.get("MY_CUSTOM_SETTING", "default value")
    print(f"Setting: {setting}")

    # Get a list of messages
    messages = registry.get("MORALE_MESSAGES", [])
    if messages:
        import random
        message = random.choice(messages)
        print(f"🐱 {message}")

    # Set a value (persists across tool calls)
    registry["LAST_MORALE_BOOST"] = "2024-01-15 10:30:00"

    print("Morale boosted! 🚀")

if __name__ == "__main__":
    main()
```

**Accessing registry variables in bash tools:**

```bash title="tools/morale_boost/bin/print_simple_cat"
#!/bin/bash

# Read from registry using the _read_env helper
CUSTOM_SETTING=$(_read_env "MY_CUSTOM_SETTING" "default value")
DEBUG_MODE=$(_read_env "DEBUG_MODE" "false")

echo "🐱 Custom setting: $CUSTOM_SETTING"

if [ "$DEBUG_MODE" = "true" ]; then
    echo "Debug mode is enabled!"
fi
```

The registry is particularly useful for complex tools that need to maintain state across multiple invocations, like the `review_on_submit_m` tool that tracks submission stages.

## State commands and more

Take a look at our [tool documentation](../config/tools.md).

{% include-markdown "../_footer.md" %}