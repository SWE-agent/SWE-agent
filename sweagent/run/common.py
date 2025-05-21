"""Common functionality for the run scripts."""

import json
import sys
from argparse import ArgumentParser
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from types import UnionType
from typing import Any

import yaml
from pydantic import ValidationError
from pydantic_settings import BaseSettings, CliApp, SettingsError
from rich import print as rich_print
from rich.panel import Panel

from sweagent import CONFIG_DIR
from sweagent.types import AgentInfo, AgentRunResult
from sweagent.utils.log import get_logger
from sweagent.utils.serialization import merge_nested_dicts


def _shorten_strings(data, *, max_length=30):
    """
    Recursively shortens all strings in a nested data structure to a maximum length.

    Args:
        data: The nested data structure (dicts, lists, and strings).
        max_length: The maximum length for strings.

    Returns:
        The modified data structure with shortened strings.
    """
    if isinstance(data, str):
        # Shorten the string if it exceeds the max length
        data = data.replace("\n", "\\n")
        return data[: max_length - 3] + "..."
    elif isinstance(data, list):
        # Recursively process each item in the list
        return [_shorten_strings(item, max_length=max_length) for item in data]
    elif isinstance(data, dict):
        # Recursively process each value in the dictionary
        return {key: _shorten_strings(value, max_length=max_length) for key, value in data.items()}
    else:
        # Return the data as is if it's neither a string, list, nor dict
        return data


_VALIDATION_ERROR_HELP_TEXT = """
The following errors are raised by Pydantic, trying to instantiate the configuration based on
the merged configuration dictionary [bold](see above)[/bold].

Every new indented block corresponds to a different error from Pydantic.
The first line of each block is the attribute that failed validation, the following lines are the error messages.

If you see many lines of errors, there are probably different ways to instantiate the same object (a union type).
For example, there are different deployments with different options each. Pydantic is then trying
one after the other and reporting the failures for each of them.
More on union types: [link=https://swe-agent.com/latest/usage/cl_tutorial/#union-types]https://swe-agent.com/latest/usage/cl_tutorial/#union-types[/link]
"""

_SETTING_ERROR_HINTS = """
[red][bold]Hints:[/bold][/red]
Run `sweagent <subcommand> --help` for usage examples.

[red][bold]Common mistakes:[/bold][/red]
- You used dashes instead of underscores (wrong: `--num-workers`, correct: `--num_workers`).
- You forgot about part of the hierarchy (wrong: `--model.name`, correct: `--agent.model.name`).
"""


class AutoCorrectSuggestion:
    def __init__(
        self, original: str, alternative: str = "", *, condition: Callable | None = None, help: str | None = None
    ):
        self.original = original
        self.alternative = alternative
        self.condition = condition
        self.help = help
        if self.help and self.alternative:
            msg = "Cannot set both help and alternative"
            raise ValueError(msg)

    def show(self, args: list[str]) -> bool:
        no_equal = []
        for arg in args:
            if "=" in arg:
                no_equal.extend(arg.split("="))
            else:
                no_equal.append(arg)
        if self.condition is not None:
            return self.condition(no_equal)
        return f"--{self.original}" in no_equal

    def format(self) -> str:
        if self.help:
            return self.help
        return f"You wrote [red]--{self.original}[/red]. Did you mean [green]--{self.alternative}[/green]?"


class ConfigHelper:
    """Produce easy-to-read help text from pydantic setting objects."""

    def _get_type_name(self, item: Any, full: bool = False):
        """Given a config type, return a string that is either the full name or just the class name."""
        full_name = str(item).removeprefix("<class '").removesuffix("'>")
        if full:
            return full_name
        return full_name.split(".")[-1]

    def _get_value_help_string(self, item: Any, description: str | None):
        """Given an item, document it"""
        if hasattr(item, "model_fields"):
            # It's a pydantic config class
            full_name = self._get_type_name(item, full=True)
            name = self._get_type_name(item)
            out = f"[green]{name}[/green]\n"
            if description:
                out += f"    {description}\n"
            out += f"    Run [green]--help_option {full_name}[/green] for more info"
            return out
        if isinstance(item, UnionType):
            name = self._get_type_name(item)
            out = ""
            if description:
                out += f"    {description}\n"
            out += "    This config item can be one of the following things (run [green]--help_option <name>[/green] for more info):\n"
            things = str(item).split("|")
            for thing in things:
                out += f"    [green]{thing.strip()}[/green]\n"
            return out.strip()
        return self._get_type_name(item)

    def get_help(self, config_type: type[BaseSettings]) -> str:
        lines = []
        for name, field_info in config_type.model_fields.items():
            line = f"[green][bold]{name}[/bold][/green]: "
            line += self._get_value_help_string(field_info.annotation, field_info.description)
            lines.append(line)
        return "\n\n".join(lines)


