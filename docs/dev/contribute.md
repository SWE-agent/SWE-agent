# Contribute to SWE-agent

!!! tip "Formatting change"
    We've recently added automated formatting to our code base.
    If you are dealing with merge-conflicts when opening a PR or updating your fork,
    please first install `pre-commit` and run `pre-commit run --all-files` and try again.

{%
    include-markdown "../../CONTRIBUTING.md"
    start="<!-- INCLUSION START -->"
    end="<!-- INCLUSION END -->"
%}

Wanna do more and actually contribute code? Great! Please see the following sections for tips and guidelines!

## Development repository set-up

Please install the repository from source, following our [usual instructions](../installation/source.md) but add the `[dev]` option to the `pip` command (you can just run the command again):

```bash
pip install -e '.[dev]'
```

Then, make sure to set up [`pre-commit`](https://pre-commit.com):

```bash
# cd to our repo root
pre-commit install
```

`pre-commit` will check for formatting and basic syntax errors before your commits.

!!! tip "Autofixes"
    Most problems (including formatting) will be automatically fixed.
    Therefore, if `pre-commit`/`git commit` fails on its first run, simply try running it a second time.

    Some more autofixes can be enabled with the `--unsafe-fixes` option from [`ruff`](https://github.com/astral-sh/ruff):

    ```bash
    pipx run ruff check --fix --unsafe-fixes
    ```

## Running tests

We provide a lot of tests that can be very helpful for rapid development.
Run them with

```bash
pytest
```

Some of the tests might be slower than others. You can exclude them with

```bash
pytest -m "not slow"
```

You can run all tests in parallel with `pytest-xdist`:

```bash
pytest -n auto
```

If you are using VSCode, you might want to add the following two files:

<details>
<summary><code>.vscode/launch.json</code></summary>

```json
--8<-- "docs/dev/vscode_launch.json"
```
</details>

<details>
<summary><code>.vscode/settings.json</code></summary>

```json
--8<-- "docs/dev/vscode_settings.json"
```
</details>

## Debugging

We recommend to install `pdbpp` for some improved debugger features:

```bash
pip install pdbpp
```

Set breakpoints with `breakpoint()` and then run `sweagent` with `pdb`:

```bash
pdb -m sweagent <command> -- <more command line arguments> # (1)!
```

1. Note the `--` before the options passed to sweagent. This is to separate
  options passed to `pdb` from those that are passed to `sweagent`.


When working on a test that fails, you can use

```
pytest -k name_of_test -s --capture=no --log-cli-level=DEBUG
```

to see all debug output from the agent.

## Tips for pull requests

* If you see a lot of formatting-related merge conflicts, please see [here](formatting_conflicts.md).
* Please open separate PRs for separate issues. This makes it easier to incorporate part of your changes.
* It might be good to open an issue and discuss first before investing time on an experimental feature.
* Don't know where to get started? Look for issues marked [👋 good first issue][gfi] or [🙏 help wanted][help_wanted]
* When changing the behavior of the agent, we need to have some indication that it actually improves the success rate of SWE-agent.
  However, if you make the behavior optional without complicating SWE-agent (for example by providing new [commands](../config/tools.md)),
  we might be less strict.
* Please add simple unit tests or integration tests wherever possible. Take a look in the [tests directory](https://github.com/SWE-agent/SWE-agent/tree/main/tests)
  for inspiration. We emphasize simple easy-to-write tests that get a lot of coverage.

[gfi]: https://github.com/SWE-agent/SWE-agent/issues?q=is%3Aissue+is%3Aopen+sort%3Aupdated-desc+label%3A%22%F0%9F%91%8B+good+first+issue%22+
[help_wanted]: https://github.com/SWE-agent/SWE-agent/issues?q=is%3Aissue+is%3Aopen+sort%3Aupdated-desc+label%3A%22%F0%9F%99%8F+help+wanted%22

## Building the documentation <a name="mkdocs"></a>

Simply run

```bash
# cd repo root
mkdocs serve
```

and point your browser to port 8000 or click one of the links in the output.

## Diving into the code

<div class="grid cards" markdown>

-   :material-cog:{ .lg .middle } __Code structure and reference__

    ---

    Read the reference for more information on our code.

    [:octicons-arrow-right-24: Read more](../reference/index.md)

</div>

{% include-markdown "../_footer.md" %}
