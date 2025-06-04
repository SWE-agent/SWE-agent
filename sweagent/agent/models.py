from __future__ import annotations

import copy
import json
import os
import random
import shlex
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from threading import Lock
from typing import Annotated, Any, Literal

import litellm
import litellm.types.utils
from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field, SecretStr
from swerex.exceptions import SwerexException
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from sweagent import REPO_ROOT
from sweagent.exceptions import (
    ContentPolicyViolationError,
    ContextWindowExceededError,
    CostLimitExceededError,
    FunctionCallingFormatError,
    InstanceCallLimitExceededError,
    InstanceCostLimitExceededError,
    ModelConfigurationError,
    TotalCostLimitExceededError,
)
from sweagent.tools.tools import ToolConfig
from sweagent.types import History, HistoryItem
from sweagent.utils.log import get_logger

try:
    import readline  # noqa: F401
except ImportError:
    readline = None

litellm.suppress_debug_info = True


_THREADS_THAT_USED_API_KEYS = []
"""Keeps track of thread orders so that we can choose the same API key for the same thread."""


class RetryConfig(PydanticBaseModel):
    """This configuration object specifies how many times to retry a failed LM API call."""

    retries: int = 20
    """Number of retries"""
    min_wait: float = 10
    """Minimum wait time between retries (random exponential wait)"""
    max_wait: float = 120
    """Maximum wait time between retries (random exponential wait)"""


class GenericAPIModelConfig(PydanticBaseModel):
    """This configuration object specifies a LM like GPT4 or similar.
    The model will be served with the help of the `litellm` library.
    """

    name: str = Field(description="Name of the model.")

    per_instance_cost_limit: float = Field(
        default=3.0,
        description="Cost limit for every instance (task).",
    )
    total_cost_limit: float = Field(default=0.0, description="Total cost limit.")
    per_instance_call_limit: int = Field(default=0, description="Per instance call limit.")
    temperature: float = 0.0
    """Sampling temperature"""
    top_p: float | None = 1.0
    """Sampling top-p"""
    api_base: str | None = None
    api_version: str | None = None
    api_key: SecretStr | None = None
    """API key to the model. We recommend using environment variables to set this instead
    or putting your environment variables in a `.env` file.
    You can concatenate more than one key by separating them with `:::`, e.g.,
    `key1:::key2`.
    If field starts with `$`, it will be interpreted as an environment variable.
    """
    stop: list[str] = []
    """Custom stop sequences"""

    completion_kwargs: dict[str, Any] = {}
    """Additional kwargs to pass to `litellm.completion`"""

    convert_system_to_user: bool = False
    """Whether to convert system messages to user messages. This is useful for
    models that do not support system messages like o1.
    """

    retry: RetryConfig = RetryConfig()
    """Retry configuration: How often to retry after a failure (e.g., from a rate limit)
    etc.
    """

    delay: float = 0.0
    """Minimum delay before querying (this can help to avoid overusing the API if sharing
    it with other people).
    """

    fallbacks: list[dict[str, Any]] = []
    """List of fallbacks to try if the main model fails
    See https://docs.litellm.ai/docs/completion/reliable_completions#fallbacks-sdk
    for more information.
    """

    choose_api_key_by_thread: bool = True
    """Whether to choose the API key based on the thread name (if multiple are configured).
    This ensures that with
    run-batch, we use the same API key within a single-thread so that prompt caching still works.
    """

    max_input_tokens: int | None = None
    """If set, this will override the max input tokens for the model that we usually look
    up from `litellm.model_cost`.
    Use this for local models or if you want to set a custom max input token limit.
    If this value is exceeded, a `ContextWindowExceededError` will be raised.
    Set this to 0 to disable this check.
    """

    max_output_tokens: int | None = None
    """If set, this will override the max output tokens for the model that we usually look
    up from `litellm.model_cost`.
    Use this for local models or if you want to set a custom max output token limit.
    If this value is exceeded, a `ContextWindowExceededError` will be raised.
    Set this to 0 to disable this check.
    """

    # pydantic
    model_config = ConfigDict(extra="forbid")

    def get_api_keys(self) -> list[str]:
        """Returns a list of API keys that were explicitly set in this config.
        Does not return API keys that were set via environment variables/.env
        """
        if self.api_key is None:
            return []
        api_key = self.api_key.get_secret_value()
        if not api_key:
            return []
        if api_key.startswith("$"):
            env_var_name = api_key[1:]
            api_key = os.getenv(env_var_name, "")
            if not api_key:
                get_logger("swea-config", emoji="🔧").warning(f"Environment variable {env_var_name} not set")
                return []
        return api_key.split(":::")

    def choose_api_key(self) -> str | None:
        """Chooses an API key based on the API keys explicitly set in this config.
        If no API keys are set, returns None (which means that the API key will be
        taken from the environment variables/.env file).
        """
        api_keys = self.get_api_keys()
        if not api_keys:
            return None
        if not self.choose_api_key_by_thread:
            return random.choice(api_keys)
        thread_name = threading.current_thread().name
        if thread_name not in _THREADS_THAT_USED_API_KEYS:
            _THREADS_THAT_USED_API_KEYS.append(thread_name)
        thread_idx = _THREADS_THAT_USED_API_KEYS.index(thread_name)
        key_idx = thread_idx % len(api_keys)
        get_logger("config", emoji="🔧").debug(
            f"Choosing API key {key_idx} for thread {thread_name} (idx {thread_idx})"
        )
        return api_keys[key_idx]

    @property
    def id(self) -> str:
        return f"{self.name}__t-{self.temperature:.2f}__p-{self.top_p:.2f}__c-{self.per_instance_cost_limit:.2f}"


