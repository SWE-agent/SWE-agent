from abc import abstractmethod
from textwrap import dedent
from typing import Any, Literal

from jinja2 import Template
from pydantic import BaseModel

from sweagent.agent.models import AbstractModel
from sweagent.agent.problem_statement import ProblemStatement
from sweagent.exceptions import FormatError
from sweagent.tools.tools import ToolHandler
from sweagent.types import Trajectory
from sweagent.utils.log import get_logger


class ActionSamplerOutput(BaseModel):
    completion: dict[str, Any]
    messages: list[dict[str, Any]] = []
    trajectory_items: list[dict[str, Any]] = []
    extra_info: dict[str, Any] = {}


class AbstractActionSampler:
    def __init__(self, model: AbstractModel, tools: ToolHandler):
        self._model = model
        self._tools = tools
        self._logger = get_logger("action_sampler", emoji="👥")

    @abstractmethod
    def get_action(
        self,
        problem_statement: ProblemStatement,
        trajectory: Trajectory,
        history: list[dict[str, Any]],
    ) -> ActionSamplerOutput:
        """Returns action with tool calls"""
        pass


class AskColleaguesConfig(BaseModel):
    type: Literal["ask_colleagues"] = "ask_colleagues"

    n_samples: int = 2

    def get(self, model: AbstractModel, tools: ToolHandler) -> "AskColleagues":
        return AskColleagues(self, model, tools)


class AskColleagues(AbstractActionSampler):
    def __init__(self, config: AskColleaguesConfig, model: AbstractModel, tools: ToolHandler):
        super().__init__(model, tools)
        self.config = config

    def get_colleague_discussion(self, completions: list[dict[str, Any]]) -> str:
        """Concat all completions into a single string"""
        out = "Your colleagues had the following ideas: \n\n"
        n_parsed_ok = 0
        for i, completion in enumerate(completions):
            try:
                thought, action = self._tools.parse_actions(completion)
            except FormatError:
                self._logger.warning("Could not parse completion %s, skipping.", completion)
                continue
            n_parsed_ok += 1
            out += f"Thought (colleague {i}): {thought}\nProposed Action (colleague {i}): {action}\n\n"
        if n_parsed_ok == 0:
            msg = "No completions could be parsed."
            raise FormatError(msg)
        out += (
            "Please summarize and compare the ideas and propose and action to take. "
            "Finally choose one action to perform and explain it in detail and include it as a tool call. "
            "<important>You must include a thought and action (as a tool/function call). Do not try to invoke commands with triple backticks, use function calls instead.</important>"
        )
        return out

    def get_action(
        self,
        problem_statement: ProblemStatement,
        trajectory: Trajectory,
        history: list[dict[str, Any]],
    ) -> ActionSamplerOutput:
        """Returns action with tool calls"""
        completions = self._model.query(history, n=self.config.n_samples)  # type: ignore
        discussion = self.get_colleague_discussion(completions)
        self._logger.info(f"COLLEAGUE DISCUSSION:\n{discussion}")
        new_messages = [
            {"role": "user", "content": discussion},
        ]
        final_completion = self._model.query(history + new_messages)  # type: ignore
        return ActionSamplerOutput(
            completion=final_completion,
            extra_info={"colleagues": discussion},
        )


class BinaryTrajectoryComparisonConfig(BaseModel):
    type: Literal["binary_trajectory_comparison"] = "binary_trajectory_comparison"

    min_n_samples: int = 4
    max_n_samples: int = 10

    comparison_temperature: float | None = None
    """Override the model's temperature. If None, take the temperature configured for the model."""

    system_template: str = """<setting>You are an expert software engineer overseeing junior developers. They suggest actions to take to solve a problem. You must choose the best action to take. </setting>"""
    instance_template: str = dedent("""
    We're solving the following problem

    <problem_statement>
    {{problem_statement}}
    </problem_statement>

    So far, we've performed the following actions:

    <trajectory>
    {{traj}}
    </trajectory>
    """)

    comparison_template: str = dedent("""
    Two junior developers suggested the following actions:

    <thought1>
    {{thought1}}
    </thought1>

    <action1>
    {{action1}}
    </action1>

    <thought2>
    {{thought2}}
    </thought2>

    <action2>
    {{action2}}
    </action2>

    Please compare the two actions in detail.

    Which action should we take?

    If you think the first action is better, respond with "first".
    If you think the second action is better, respond with "second".

    The last line of your response MUST be "first" or "second".
    """)

    def get(self, model: AbstractModel, tools: ToolHandler) -> "BinaryTrajectoryComparison":
        return BinaryTrajectoryComparison(self, model, tools)


