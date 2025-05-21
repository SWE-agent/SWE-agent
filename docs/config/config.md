# Configuration

This page contains details describing how to write your own configurations to control how agents can interact with the `SWEEnv` environment.

A configuration is represented in one or more `.yaml` files, specified by the `--config` flag in the [command line interface](../usage/cl_tutorial.md), allowing you to...

* Define the [**tools**](tools.md) that agents may use to traverse + modify a codebase.
* Write [**prompts**](templates.md) that are deterministically/conditionally shown to the agent over the course of a single trajectory.
* Use [**demonstrations**](demonstrations.md) to guide the agent's behavior.
* Change the [**model behavior**](models.md) of the agent.
* Control the **input/output interface** that sits between the agent and the environment

!!! tip "Default config files"
    Our default config files are in the [`config/`](https://github.com/SWE-agent/SWE-agent/tree/main/config) directory.

To use a config file, you can use the `--config` flag in the command line interface.

```bash
sweagent run --config config/your_config.yaml
sweagent run-batch --config config/your_config.yaml
```

This is the current default configuration file which is loaded when no `--config` flag is provided:

<details>
<summary><code>default.yaml</code></summary>

```yaml title="config/default.yaml"
--8<-- "config/default.yaml"
```
</details>

!!! hint "Relative paths"
    Relative paths in config files are resolved to the `SWE_AGENT_CONFIG_ROOT` environment variable (if set)
    or the SWE-agent repository root.