class ReplayModelConfig(GenericAPIModelConfig):
    replay_path: Path = Field(description="Path to replay file when using the replay model.")

    per_instance_cost_limit: float = Field(
        default=0.0, description="Cost limit for every instance (task). This is a dummy value here."
    )
    total_cost_limit: float = Field(
        default=0.0, description="Cost limit for all instances (tasks). This is a dummy value here."
    )

    name: Literal["replay"] = Field(default="replay", description="Model name.")

    model_config = ConfigDict(extra="forbid")


class InstantEmptySubmitModelConfig(GenericAPIModelConfig):
    """Model that immediately submits an empty patch"""

    name: Literal["instant_empty_submit"] = Field(default="instant_empty_submit", description="Model name.")

    per_instance_cost_limit: float = Field(
        default=0.0, description="Cost limit for every instance (task). This is a dummy value here."
    )
    total_cost_limit: float = Field(
        default=0.0, description="Cost limit for all instances (tasks). This is a dummy value here."
    )
    delay: float = 0.0
    """Delay before answering"""

    model_config = ConfigDict(extra="forbid")


class HumanModelConfig(GenericAPIModelConfig):
    name: Literal["human"] = Field(default="human", description="Model name.")

    per_instance_cost_limit: float = Field(
        default=0.0, description="Cost limit for every instance (task). This is a dummy value here."
    )
    total_cost_limit: float = Field(default=0.0, description="Cost limit for all instances (tasks).")
    cost_per_call: float = 0.0
    catch_eof: bool = True
    """Whether to catch EOF and return 'exit' when ^D is pressed. Set to False when used in human_step_in mode."""
    model_config = ConfigDict(extra="forbid")


class HumanThoughtModelConfig(HumanModelConfig):
    name: Literal["human_thought"] = Field(default="human_thought", description="Model name.")

    per_instance_cost_limit: float = Field(
        default=0.0, description="Cost limit for every instance (task). This is a dummy value here."
    )
    total_cost_limit: float = Field(
        default=0.0, description="Cost limit for all instances (tasks). This is a dummy value here."
    )
    cost_per_call: float = 0.0

    model_config = ConfigDict(extra="forbid")


