# Command line basics

!!! abstract "Command line basics"
    This tutorial walks you through running SWE-agent from the command line.

    * Please read our [hello world](hello_world.md) tutorial before proceeding.
    * This tutorial focuses on using SWE-agent as a tool to solve individual issues.
      Benchmarking SWE-agent is covered [separately](batch_mode.md).
      Finally, we have a different tutorial for using SWE-agent for [coding challenges](coding_challenges.md).

## A few examples

Before we start with a more structured explanation of the command line options, here are a few examples that you might find immediately useful:

```bash title="Fix a github issue"
python run.py \
  --agent.model.name=gpt4 \
  --agent.model.per_instance_cost_limit=2.00 \
  --env.repo.github_url=https://github.com/SWE-agent/test-repo \
  --problem_statement.github_url=https://github.com/SWE-agent/test-repo/issues/1
```

```bash title="Work on a github repo with a custom problem statement" hl_lines="4"
python run.py \
  ...
  --env.repo.github_url=https://github.com/SWE-agent/test-repo \
  --problem_statement.text="Hey, can you fix all the bugs?"
```

```bash title="Fix a bug in a local repository using a custom docker image" hl_lines="4 5 6"
git clone https://github.com/SWE-agent/test-repo.git
python run.py \
  --agent.model.name=claude-sonnet-4-20250514\
  --env.repo.path=test-repo \
  --problem_statement.path=test-repo/problem_statements/1.md \
  --env.deployment.image=python:3.12
```