def _nested_dict():
    """Helper function to create nested dictionaries."""
    return defaultdict(_nested_dict)


def _parse_args_to_nested_dict(args):
    """Parse the command-line arguments into a nested dictionary."""
    result = _nested_dict()

    i = 0
    while i < len(args):
        arg = args[i]
        if not arg.startswith("--"):
            i += 1
            continue

        # Handle --key=value format
        if "=" in arg:
            key, value = arg[2:].split("=", 1)
        # Handle --key value format
        else:
            key = arg[2:]
            i += 1
            if i >= len(args):
                break
            value = args[i]

        # Convert value to int if possible
        value = int(value) if value.isdigit() else value

        # Build nested dict structure
        keys = key.split(".")
        current = result
        for k in keys[:-1]:
            current = current[k]
        current[keys[-1]] = value

        i += 1

    return result


# todo: Parameterize type hints
class BasicCLI:
    def __init__(self, config_type: type[BaseSettings], *, default_settings: bool = True, help_text: str | None = None):
        """This class implements a basic CLI for SWE-agent. It is based on pydantic-settings, i.e., takes
        a `BaseSettings` object. In principle you could just initialize these via `pydantic-settings`'s `CliApp.run`,
        however, we also want to add a `--config` option to load additional config files and some other things.
        We also try to improve a bit on the pydantic error messages in here.

        Args:
            config_type: The type of the configuration object to instantiate.
            default_settings: Whether to load the default settings.
            help_text: If given, this will override the default help text that would usually be shown
                by argparse.
        """
        self.arg_type = config_type
        self.default_settings = default_settings
        self.logger = get_logger("swea-cli", emoji="🔧")
        self.help_text = help_text

    def maybe_show_auto_correct(self, args: list[str]):
        auto_correct = []
        if hasattr(self.arg_type, "_get_auto_correct"):
            for ac in self.arg_type._get_auto_correct():  # type: ignore
                if ac.show(args):
                    auto_correct.append(ac)
        if auto_correct:
            rich_print(
                Panel.fit(
                    "[red][bold]Auto-correct suggestions[/bold][/red]\n\n"
                    + "\n".join(ac.format() for ac in auto_correct),
                )
            )

    def get_config(self, args: list[str] | None = None) -> BaseSettings:
        """Get the configuration object from defaults and command arguments."""

        # >>> Step 1: Use argparse to add a --config option to load whole config files

        # The defaults if no config file is provided
        # Otherwise, the configs from the respective classes will be used
        parser = ArgumentParser(description=__doc__, add_help=False)
        parser.add_argument(
            "--config",
            type=Path,
            action="append",
            default=[],
            help=(
                "Load additional config files. Use this option multiple times to load "
                "multiple files, e.g., --config config1.yaml --config config2.yaml"
            ),
        )
        parser.add_argument(
            "-h",
            "--help",
            help="Show help text and exit",
            action="store_true",
        )
        parser.add_argument(
            "--help_option",
            help="Show help text for a specific option",
        )
        if self.default_settings:
            parser.add_argument(
                "--no_config_file",
                action="store_true",
                help="Do not load default config file when no config file is provided",
            )
        parser.add_argument(
            "--print_config",
            action="store_true",
            help="Print the final config and exit",
        )

        # >>> Step 2: Parse argparse arguments but keep all the remaining arguments.
        # Explicitly handle --help and --print-options

        cli_args, remaining_args = parser.parse_known_args(args)

        if cli_args.help:
            if self.help_text:
                rich_print(self.help_text)
            else:
                parser.print_help()
            exit(0)
        if cli_args.help_option:
            module, _, name = cli_args.help_option.rpartition(".")
            if module not in sys.modules:
                __import__(module)
            type_ = getattr(sys.modules[module], name)
            rich_print(ConfigHelper().get_help(type_))
            exit(0)

        # >>> Step 3: Load config files and merge them in a big nested data structure

        config_merged = {}
        config_files = []
        if cli_args.config:
            config_files.extend(cli_args.config)
            for _f in cli_args.config:
                txt = Path(_f).read_text()
                if not txt.strip():
                    self.logger.warning(f"Config file {_f} is empty")
                    continue
                _loaded = yaml.safe_load(txt)
                merge_nested_dicts(config_merged, _loaded)
        elif self.default_settings and not cli_args.no_config_file:
            config_file = CONFIG_DIR / "default.yaml"
            config_files.append(config_file)
            msg = (
                f"Loading default config from {config_file}, because no other "
                "config file is specified. Specify --no_config_file to disable this."
            )
            self.logger.info(msg)
            txt = config_file.read_text()
            if not txt.strip():
                self.logger.warning(f"Default config file {config_file} is empty")
                config_merged = {}
            else:
                config_merged = yaml.safe_load(txt)
        else:
            config_merged = {}

        # For informational purposes, we also merge in the command line options
        cl_options_dict = _parse_args_to_nested_dict(remaining_args)

        # >>> Step 4: Bring together remaining arguments and the merged config to initialize the config object
        # This is done by CliApp.run from pydantic-settings

        try:
            config: BaseSettings = CliApp.run(self.arg_type, remaining_args, **config_merged, cli_exit_on_error=False)  # type: ignore
        except ValidationError as e:
            rich_print(
                Panel.fit(
                    "[red][bold]Configuration from config files\n[/bold]"
                    "This is all the configuration that was provided from defaults, --config, and CLI arguments[/red]\n\n"
                    + yaml.dump(_shorten_strings(config_merged))
                )
            )
            rich_print(
                Panel.fit(
                    "[red][bold]Configuration from CLI arguments\n[/bold]"
                    "This is all the configuration that was provided from the command line arguments[/red]\n\n"
                    + yaml.dump(_shorten_strings(cl_options_dict))
                )
            )
            rich_print(
                Panel.fit(
                    "[red][bold]Merged configuration\n[/bold]"
                    "This is the merged configuration that was used to instantiate the config object[/red]\n\n"
                    + yaml.dump(_shorten_strings(merge_nested_dicts(config_merged, cl_options_dict)))
                )
            )
            rich_print(
                Panel.fit(
                    "[red][bold]Validation error[/bold]\n" + _VALIDATION_ERROR_HELP_TEXT + "[/red]\n" + str(e),
                )
            )
            self.maybe_show_auto_correct(remaining_args)
            msg = "Invalid configuration. Please check the above output."
            raise RuntimeError(msg) from None
        except SettingsError as e:
            rich_print(Panel.fit("[red][bold]SettingsError[/bold][/red]\n\n" + str(e) + "\n\n" + _SETTING_ERROR_HINTS))
            self.maybe_show_auto_correct(remaining_args)
            msg = "Invalid command line arguments. Please check the above output in the box."
            raise RuntimeError(msg) from None

        if cli_args.print_config:  # type: ignore
            print(yaml.dump(config.model_dump()))
            exit(0)

        # Attach config files to the arg object, because we need them for file naming purposes
        # (the output traj directory is named after the last config file)
        config._config_files = config_files  # type: ignore
        return config


def save_predictions(traj_dir: Path, instance_id: str, result: AgentRunResult):
    """Save predictions in a file readable by SWE-bench"""
    output_file = traj_dir / instance_id / (instance_id + ".pred")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    datum = {
        "model_name_or_path": traj_dir.name,
        "instance_id": instance_id,
        "model_patch": result.info.get("submission"),
    }
    output_file.write_text(json.dumps(datum))


def _is_promising_patch(info: AgentInfo) -> bool:
    """Do we actually believe that the patch will solve the issue?
    Or are we just submitting the last patch we generated before hitting an error?
    """
    # The exit status can also be `submitted (exit_cost)` etc.
    return info.get("exit_status") == "submitted" and info.get("submission") is not None
