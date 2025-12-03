# History processor configuration

History processors can filter the history/trajectory to query the model.
For example, a very simple history processor would be one that strips away old observations to reduce context when querying the model.

You can set them as follows:

```yaml
agent:
  history_processors:
    - type: last_n_observations
      n: 5
```

::: sweagent.agent.history_processors.DefaultHistoryProcessor

::: sweagent.agent.history_processors.LastNObservations

::: sweagent.agent.history_processors.TagToolCallObservations

::: sweagent.agent.history_processors.CacheControlHistoryProcessor

::: sweagent.agent.history_processors.RemoveRegex