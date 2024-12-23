# Model Configuration

SWE-agent supports various model configurations through its flexible model system. Here are the available model types:

## Generic API Model
The base model configuration that works with any LiteLLM-supported model:

```yaml
agent:
  model:
    name: gpt-4  # Any LiteLLM supported model
    temperature: 0.0
    top_p: 0.95
    per_instance_cost_limit: 3.0
    total_cost_limit: 0.0
```

## Ollama Local Models
For running local models through Ollama:

```yaml
agent:
  model:
    name: ollama
    model_id: llama2  # Any Ollama model identifier
    api_base: http://localhost:11434  # Ollama API endpoint
    temperature: 0.0
    top_p: 0.95
    per_instance_cost_limit: 0.0  # Local models have no cost
    total_cost_limit: 0.0
```

## Replay Model
For replaying recorded trajectories:

```yaml
agent:
  model:
    name: replay
    replay_path: path/to/replay.json
```

## Human Model
For interactive human input:

```yaml
agent:
  model:
    name: human
```

## Human Thought Model
For interactive human input with thought process:

```yaml
agent:
  model:
    name: human_thought
```

## Instant Empty Submit Model
For testing purposes:

```yaml
agent:
  model:
    name: instant_empty_submit
```
