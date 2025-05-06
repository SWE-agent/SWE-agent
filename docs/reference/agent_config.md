# Agent configuration

This page documents the configuration objects used to specify the behavior of an agent.
To learn about the agent class itself, see the [agent class reference page](agent.md).

It might be easiest to simply look at some of our example configurations in the [config dir](https://github.com/SWE-agent/SWE-agent/tree/main/config).

<details>
<summary>Example: default config <code>anthropic_filemap.yaml</code></summary>

```yaml
--8<-- "config/default_from_url.yaml"
```
</details>

Currently, there are two main agent classes:

* `DefaultAgentConfig`: This is the default agent.
* `RetryAgentConfig`: A "meta agent" that instantiates multiple agents for multiple attempts and then picks the best solution.

::: sweagent.agent.agents.RetryAgentConfig

::: sweagent.agent.agents.DefaultAgentConfig