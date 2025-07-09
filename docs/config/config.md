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

    For multimodal support, use `config/default_mm_with_images.yaml` which includes image processing capabilities.

To use a config file, you can use the `--config` flag in the command line interface.

```bash
sweagent run --config config/your_config.yaml
sweagent run-batch --config config/your_config.yaml
```

You can also use more than one config file, e.g., `--config config/default.yaml --config my_config.yaml`
(note that you need to repeat `--config`).
Config options are merged in a nested way.

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

## Multimodal Configuration

For working with images and vision-capable models, SWE-agent provides specialized multimodal configuration options.

These options are best demonstrated in `default_mm_with_images.yaml`.

This configuration enables full image processing capabilities:

- **SWE-bench Multimodal Image processing**: Downloads and converts GitHub issue images to base64 format for SWE-bench Multimodal instances.
- **Extended observation length**: Increases observation token limits to accommodate images
- **Image tools**: Includes `image_tools` bundle for viewing images
- **Web browsing tools**: Includes `web_browser` bundle for using web browsers
- **History processing**: Enables `image_parsing` history processor for parsing

### Key Multimodal Settings

```yaml
agent:
  templates:
    disable_image_processing: false  # enable/disable image processing
    max_observation_length: 10_000_000  # increased for images
  tools:
    bundles:
      - path: tools/image_tools  # image viewing capabilities
      - path: tools/web_browser  # browser automation tools
  history_processors:
    - type: image_parsing  # process image tools outputs (required for tools to work)
```

See the [multimodal guide](../usage/multimodal.md) for detailed configuration options.