ModelConfig = Annotated[
    GenericAPIModelConfig
    | ReplayModelConfig
    | InstantEmptySubmitModelConfig
    | HumanModelConfig
    | HumanThoughtModelConfig,
    Field(union_mode="left_to_right"),
]


class GlobalStats(PydanticBaseModel):
    """This class tracks usage numbers (costs etc.) across all instances."""

    total_cost: float = 0
    """Cumulative cost for all instances so far"""

    last_query_timestamp: float = 0
    """Timestamp of the last query. Currently only used with API models."""


GLOBAL_STATS = GlobalStats()
"""This object tracks usage numbers (costs etc.) across all instances.
Please use the `GLOBAL_STATS_LOCK` lock when accessing this object to avoid race conditions.
"""

GLOBAL_STATS_LOCK = Lock()
"""Lock for accessing `GLOBAL_STATS` without race conditions"""


class InstanceStats(PydanticBaseModel):
    """This object tracks usage numbers (costs etc.) for a single instance."""

    instance_cost: float = 0
    tokens_sent: int = 0
    tokens_received: int = 0
    api_calls: int = 0

    def __add__(self, other: InstanceStats) -> InstanceStats:
        return InstanceStats(
            **{field: getattr(self, field) + getattr(other, field) for field in self.model_fields.keys()},
        )

    def __sub__(self, other: InstanceStats) -> InstanceStats:
        return InstanceStats(
            **{field: getattr(self, field) - getattr(other, field) for field in self.model_fields.keys()},
        )


class AbstractModel(ABC):
    def __init__(self, config: ModelConfig, tools: ToolConfig):
        self.config: ModelConfig
        self.stats: InstanceStats

    def reset_stats(self):
        self.stats = InstanceStats()

    @abstractmethod
    def query(self, history: History, action_prompt: str = "> ") -> dict: ...

    @property
    def instance_cost_limit(self) -> float:
        """Cost limit for the model. Returns 0 if there is no limit."""
        return 0


def _handle_raise_commands(action: str) -> None:
    if action == "raise_runtime":
        raise SwerexException()
    elif action == "raise_cost":
        raise CostLimitExceededError()
    elif action == "raise_context":
        raise ContextWindowExceededError()
    elif action.startswith("raise_function_calling"):
        parts = shlex.split(action)
        error_code = parts[1]
        if len(parts) == 3:
            error_message = parts[2]
        assert len(parts) < 4
        raise FunctionCallingFormatError(error_message, error_code)  # type: ignore


