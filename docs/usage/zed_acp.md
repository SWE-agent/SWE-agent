# Zed ACP setup

Run SWE-agent inside the Zed Agent Panel via the Agent Client Protocol (ACP).

## Prerequisites

- SWE-agent installed locally (`pip install -e .` from the repo root).
- A model API key available in the environment (for example `OPENAI_API_KEY`).
- Docker running if you use the default container-based environment.

## 1) Choose a config

Pick a standard SWE-agent config file. The default works for most setups:

```
config/default.yaml
```

You can override settings with CLI flags (for example, the model name).

## 2) Add SWE-agent to Zed

Open your Zed `settings.json` and add a custom agent server:

```json
{
  "agent_servers": {
    "SWE-agent": {
      "type": "custom",
      "command": "sweagent",
      "args": [
        "acp",
        "--config",
        "/absolute/path/to/SWE-agent/config/default.yaml",
        "--agent.model.name",
        "gpt-4o"
      ],
      "env": {
        "OPENAI_API_KEY": "your-api-key"
      }
    }
  }
}
```

Notes:

- Zed launches the agent with the workspace root as the session `cwd`. If your config does not set `env.repo`, SWE-agent will treat that `cwd` as a local repo.
- The local repo is uploaded into the container. By default SWE-agent expects a clean git working tree for local repos.
- Keep ACP output on stdout only. Use stderr for logs if you add custom wrappers.
- If you prefer not to store keys in `settings.json`, omit the `env` block and set your API keys in the environment before launching Zed.

## 3) Start a thread in Zed

1. Open the Agent Panel.
2. Click the `+` button and pick **SWE-agent**.
3. Send a prompt and watch the ACP logs via `dev: open acp logs`.

## Limitations

- Each ACP prompt is treated as a fresh SWE-agent run.
- Tool permission requests are not used (all tool execution happens inside the SWE-agent runtime).
- MCP servers passed by Zed are ignored for now.
