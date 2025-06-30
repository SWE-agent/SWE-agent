# Models

!!! tip "Required reading"

    See [the model section](../installation/keys.md) in the installation guide for a primer before reading the rest of this page.

!!! tip "Related pages"

    * See [the model config reference](../reference/model_config.md) for the full list of model options
    * To control how the agent extracts the actions from the model response, see the [action parsers](../reference/parsers.md) reference

## Notes for specific models

### Local models

See [the model section](../installation/keys.md) in the installation guide.
Remember to unset spending limits and configure the action parser if you cannot support function calling.

For "cost" tracking with local models, you can optionally provide a custom `litellm_model_registry` file in your configuration.
This allows you to define custom pricing information for your local models instead of disabling cost limits entirely.
See the [local models section](../installation/keys.md#custom-model-registry-for-cost-tracking) for detailed instructions.

### Anthropic Claude

Prompt caching makes SWE-agent several times more affordable. While this is done automatically for models like `gpt-4o`,
care has to be taken for Anthropic Claude, as you need to manually set the cache break points.

For this, include the following history processor:

```yaml
agent:
  history_processors:
  - type: cache_control
    last_n_messages: 2
```

!!! warning "Other history processors"

    Other history processors might interfere with the prompt caching
    if you are not careful.
    However, if your history processor is only modifying the last observation,
    you can combine as done [here](https://github.com/SWE-agent/SWE-agent/blob/main/config/sweagent_heavy.yaml).

Anthropic Claude gives you 4 cache break points per key.
You need two of them for a single agent run (because the break points are both used to retrieve and set the cache).
Therefore, you can only run two parallel instances of SWE-agent with [`run-batch`](../usage/batch_mode.md) per key.
To support more parallel running instances, supply multiple keys as described below.

We recommend that you check how often you hit the cache. A very simple way is to go to your trajectory directory and grep like so:

```bash
grep -o "cached_tokens=[0-9]*" django__django-11299.debug.log
```

Note that the maximum number of output tokens of Claude 3.7/4 can be extended with extra headers.
See [this issue in litellm](https://github.com/BerriAI/litellm/issues/8984) and and [swe-agent PR #1035](https://github.com/SWE-agent/SWE-agent/issues/1035)
for omore information.
Since [#1036](https://github.com/SWE-agent/SWE-agent/pull/1036) you can also manually set the maximum output tokens and override the information
from `litellm`.

### o1

Make sure to set

```yaml
agent:
    model:
        top_p: null
        temperature: 1.
```

as other values aren't supported by `o1`.

## Using multiple keys

We support rotating through multiple keys for [`run-batch`](../usage/batch_mode.md). For this, concatenate all keys with `:::` and set them via the `--agent.model.api_key` flag.
Every thread (i.e., every parallel running agent that is working on one task instance) will stick to one key during the entire run, i.e., this does not break prompt caching.


### Custom cost tracking

If you want to track costs for models not in the default litellm registry, you can provide a custom model registry file. This is particularly useful for:

- New models not yet supported by litellm's default registry
- Overriding default / old cost values in litellm
- Local models that you want to track "costs" for, to compare to other results

This file will override entries in the [litellm community model cost file](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json).

Create a JSON file with your model's cost information following the litellm model registry format:

```json title="my_model_registry.json"
{
  "ollama/llama2": {
    "max_tokens": 8192,
    "input_cost_per_token": 0.00002,
    "output_cost_per_token": 0.00006,
    "litellm_provider": "ollama",
    "mode": "chat"
  },
  "my-custom-provider/my-new-model": {
    "max_tokens": 8192,
    "max_input_tokens": 8192,
    "max_output_tokens": 8192,
    "input_cost_per_token": 0.000001,
    "output_cost_per_token": 0.000002,
    "litellm_provider": "openai",
    "mode": "chat"
  }
}
```

Then specify this registry in your config:

```yaml title="config/your_config.yaml"
agent:
  model:
    litellm_model_registry: "my_model_registry.json"  # Path to your custom registry
    ...
```

If you need to modify the tokenizer that is used when calculating costs, you can set the `custom_tokenizer` setting in the [model config](../reference/model_config.md).

## Models for testing

We also provide models for testing SWE-agent without spending any credits

* `HumanModel` and `HumanThoughtModel` will prompt for input from the user that stands in for the output of the LM. This can be used to create new [demonstrations](../config/demonstrations.md#manual).
* `ReplayModel` takes a trajectory as input and "replays it"
* `InstantEmptySubmitTestModel` will create an empty `reproduce.py` and then submit


{% include-markdown "../_footer.md" %}