class HumanModel(AbstractModel):
    def __init__(self, config: HumanModelConfig, tools: ToolConfig):
        """Model that allows for human-in-the-loop"""
        self.logger = get_logger("swea-lm", emoji="🤖")
        self.config: HumanModelConfig = config
        self.stats = InstanceStats()

        # Determine which commands require multi-line input
        self.multi_line_command_endings = {
            command.name: command.end_name for command in tools.commands if command.end_name is not None
        }
        self._readline_histfile = REPO_ROOT / ".swe-agent-human-history"
        self._load_readline_history()

    def _load_readline_history(self) -> None:
        """Load autocomplete history from file"""
        if readline is None:
            return
        if self._readline_histfile.is_file():
            self.logger.debug(f"Loading readline history from {self._readline_histfile}")
            readline.read_history_file(self._readline_histfile)

    def _save_readline_history(self) -> None:
        """Save autocomplete history to file"""
        if readline is None:
            return
        readline.write_history_file(self._readline_histfile)

    def _update_stats(
        self,
    ) -> None:
        self.stats.instance_cost += self.config.cost_per_call
        self.stats.api_calls += 1
        if 0 < self.config.per_instance_cost_limit < self.stats.instance_cost:
            msg = f"Instance cost limit exceeded: {self.stats.instance_cost} > {self.config.per_instance_cost_limit}"
            raise InstanceCostLimitExceededError(msg)
        if 0 < self.config.total_cost_limit < self.stats.instance_cost:
            msg = f"Total cost limit exceeded: {self.stats.instance_cost} > {self.config.total_cost_limit}"
            raise TotalCostLimitExceededError(msg)

    def _query(
        self,
        history: History,
        action_prompt: str = "> ",
    ) -> dict:
        """Logic for handling user input to pass to SWEEnv"""
        action = input(action_prompt)
        self._save_readline_history()
        command_name = action.split()[0] if action.strip() else ""

        # Special handling for multi-line input actions (i.e. edit)
        if command_name in self.multi_line_command_endings:
            buffer = [action]
            end_keyword = self.multi_line_command_endings[command_name]
            while True:
                action = input("... ")
                buffer.append(action)
                if action.rstrip() == end_keyword:
                    # Continue reading input until terminating keyword inputted
                    break
            action = "\n".join(buffer)
        elif action.strip() == "start_multiline_command":  # do arbitrary multi-line input
            buffer = []
            while True:
                action = input("... ")
                if action.rstrip() == "end_multiline_command":
                    break
                buffer.append(action)
            action = "\n".join(buffer)
        else:
            # Input has escaped things like \n, so we need to unescape it
            action = action.encode("utf8").decode("unicode_escape")
        if action.strip() and action.strip().split()[0] == "spend_money":
            money = float(action.strip().split()[1])
            self.stats.instance_cost += money
            action = f"echo 'Spent {money} dollars'"
        _handle_raise_commands(action)
        self._update_stats()
        return {"message": action}

    def query(self, history: History, action_prompt: str = "> ", n: int | None = None, **kwargs) -> dict | list[dict]:
        """Wrapper to separate action prompt from formatting"""
        out = []
        n_samples = n or 1
        for _ in range(n_samples):
            try:
                out.append(self._query(history, action_prompt))
            except KeyboardInterrupt:
                print("^C (exit with ^D)")
                out.append(self.query(history, action_prompt))
            except EOFError:
                if self.config.catch_eof:
                    print("\nGoodbye!")
                    out.append({"message": "exit"})
                else:
                    # Re-raise EOFError when catch_eof is disabled
                    raise
        if n is None:
            return out[0]
        return out


class HumanThoughtModel(HumanModel):
    def query(self, history: History, **kwargs) -> dict:
        """Logic for handling user input (both thought + action) to pass to SWEEnv"""
        thought_all = ""
        thought = input("Thought (end w/ END_THOUGHT): ")
        while True:
            if "END_THOUGHT" in thought:
                thought = thought.split("END_THOUGHT")[0]
                thought_all += thought
                break
            thought_all += thought
            thought = input("... ")

        action = super()._query(history, action_prompt="Action: ")

        return {"message": f"{thought_all}\n```\n{action}\n```"}


class ReplayModel(AbstractModel):
    def __init__(self, config: ReplayModelConfig, tools: ToolConfig):
        """Model used for replaying a trajectory (i.e., taking all the actions for the `.traj` file
        and re-issuing them.
        """
        self.config = config
        self.stats = InstanceStats()

        if not self.config.replay_path.exists():
            msg = f"Replay file {self.config.replay_path} not found"
            raise FileNotFoundError(msg)

        self._replays = [
            list(json.loads(x).values())[0] for x in Path(self.config.replay_path).read_text().splitlines(keepends=True)
        ]
        self._replay_idx = 0
        self._action_idx = 0
        self.use_function_calling = tools.use_function_calling
        self.submit_command = tools.submit_command
        self.logger = get_logger("swea-lm", emoji="🤖")

    def _next_replay(self) -> None:
        """Called after last action"""
        self._replay_idx += 1
        self._action_idx = 0

    def query(self, history: History) -> dict:
        """Logic for tracking which replay action to pass to SWEEnv"""
        self.stats.api_calls += 1
        actions = self._replays[self._replay_idx]
        try:
            action = actions[self._action_idx]
        except IndexError:
            # log error
            self.logger.error("Reached end of replay trajectory without submitting. Submitting now.")
            if self.use_function_calling:
                action = {
                    "message": f"Calling `{self.submit_command}` to submit.",
                    "tool_calls": [
                        {
                            "type": "function",
                            "id": "call_submit",
                            "function": {
                                "name": self.submit_command,
                                "arguments": "{}",
                            },
                        }
                    ],
                }
            else:
                action = f"```\n{self.submit_command}\n```"

        self._action_idx += 1

        # Assuming `submit` is always last action of replay trajectory
        if isinstance(action, str) and action == "submit":
            self._next_replay()
            return {"message": action}

        # Handle both dict and string actions
        if isinstance(action, dict):
            return action
        return {"message": action}


