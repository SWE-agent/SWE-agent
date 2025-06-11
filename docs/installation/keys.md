# Models and API keys

!!! abstract "Setting up models"
    This page shows how you can set up your LM with SWE-agent

    * Generally all API models work out of the box by just adding the key and specifying `--agent.model.name`
    * More care must be taken for local models (see tips below!)

## Setting API keys

In order to access the LM of your choice (and to access private GitHub repositories), you need to supply the corresponding keys.

There are two options to do this:

1. Set the corresponding [environment variables](https://www.cherryservers.com/blog/how-to-set-list-and-manage-linux-environment-variables).
2. Create a `.env` file at the root of this repository. All of the variables defined there will take the place of environment variables.
3. Use `--agent.model.api_key` to set the key

Here's an example

```bash
# Remove the comment '#' in front of the line for all keys that you have set
# GITHUB_TOKEN='GitHub Token for access to private repos'
# OPENAI_API_KEY='OpenAI API Key Here if using OpenAI Model'
# ANTHROPIC_API_KEY='Anthropic API Key Here if using Anthropic Model'
# TOGETHER_API_KEY='Together API Key Here if using Together Model'
```

See the following links for tutorials on obtaining [Anthropic](https://docs.anthropic.com/en/api/getting-started), [OpenAI](https://platform.openai.com/docs/quickstart/step-2-set-up-your-api-key), and [Github](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) tokens.

!!! tip "Advanced settings"

    See [model config](../config/models.md) for more details on advanced settings.

## Supported API models

We support all models supported by [litellm](https://github.com/BerriAI/litellm), see their list [here](https://docs.litellm.ai/docs/providers).

!!! tip "Custom model registries"

    If you're using a model that's not in the default litellm model registry (e.g., custom local models or new models), you can provide a custom model registry file using the `litellm_model_registry` configuration option. This allows proper cost tracking for any model. See the [custom model registry section](#custom-model-registry-for-cost-tracking) below for details.

Here are a few options for `--agent.model.name`:

| Model | API key | Comment |
| ----- | ------- | ------- |
| `claude-sonnet-4-20250514)` | `ANTHROPIC_API_KEY` | Our recommended model |
| `gpt-4o` | `OPENAI_API_KEY` | |
| `o1-preview` | `OPENAI_API_KEY` | You might need to set temperature and sampling to the supported values. |

!!! warning "Function calling and more: Setting the correct parser"

    The default config uses function calling to retrieve actions from the model response, i.e.,
    the model directly provides the action as a JSON object.
    If your model doesn't support function calling, you can use the `thought_action` parser by setting
    `agent.tools.parse_function.type` to `thought_action`.
    Then, we extract the last triple-backticks block from the model response as the action.
    See [our API docs](../reference/parsers.md) for more details on parsers.
    Remember to document the tools in your prompt as the model will not be able to see the function signature
    like with function calling.

!!! tip "Specific models"

    See [model config](../config/models.md) for more details on specific models.

## Using local models

We currently support all models that serve to an endpoint with an OpenAI-compatible API.

For example, to use llama, you can follow the [litellm instructions](https://docs.litellm.ai/docs/providers/ollama) and set

```yaml title="config/your_config.yaml"
agent:
  model:
    name: ollama/llama2  # (1)!
    api_base: http://localhost:11434
    per_instance_cost_limit: 0   # (2)!
    total_cost_limit: 0
    per_instance_call_limit: 100
    max_input_tokens: 0  # (3)!
  tools:
    # The default for obtaining actions from model outputs is function calling.
    # If your local model does not support that, you can use the thought_action parser
    # instead (see below)
    parse_function:
      type: "thought_action"
  # You probably do not need the cache control history processor if you're not
  # using Claude, so please remove it if it's in your config.
  history_processors: []
```

1. Make sure that your model includes a "provider", i.e., follows the form `provider/model_name`. The model name and provider might be arbitrarily chosen.
2. We cannot track costs, so you must disable this (see below)
3. Disable max input tokens check

in your [config file](../config/config.md).
Note that you're always ingesting a config file: If you haven't specified it manually with `--config`, we're loading a default config, which might not
what you want (in particular, it uses function calling and prompt caching)!
If you're using a [litellm proxy](https://docs.litellm.ai/docs/providers/openai_compatible#usage-with-litellm-proxy-server), make sure to set your `agent.model.name` to `openai/...`
and set `agent.model.api_key` to the key you've configured for your proxy (or a random value; it cannot be empty).

!!! warning "Model providers"

    Make sure that your model name includes a "provider", i.e., follows the form `provider/model_name`. The model name and provider might be arbitrarily chosen
    for local models.

!!! warning "Cost/token limits"

    If you do not disable the default cost limits, you will see an error because the cost calculator will not be able to find the model in the `litellm` model cost dictionary.

    You have two options:

    1. **Disable cost tracking** (recommended for most users): Set `per_instance_cost_limit` to 0 and use the `per_instance_call_limit` instead to limit the runtime per issue.
    2. **Use a custom model registry**: If you want to track costs for your local model, you can provide a custom `litellm_model_registry` file with cost information for your model (see below).

    Please also make sure to set `max_input_tokens` to a non-`None` value to avoid other warnings.

### Custom model registry for cost tracking

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

!!! warning "Parsing functions"

    The default config uses function calling to retrieve actions from the model response, i.e.,
    the model directly provides the action as a JSON object.
    If your model doesn't support function calling, you can use the `thought_action` parser by setting
    `agent.tools.parse_function.type` to `thought_action`.
    Then, we extract the last triple-backticks block from the model response as the action.
    See [our API docs](../reference/parsers.md) for more details on parsers.
    Remember to document the tools in your prompt as the model will not be able to see the function signature
    like with function calling.

!!! warning "Message types"

    The `cache_control` history processor requires a different message format
    (e.g., `{'role': 'user', 'content': [{'type': 'text', 'text': 'some text', 'cache_control': {'type': 'ephemeral'}}]}]`).
    This might not be understood by all language models.
    Therefore, please remove this history processor if you do not need it
    (it's currently mostly used for anthropic cache control).
    See [#957](https://github.com/SWE-agent/SWE-agent/issues/957) for more information.

## Something went wrong?

* If you get `Error code: 404`, please check your configured keys, in particular
  whether you set `OPENAI_API_BASE_URL` correctly (if you're not using it, the
  line should be deleted or commented out).
  Also see [this issue](https://github.com/SWE-agent/SWE-agent/issues/467)
  for reference.


## Further reads & debugging

!!! hint "Further reads"

    See [our API docs](../reference/model_config.md) for all available options.
    Our [model config page](../config/models.md) has more details on specific models and tips and tricks.

{% include-markdown "../_footer.md" %}