class BinaryTrajectoryComparison(AbstractActionSampler):
    def __init__(self, config: BinaryTrajectoryComparisonConfig, model: AbstractModel, tools: ToolHandler):
        super().__init__(model, tools)
        self.config = config

    def _format_trajectory(self, trajectory: Trajectory) -> str:
        steps = []
        for i, step in enumerate(trajectory):
            steps.append(f"Action {i}: {step['action']}\n Observation {i}: {step['observation']}")
        return "\n".join(steps)

    def format_messages(
        self,
        *,
        problem_statement: ProblemStatement,
        trajectory: Trajectory,
        thought1: str,
        action1: str,
        thought2: str,
        action2: str,
        use_cache_control: bool = False,
    ) -> list[dict]:
        system_message = self.config.system_template
        self._logger.debug(f"MODEL INPUT (system)\n{system_message}")
        ps_format_dict = {
            "problem_statement": problem_statement.get_problem_statement(),
            **problem_statement.get_extra_fields(),
        }
        user_message = Template(self.config.instance_template).render(
            **ps_format_dict,
            traj=self._format_trajectory(trajectory),
        )
        self._logger.debug(f"MODEL INPUT (instance)\n{user_message}")
        comparison_message = Template(self.config.comparison_template).render(
            thought1=thought1,
            action1=action1,
            thought2=thought2,
            action2=action2,
        )
        self._logger.debug(f"MODEL INPUT (comparison)\n{comparison_message}")
        cache_control_kwargs = {"cache_control": {"type": "ephemeral"}} if use_cache_control else {}
        return [
            {"role": "system", "content": system_message},
            {
                "role": "user",
                "content": [{"type": "text", "text": user_message, **cache_control_kwargs}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": comparison_message,
                    }
                ],
            },
        ]

    def filter_duplicates(self, completions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter out duplicate actions"""
        thoughts: list[str] = []
        actions: list[str] = []
        filtered_completions: list[dict[str, Any]] = []
        for pc in completions:
            thought, action = self._tools.parse_actions(pc)
            if action not in actions:
                thoughts.append(thought)
                actions.append(action)
                filtered_completions.append(pc)

        if len(filtered_completions) < len(completions):
            self._logger.debug("Filtering duplicates: %d -> %d", len(completions), len(filtered_completions))

        return filtered_completions

    def filter_parseable_completions(self, completions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        filtered_completions = []
        for completion in completions:
            try:
                self._tools.parse_actions(completion)
            except FormatError:
                self._logger.warning("Could not parse completion %s, skipping.", completion)
                continue
            filtered_completions.append(completion)
        if len(filtered_completions) == 0:
            msg = "No completions could be parsed."
            raise FormatError(msg)
        return filtered_completions

    def contains_edits(self, completions: list[dict[str, Any]]) -> bool:
        keywords = ["edit", "str_replace_editor insert", "str_replace_editor str_replace"]
        for completion in completions:
            _, action = self._tools.parse_actions(completion)
            normalized_action = action.lstrip()
            if any(normalized_action.startswith(keyword) for keyword in keywords):
                return True
        return False

    def get_completions(self, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        completions = self._model.query(history, n=self.config.min_n_samples)  # type: ignore
        completions = self.filter_parseable_completions(completions)
        completions = self.filter_duplicates(completions)
        if not completions:
            msg = "No completions could be parsed."
            raise FormatError(msg)
        if self.contains_edits(completions) and self.config.min_n_samples < self.config.max_n_samples:
            self._logger.debug("Edits were proposed, will sample more")
            new_completions = self._model.query(history, n=self.config.max_n_samples - self.config.min_n_samples)  # type: ignore
            completions = self.filter_duplicates(self.filter_parseable_completions(completions + new_completions))
        if len(completions) == 1:
            _, action = self._tools.parse_actions(completions[0])
            self._logger.warning("Only identical actions were proposed (action=%s)", action)
        return completions

    def get_action(
        self,
        *,
        problem_statement: ProblemStatement,
        trajectory: Trajectory,
        history: list[dict[str, Any]],
    ) -> ActionSamplerOutput:
        completions = self.get_completions(history)
        best_idx = 0
        comparison_log = []
        for i in range(1, len(completions)):
            thought1, action1 = self._tools.parse_actions(completions[best_idx])
            thought2, action2 = self._tools.parse_actions(completions[i])
            messages = self.format_messages(
                problem_statement=problem_statement,
                trajectory=trajectory,
                thought1=thought1,
                action1=action1,
                thought2=thought2,
                action2=action2,
                use_cache_control=len(completions) >= 3,
            )
            response = self._model.query(messages, temperature=self.config.comparison_temperature)["message"]  # type: ignore
            self._logger.info(f"RESPONSE: {response}")
            idx = self.interpret(response)
            comparison_log.append(
                {
                    "comparison_between": (best_idx, i),
                    "messages": messages,
                    "response": response,
                    "idx": idx,
                }
            )
            best_idx = i if idx == 1 else best_idx

        return ActionSamplerOutput(
            completion=completions[best_idx],
            extra_info={"comparison_log": comparison_log},
        )

    def interpret(self, response: str) -> Literal[0, 1]:
        """Interpret response from LM. Note: 1-based indexing"""
        last_line = response.strip().split("\n")[-1].strip()
        if "first" in last_line.lower():
            return 0
        elif "second" in last_line.lower():
            return 1
        self._logger.warning("Could not interpret response: %s, will choose first submission.", response)
        return 0


ActionSamplerConfig = BinaryTrajectoryComparisonConfig | AskColleaguesConfig