class PredeterminedTestModel(AbstractModel):
    def __init__(self, outputs: list[dict | str]):
        """Model that outputs a predetermined sequence of messages. Useful for testing."""
        self._outputs = outputs
        self._idx = -1
        self.stats = InstanceStats()

    def query(self, *args, **kwargs) -> dict:
        self._idx += 1
        output = self._outputs[self._idx]
        if isinstance(output, str):
            _handle_raise_commands(output)
            return {"message": output}
        if not isinstance(output, dict):
            msg = f"Output must be string or dict, got {type(output)}"
            raise ValueError(msg)
        result = {"message": output["message"]}
        if "tool_calls" in output:
            result["tool_calls"] = output["tool_calls"]
        return result


class InstantEmptySubmitTestModel(AbstractModel):
    def __init__(self, args: InstantEmptySubmitModelConfig, tools: ToolConfig):
        """This model immediately submits. Useful for testing purposes"""
        super().__init__(args, tools)
        self.config: InstantEmptySubmitModelConfig = args
        self.stats = InstanceStats()
        self._action_idx = 0

    def query(self, history: list[dict[str, str]]) -> dict:
        time.sleep(random.uniform(0, self.config.delay))
        # Need to at least do _something_ to submit
        if self._action_idx == 0:
            self._action_idx = 1
            action = (
                "DISCUSSION\n"
                "Let's reproduce the bug by creating a `reproduce.py` file.\n\n"
                "```\n"
                "touch reproduce.py\n"
                "```\n"
            )
        elif self._action_idx == 1:
            self._action_idx = 0
            action = "DISCUSSION\nThe task should be resolved, so let's submit the patch.\n\n```\nsubmit\n```\n"
        self.stats.api_calls += 1
        return {"message": action}


