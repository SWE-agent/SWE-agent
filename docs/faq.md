# Frequently Asked Questions

## Basics

> Does SWE-agent run on Windows/MacOS/Linux?

Yes! Your only limitation might be the availability of the docker containers for your environments.
But you can always execute SWE-agent in the cloud.

> I got a very long error message about various configuration options not working. What's up?

This is probably because of union types.
See [this section](usage/cl_tutorial.md#union-types) for more information, but the short version is that some options (e.g., the repository or problem statement) can be specified in multiple ways, so we try every option until we find the one that works based on your inputs.
If none of them work, we throw an error which then tells you why we cannot initialize any of the types, so this will get somewhat long and confusing.

> Why are my images not being processed?

Check that you're using a multimodal configuration (see `default_mm_with_images.yaml` as an example), have internet connectivity, and images are under 10MB. See [Multimodal usage notes](usage/multimodal.md) for more details.

## Models

> What models are supported? Do you support local models?

Probably all of them, including local models! There's even a few for testing. See [models](installation/keys.md) and [more on models](config/models.md).

> Does SWE-agent support multimodal models and images?

Yes! SWE-agent supports vision-capable models that can process images from GitHub issues. Use `--config config/default_mm_with_images.yaml` and specify a multimodal model like Claude Sonnet 4 or GPT-4o. See the [multimodal guide](usage/multimodal.md) for details.

> What can I do if my model doesn't support function calling?

You can configure how to parse the model's response by choosing your `agent.tools.parse_function`.
The default now is `function_calling`, but you can change it to `thought_action`.
More information in the [reference](reference/parsers.md).
There are also some config example in our [config folder](https://github.com/SWE-agent/SWE-agent/tree/main/config).

## Configuring SWE-agent

> How can I change the demonstrations given to SWE-agent?

At the start of each run, we feed the agent a demonstration trajectory, showing it how to solve an example issue.
This substantially improves the agent's abilities to solve novel issues.
If you'd like to modify or totally change this demonstration, to better fit your use case, see [this](config/demonstrations.md).

> Can I add custom tools?

Yes! Take a look at [this tutorial](usage/adding_custom_tools.md).

## MISC

> What's up with all the output files?

You're probably most interested in the `*.traj` files, which contain complete records of SWE-agent's thought process and actions. See [output files](usage/trajectories.md) for more information.

## Anything else?

> I have a question/bug report/feature request...

Please open a [github issue!](https://github.com/SWE-agent/SWE-agent/issues)!


{% include-markdown "_footer.md" %}