1. Make sure to add anthropic keys (or keys for your model provider) to the environment for this one!
2. `--env.deployment.image` points to the [dockerhub image](https://hub.docker.com/_/python) of the same name


For the next example, we will use a cloud-based execution environment instead of using local docker containers.
For this, you first need to set up a modal account, install the necessary extra dependencies `pip install 'swe-rex[modal]'`, then run:

```bash title="Deployment on modal (cloud-based execution)" hl_lines="3"
python run.py \
  ...
  --env.deployment.type=modal \
  --env.deployment.image=python:3.12
```

!!! tip "All options"
    Run `python run.py --help` to see all available options for `run.py`. This tutorial will only cover a subset of options.

## Configuration files

All configuration options can be specified either in one or more `.yaml` files, or as command line arguments. For example, our first command can be written as

=== "Command line"

    ```bash
    python run.py --config my_run.yaml
    ```

=== "Configuration file"

    ```yaml title="my_run.yaml"
    agent:
      model:
        name: gpt4
        per_instance_cost_limit: 2.00
    env:
      repo:
        github_url: https://github.com/SWE-agent/test-repo
    problem_statement:
      github_url: https://github.com/SWE-agent/test-repo/issues/1
    ```

But we can also split it up into multiple files and additional command line options:

=== "Command line"

    ```bash
    # Note that you need --config in front of every config file
    python run.py --config agent.yaml --config env.yaml \
        --problem_statement.text="Hey, can you fix all the bugs?"
    ```

=== "`agent.yaml`"

    ```yaml title="agent.yaml"
    agent:
      model:
        name: gpt4
        per_instance_cost_limit: 2.00
    ```

=== "`env.yaml`"

    ```yaml title="env.yaml"
    env:
      repo:
        github_url: https://github.com/SWE-agent/test-repo
    ```

!!! warning "Multiple config files"
    Prior to version SWE-agent 1.1.0, configs were merged with simple dictionary updates,
    rather than a hierarchical merge, so specifying `agent` (or any key with subkeys) in the
    second config would completely overwrite all `agent` settings of the first config.
    This is fixed since SWE-agent 1.1.0.

The default config file is `config/default.yaml`. Let's take a look at it:

<details>
<summary>Example: default config <code>default.yaml</code></summary>

```yaml
--8<-- "config/default.yaml"
```
</details>

As you can see, this is where all the templates are defined!

This file is also loaded when no other `--config` options are specified.
So to make sure that we get the default templates in the above examples with `--config`, we should have added

```bash
--config config/default.yaml
```

in addition to all the other `--config` options for the two examples above.

## Problem statements and union types <a id="union-types"></a>

!!! note "Operating in batch mode: Running on SWE-bench and other benchmark sets"
    If you want to run SWE-agent in batch mode on SWE-bench or another whole evaluation set, see
    [batch mode](batch_mode.md). This tutorial focuses on using SWE-agent on
    individual issues.

We've already seen a few examples of how to specify the problem to solve, namely

```bash
--problem_statement.data_path /path/to/problem.md
--problem_statement.repo_path /path/to/repo
--problem_statement.text="..."
```

Each of these types of problems can have specific configuration options.

To understand how this works, we'll need to understand **union types**.
Running `sweagent run` builds up a configuration object that essentially looks like this:

```yaml
agent: AgentConfig
env: EnvironmentConfig
problem_statement: TextProblemStatement | GithubIssue | FileProblemStatement  # (1)!
```

1. This is a union type, meaning that the problem statement can be one of the three types.

Each of these configuration objects has its own set of options:

* [`GithubIssue`](../reference/problem_statements.md#sweagent.agent.problem_statement.GithubIssue)
* [`TextProblemStatement`](../reference/problem_statements.md#sweagent.agent.problem_statement.TextProblemStatement)
* [`FileProblemStatement`](../reference/problem_statements.md#sweagent.agent.problem_statement.FileProblemStatement)

So how do we know which configuration object to initialize?
It's simple: Each of these types has a different set of required options (e.g., `github_url` is required for `GithubIssue`, but not for `TextProblemStatement`).
SWE-agent will automatically select the correct configuration object based on the command line options you provide.

However, you can also explicitly specify the type of problem statement you want to use by adding a `--problem_statement.type` option.

!!! tip "Union type errors"
    If you ever ran a SWE-agent command and got a very long error message about various configuration options not working, it is because for union types.
    If everything works correctly, we try to initialize every option until we find the one that works based on your inputs (for example stopping at `TextProblemStatement` if you provided a `--problem_statement.text`).
    However, if none of them work, we throw an error which then tells you why we cannot initialize any of the types (so it will tell you that `github_url` is required for `GithubIssue`, even though you might not even have tried to work on a GitHub issue).

      <details>Example union type errors
      <summary>Example union type errors</summary>

      This is the output of running

      ```bash
      sweagent run --problem_statement.path="test" --problem_statement.github_url="asdf"
      ```

      ```
      --8<-- "docs/usage/union_type_error.txt"
      ```
      </details>

If you want to read more about how this works, check out the [pydantic docs](https://docs.pydantic.dev/latest/concepts/unions/).

## Specifying the repository

The repository can be specified in a few different ways:

```bash
--env.repo.github_url=https://github.com/SWE-agent/test-repo
--env.repo.path=/path/to/repo
```

Again, those are [union types](#union-types). See here for all the options:

* [`GithubRepoConfig`](../reference/repo.md#sweagent.environment.repo.GithubRepoConfig): Pull a repository from GitHub.
* [`LocalRepoConfig`](../reference/repo.md#sweagent.environment.repo.LocalRepoConfig): Copies a repository from your local filesystem to the docker container.
* [`PreExistingRepoConfig`](../reference/repo.md#sweagent.environment.repo.PreExistingRepoConfig): If you want to use a repository that already exists on the docker container.

## Configuring the environment

We mainly recommend you to build a docker image with all the dependencies you need and then use that with `--env.deployment.image`.
In addition, you can also execute additional commands before starting the agent with `env.post_startup_commands`, which takes a list of commands, e.g.,

```bash
sweagent run \
    --agent.model.name=claude-3-7-sonnet-latest \
    --env.post_startup_commands='["pip install flake8"]' \
    ...
```

Note the list syntax that is passed as a string using single ticks `'`. This is particularly important for `zsh` where `[`, `]` have special meaning.

Here's an example of a custom docker environment (it's also available in the repo as `docker/tiny_test.Dockerfile`):

<!-- There's a dockerfile annotation, but it somehow breaks annotations -->
```bash title="tiny_test.Dockerfile"
FROM python:3.11.10-bullseye  # (1)!

ARG DEBIAN_FRONTEND=noninteractive  # (2)!
ENV TZ=Etc/UTC  # (3)!

WORKDIR /

# SWE-ReX will always attempt to install its server into your docker container
# however, this takes a couple of seconds. If we already provide it in the image,
# this is much faster.
RUN pip install pipx
RUN pipx install swe-rex  # (4)!
RUN pipx ensurepath  # (5)!

RUN pip install flake8  # (6)!

SHELL ["/bin/bash", "-c"]
# This is where pipx installs things
ENV PATH="$PATH:/root/.local/bin/"  # (7)!
```

Click on the :material-chevron-right-circle: icon in the right margin of the code snippet to see more information about the lines.

1. This is the base image.
2. This is to avoid any interactive prompts from the package manager.
3. Again, this avoids interactive prompts
4. SWE-ReX is our execution backend. We start a small server within the container, which receives
   commands from the agent and executes them.
5. This ensures that the path where pipx installs things is in the `$PATH` variable.
6. This is to install flake8, which is used by some of our edit tools.
7. Unfortunately, step 5 sometimes still doesn't properly add the SWE-ReX server to the `$PATH` variable.
   So we do it here again.


## Taking actions

* You can use `--actions.apply_patch_locally` to have SWE-agent apply successful solution attempts to local files.
* Alternatively, when running on a GitHub issue, you can have the agent automatically open a PR if the issue has been solved by supplying the `--actions.open_pr` flag.
  Please use this feature responsibly (on your own repositories or after careful consideration).

!!! tip "All action options"
    See [`RunSingleActionConfig`](../reference/run_single_config.md#sweagent.run.run_single.RunSingleActionConfig) for all action options.

Alternatively, you can always retrieve the patch that was generated by SWE-agent.
Watch out for the following message in the log:


```
╭──────────────────────────── 🎉 Submission successful 🎉 ────────────────────────────╮
│ SWE-agent has produced a patch that it believes will solve the issue you submitted! │
│ Use the code snippet below to inspect or apply it!                                  │
╰─────────────────────────────────────────────────────────────────────────────────────╯
```

And follow the instructions below it:

```bash
 # The patch has been saved to your local filesystem at:
 PATCH_FILE_PATH='/Users/.../patches/05917d.patch'
 # Inspect it:
 cat "${PATCH_FILE_PATH}"
 # Apply it to a local repository:
 cd <your local repo root>
 git apply "${PATCH_FILE_PATH}"
```

{% include-markdown "../_footer.md" %}