class LiteLLMModel(AbstractModel):
    def __init__(self, args: GenericAPIModelConfig, tools: ToolConfig):
        """Model served by the `litellm` library."""
        # Always copy config to avoid shared state between different instances
        self.config: GenericAPIModelConfig = args.model_copy(deep=True)
        self.stats = InstanceStats()
        self.tools = tools
        self.logger = get_logger("swea-lm", emoji="🤖")

        if tools.use_function_calling:
            if not litellm.utils.supports_function_calling(model=self.config.name):
                msg = (
                    f"Model {self.config.name} does not support function calling. If your model"
                    " does not support function calling, you can use `parse_function='thought_action'` instead. "
                    "See https://swe-agent.com/latest/faq/ for more information."
                )
                self.logger.warning(msg)

        if self.config.max_input_tokens is not None:
            self.model_max_input_tokens = self.config.max_input_tokens
        else:
            self.model_max_input_tokens = litellm.model_cost.get(self.config.name, {}).get("max_input_tokens")

        if self.config.max_output_tokens is not None:
            self.model_max_output_tokens = self.config.max_output_tokens
        else:
            self.model_max_output_tokens = litellm.model_cost.get(self.config.name, {}).get("max_output_tokens")
            # Special handling for Claude 3.7 models to set 64k context by default when beta header not present
            # See https://github.com/SWE-agent/SWE-agent/pull/1016
            is_claude_3_7 = "claude-3-7-sonnet" in self.config.name or "claude-sonnet-4" in self.config.name
            has_128k_beta_header = (
                self.config.completion_kwargs.get("extra_headers", {}).get("anthropic-beta") == "output-128k-2025-02-19"
            )
            if is_claude_3_7 and not has_128k_beta_header:
                self.model_max_output_tokens = 64000
                self.logger.warning(
                    "Claude 3.7/4 models do not support 128k context by default. "
                    "Setting max output tokens to 64k. To enable 128k context, please set the "
                    "completion_kwargs to {'extra_headers': {'anthropic-beta': 'output-128k-2025-02-19'}}."
                )

        self.lm_provider = litellm.model_cost.get(self.config.name, {}).get("litellm_provider")

    @property
    def instance_cost_limit(self) -> float:
        """Cost limit for the model. Returns 0 if there is no limit."""
        return self.config.per_instance_cost_limit

    def _update_stats(self, *, input_tokens: int, output_tokens: int, cost: float) -> None:
        with GLOBAL_STATS_LOCK:
            GLOBAL_STATS.total_cost += cost
        self.stats.instance_cost += cost
        self.stats.tokens_sent += input_tokens
        self.stats.tokens_received += output_tokens
        self.stats.api_calls += 1

        # Log updated cost values to std. err
        self.logger.debug(
            f"input_tokens={input_tokens:,}, "
            f"output_tokens={output_tokens:,}, "
            f"instance_cost={self.stats.instance_cost:.2f}, "
            f"cost={cost:.2f}",
        )
        self.logger.debug(
            f"total_tokens_sent={self.stats.tokens_sent:,}, "
            f"total_tokens_received={self.stats.tokens_received:,}, "
            f"total_cost={GLOBAL_STATS.total_cost:.2f}, "
            f"total_api_calls={self.stats.api_calls:,}",
        )

        # Check whether total cost or instance cost limits have been exceeded
        if 0 < self.config.total_cost_limit < GLOBAL_STATS.total_cost:
            self.logger.warning(f"Cost {GLOBAL_STATS.total_cost:.2f} exceeds limit {self.config.total_cost_limit:.2f}")
            msg = "Total cost limit exceeded"
            raise TotalCostLimitExceededError(msg)

        if 0 < self.config.per_instance_cost_limit < self.stats.instance_cost:
            self.logger.warning(
                f"Cost {self.stats.instance_cost:.2f} exceeds limit {self.config.per_instance_cost_limit:.2f}"
            )
            msg = "Instance cost limit exceeded"
            raise InstanceCostLimitExceededError(msg)

        if 0 < self.config.per_instance_call_limit < self.stats.api_calls:
            self.logger.warning(f"API calls {self.stats.api_calls} exceeds limit {self.config.per_instance_call_limit}")
            msg = "Per instance call limit exceeded"
            raise InstanceCallLimitExceededError(msg)

    def _sleep(self) -> None:
        elapsed_time = time.time() - GLOBAL_STATS.last_query_timestamp
        if elapsed_time < self.config.delay:
            time.sleep(self.config.delay - elapsed_time)
        with GLOBAL_STATS_LOCK:
            GLOBAL_STATS.last_query_timestamp = time.time()

    def _single_query(
        self, messages: list[dict[str, str]], n: int | None = None, temperature: float | None = None
    ) -> list[dict]:
        self._sleep()
        # Workaround for litellm bug https://github.com/SWE-agent/SWE-agent/issues/1109
        messages_no_cache_control = copy.deepcopy(messages)
        for message in messages_no_cache_control:
            if "cache_control" in message:
                del message["cache_control"]
        input_tokens: int = litellm.utils.token_counter(messages=messages_no_cache_control, model=self.config.name)
        if self.model_max_input_tokens is None:
            msg = (
                f"No max input tokens found for model {self.config.name!r}. "
                "If you are using a local model, you can set `max_input_token` in the model config to override this."
            )
            self.logger.warning(msg)
        elif input_tokens > self.model_max_input_tokens > 0:
            msg = f"Input tokens {input_tokens} exceed max tokens {self.model_max_input_tokens}"
            raise ContextWindowExceededError(msg)
        extra_args = {}
        if self.config.api_base:
            # Not assigned a default value in litellm, so only pass this if it's set
            extra_args["api_base"] = self.config.api_base
        if self.tools.use_function_calling:
            extra_args["tools"] = self.tools.tools
        # We need to always set max_tokens for anthropic models
        completion_kwargs = self.config.completion_kwargs
        if self.lm_provider == "anthropic":
            completion_kwargs["max_tokens"] = self.model_max_output_tokens
        try:
            response: litellm.types.utils.ModelResponse = litellm.completion(  # type: ignore
                model=self.config.name,
                messages=messages,
                temperature=self.config.temperature if temperature is None else temperature,
                top_p=self.config.top_p,
                api_version=self.config.api_version,
                api_key=self.config.choose_api_key(),
                fallbacks=self.config.fallbacks,
                **completion_kwargs,
                **extra_args,
                n=n,
            )
        except litellm.exceptions.ContextWindowExceededError as e:
            raise ContextWindowExceededError from e
        except litellm.exceptions.ContentPolicyViolationError as e:
            raise ContentPolicyViolationError from e
        except litellm.exceptions.BadRequestError as e:
            if "is longer than the model's context length" in str(e):
                raise ContextWindowExceededError from e
            raise
        self.logger.debug(f"Response: {response}")
        try:
            cost = litellm.cost_calculator.completion_cost(response)
        except Exception as e:
            self.logger.debug(f"Error calculating cost: {e}, setting cost to 0.")
            if self.config.per_instance_cost_limit > 0 or self.config.total_cost_limit > 0:
                msg = (
                    f"Error calculating cost: {e} for your model {self.config.name}. If this is ok "
                    "(local models, etc.), please make sure you set `per_instance_cost_limit` and "
                    "`total_cost_limit` to 0 to disable this safety check."
                )
                self.logger.error(msg)
                raise ModelConfigurationError(msg)
            cost = 0
        choices: litellm.types.utils.Choices = response.choices  # type: ignore
        n_choices = n if n is not None else 1
        outputs = []
        output_tokens = 0
        for i in range(n_choices):
            output = choices[i].message.content or ""
            output_tokens += litellm.utils.token_counter(text=output, model=self.config.name)
            output_dict = {"message": output}
            if self.tools.use_function_calling:
                if response.choices[i].message.tool_calls:  # type: ignore
                    tool_calls = [call.to_dict() for call in response.choices[i].message.tool_calls]  # type: ignore
                else:
                    tool_calls = []
                output_dict["tool_calls"] = tool_calls
            outputs.append(output_dict)
        self._update_stats(input_tokens=input_tokens, output_tokens=output_tokens, cost=cost)
        return outputs

    def _query(
        self, messages: list[dict[str, str]], n: int | None = None, temperature: float | None = None
    ) -> list[dict]:
        if n is None:
            return self._single_query(messages, temperature=temperature)
        outputs = []
        # not needed for openai, but oh well.
        for _ in range(n):
            outputs.extend(self._single_query(messages))
        return outputs

    def query(self, history: History, n: int = 1, temperature: float | None = None) -> list[dict] | dict:
        messages = self._history_to_messages(history)

        def retry_warning(retry_state: RetryCallState):
            exception_info = ""
            if attempt.retry_state.outcome is not None and attempt.retry_state.outcome.exception() is not None:
                exception = attempt.retry_state.outcome.exception()
                exception_info = f" due to {exception.__class__.__name__}: {str(exception)}"

            self.logger.warning(
                f"Retrying LM query: attempt {attempt.retry_state.attempt_number} "
                f"(slept for {attempt.retry_state.idle_for:.2f}s)"
                f"{exception_info}"
            )

        for attempt in Retrying(
            stop=stop_after_attempt(self.config.retry.retries),
            wait=wait_random_exponential(min=self.config.retry.min_wait, max=self.config.retry.max_wait),
            reraise=True,
            retry=retry_if_not_exception_type(
                (
                    ContextWindowExceededError,
                    CostLimitExceededError,
                    RuntimeError,
                    litellm.exceptions.UnsupportedParamsError,
                    litellm.exceptions.NotFoundError,
                    litellm.exceptions.PermissionDeniedError,
                    litellm.exceptions.ContextWindowExceededError,
                    litellm.exceptions.APIError,
                    litellm.exceptions.ContentPolicyViolationError,
                    TypeError,
                    litellm.exceptions.AuthenticationError,
                    ContentPolicyViolationError,
                    ModelConfigurationError,
                    KeyboardInterrupt,
                )
            ),
            before_sleep=retry_warning,
        ):
            with attempt:
                result = self._query(messages, n=n, temperature=temperature)
        if n is None or n == 1:
            return result[0]
        return result

    def _history_to_messages(
        self,
        history: History,
    ) -> list[dict[str, str]]:
        history = copy.deepcopy(history)

        def get_role(history_item: HistoryItem) -> str:
            if history_item["role"] == "system":
                return "user" if self.config.convert_system_to_user else "system"
            return history_item["role"]

        messages = []
        for history_item in history:
            role = get_role(history_item)
            if role == "tool":
                message = {
                    "role": role,
                    "content": history_item["content"],
                    # Only one tool call per observations
                    "tool_call_id": history_item["tool_call_ids"][0],  # type: ignore
                }
            elif (tool_calls := history_item.get("tool_calls")) is not None:
                message = {"role": role, "content": history_item["content"], "tool_calls": tool_calls}
            else:
                message = {"role": role, "content": history_item["content"]}
            if "cache_control" in history_item:
                message["cache_control"] = history_item["cache_control"]
            messages.append(message)
        n_cache_control = str(messages).count("cache_control")
        self.logger.debug(f"n_cache_control: {n_cache_control}")
        return messages


def get_model(args: ModelConfig, tools: ToolConfig) -> AbstractModel:
    """Returns correct model object given arguments and commands"""
    # Convert GenericAPIModelConfig to specific model config if needed
    if isinstance(args, GenericAPIModelConfig) and not isinstance(
        args, HumanModelConfig | HumanThoughtModelConfig | ReplayModelConfig | InstantEmptySubmitModelConfig
    ):
        if args.name == "human":
            args = HumanModelConfig(**args.model_dump())
        elif args.name == "human_thought":
            args = HumanThoughtModelConfig(**args.model_dump())
        elif args.name == "replay":
            args = ReplayModelConfig(**args.model_dump())
        elif args.name == "instant_empty_submit":
            args = InstantEmptySubmitModelConfig(**args.model_dump())

    if args.name == "human":
        assert isinstance(args, HumanModelConfig), f"Expected {HumanModelConfig}, got {args}"
        return HumanModel(args, tools)
    if args.name == "human_thought":
        assert isinstance(args, HumanThoughtModelConfig), f"Expected {HumanThoughtModelConfig}, got {args}"
        return HumanThoughtModel(args, tools)
    if args.name == "replay":
        assert isinstance(args, ReplayModelConfig), f"Expected {ReplayModelConfig}, got {args}"
        return ReplayModel(args, tools)
    elif args.name == "instant_empty_submit":
        assert isinstance(args, InstantEmptySubmitModelConfig), f"Expected {InstantEmptySubmitModelConfig}, got {args}"
        return InstantEmptySubmitTestModel(args, tools)
    assert isinstance(args, GenericAPIModelConfig), f"Expected {GenericAPIModelConfig}, got {args}"
    return LiteLLMModel(args, tools)
