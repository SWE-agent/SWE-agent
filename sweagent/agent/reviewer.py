"""The reviewer implements a retry loop for the agent to retry
solving the issue and to select the best solution.
"""

from __future__ import annotations

import copy
import re
from abc import ABC, abstractmethod
from typing import Any, Literal

import numpy as np
from jinja2 import Template
from pydantic import BaseModel, ConfigDict

from sweagent.agent.history_processors import _set_cache_control
from sweagent.agent.models import (
    AbstractModel,
    InstanceStats,
    ModelConfig,
    get_model,
)
from sweagent.agent.problem_statement import ProblemStatement
from sweagent.tools.parsing import ActionParser
from sweagent.tools.tools import ToolConfig
from sweagent.types import AgentInfo, Trajectory, TrajectoryStep
from sweagent.utils.log import get_logger


class ReviewSubmission(BaseModel):
    """Information that's passed to the reviewer"""

    #: Total trajectory (including several retries)
    trajectory: Trajectory
    #: Aggregate info dict (including several retries)
    info: AgentInfo
    #: Model stats for this attempt
    model_stats: InstanceStats

    def to_format_dict(self, *, suffix="") -> dict[str, Any]:
        """Return all the data that is used to format the
        messages. Trajectory is excluded because it needs special treatment.
        """
        out = {}
        info = copy.deepcopy(self.info)
        if not info.get("submission"):
            # Observed that not all exit_cost lead to autosubmission
            # so sometimes this might be missing.
            info["submission"] = ""
        for k, v in info.items():
            if isinstance(v, str):
                out[f"{k}{suffix}"] = v
            elif isinstance(v, dict):
                for k2, v2 in v.items():
                    out[f"{k}_{k2}{suffix}"] = v2
        return out


class ReviewerResult(BaseModel):
    accept: bool | float
    outputs: list[str]
    messages: list[dict[str, Any]]


class PreselectorOutput(BaseModel):
    chosen_idx: list[int]
    response: str
    messages: list[dict[str, Any]]


class ChooserOutput(BaseModel):
    chosen_idx: int
    response: str
    preselector_output: PreselectorOutput | None = None
    messages: list[dict[str, Any]]


# --- INTERFACES ---


class AbstractReviewer(ABC):
    """The reviewer checks a single solution and tries to predict
    if it successfully solves the issue.
    """

    @abstractmethod
    def review(self, instance: ProblemStatement, submission: ReviewSubmission) -> ReviewerResult:
        """Returns True if the submission is believed to be correct"""


class AbstractRetryLoop(ABC):
    """The review loop controls how often the agent tries to solve
    the issue and how it selects the best solution.
    """

    def retry(self) -> bool:
        """Returns True if the agent should retry solving the issue"""
        return False

    def on_submit(self, submission: ReviewSubmission) -> None:
        """Called when the agent submits a solution"""

    def on_model_query(self, attempt_stats: InstanceStats):
        """Called before the model is queried. Can be used to implement
        stop conditions based on attempt cost etc.
        """

    def on_attempt_started(self, i_attempt: int, agent):
        """Called when a new attempt is started"""
        pass

    @abstractmethod
    def get_best(self) -> int:
        """Returns the best solution"""

    def get_forwarded_vars(self) -> dict[str, Any]:
        """Get the variables that should be forwarded to the next iteration.

        Returns:
            A dictionary of variables that should be forwarded to the next iteration.
        """
        return {}


# --- CONFIGS ---


class PreselectorConfig(BaseModel):
    model: ModelConfig
    system_template: str
    instance_template: str
    submission_template: str
    max_len_submission: int = 5000


class ChooserConfig(BaseModel):
    model: ModelConfig
    system_template: str
    instance_template: str
    submission_template: str
    max_len_submission: int = 5000
    preselector: PreselectorConfig | None = None


class TrajFormatterConfig(BaseModel):
    #: Filter the following actions from the trajectory
    filter: list[str] = []
    #: Filter outputs from the following actions from the trajectory
    output_filter: list[str] = []
    #: Format of the trajectory item
    item_template: str = "Model: {{response}}\n\nObservation: {{observation}}"
    only_show_last_n_output: int = 0

    model_config = ConfigDict(extra="forbid")


class ReviewerConfig(BaseModel):
    """The configuration for the reviewer"""

    system_template: str
    instance_template: str
    #: If a submission autosubmits because of total cost or a similar exit status,
    #: it will get this malus to its score
    failure_score_penalty: float = 0.0
    traj_formatter: TrajFormatterConfig
    n_sample: int = 5
    reduce_by_std: float = 0.0
    score_range: tuple[float | None, float | None] = (None, None)
    #: If set, we assume that the score is in the range [score_range[0], score_range[1]]
    #: Reviews that are outside this range will be ignored

    type: Literal["reviewer"] = "reviewer"

    model_config = ConfigDict(extra="forbid")

    def get_reviewer(self, model: AbstractModel) -> AbstractReviewer:
        return Reviewer(self, model)


class ChooserRetryLoopConfig(BaseModel):
    type: Literal["chooser"] = "chooser"
    chooser: ChooserConfig

    max_attempts: int
    min_budget_for_new_attempt: float = 0.0
    """Minimal $ that need to be left in order for us to start a new attempt.
    If set to 0: Always.
    """

    cost_limit: float
    """The maximum cost to spend on all attempts. Does not include cost of choosing.
    """

    model_config = ConfigDict(extra="forbid")

    def get_retry_loop(self, problem_statement: ProblemStatement) -> ChooserRetryLoop:
        return ChooserRetryLoop(self, problem_statement)


class ScoreRetryLoopConfig(BaseModel):
    """The configuration for the review loop"""

    type: Literal["score"] = "score"

    reviewer_config: ReviewerConfig

    accept_score: float
    max_accepts: int = 1
    max_attempts: int

    min_budget_for_new_attempt: float = 0.0
    """Minimal $ that need to be left in order for us to start a new attempt.
    If set to 0: Always.
    """

    cost_limit: float
    """The maximum cost to spend on all attempts and reviews except the last review.
    The last review is not included in the cost limit, because we would waste the last
    attempt if we couldn't score it.
    """

    model: ModelConfig

    model_config = ConfigDict(extra="forbid")

    def validate(self):
        """Checks config. Raises `ValueError` in case of misconfiguration"""
        ...

    def __post_init__(self):
        self.validate()

    def get_retry_loop(self, problem_statement: ProblemStatement) -> ScoreRetryLoop:
        return ScoreRetryLoop(self, problem_statement)


RetryLoopConfig = ScoreRetryLoopConfig | ChooserRetryLoopConfig

# --- IMPLEMENTATIONS ---


class Preselector:
    def __init__(self, config: PreselectorConfig):
        self.config = config
        self.model = get_model(config.model, ToolConfig(parse_function=ActionParser()))
        self.logger = get_logger("chooser", emoji="🧠")

    def interpret(self, response: str) -> list[int]:
        if not response:
            self.logger.warning("No response from preselector")
            return []
        # Use regex to extract the last number of the response
        last_line = response.splitlines()[-1]
        try:
            return [int(i) for i in re.findall(r"\d+", last_line)]
        except Exception as e:
            self.logger.error(f"Error interpreting response: {e}")
            return []

    def format_submission(self, problem_statement: str, submission: ReviewSubmission) -> str:
        if (
            submission.info.get("submission") is None
            or len(submission.info.get("submission", "")) > self.config.max_len_submission > 0  # type: ignore
        ):
            return "Solution invalid."
        return Template(self.config.submission_template).render(
            **submission.to_format_dict(),
            # summary=self.summarizer.summarize(problem_statement, submission.trajectory) if self.summarizer else "",
        )

    def build_messages(self, problem_statement: str, input: list[ReviewSubmission]) -> list[dict[str, Any]]:
        instance_message = Template(self.config.instance_template).render(
            problem_statement=problem_statement,
            submissions=[self.format_submission(problem_statement, s) for s in input],
        )
        self.logger.debug(f"MODEL INPUT (user)\n{instance_message}")
        return [
            {"role": "system", "content": self.config.system_template},
            {"role": "user", "content": instance_message},
        ]

    def choose(self, problem_statement: str, input: list[ReviewSubmission]) -> PreselectorOutput:
        messages = self.build_messages(problem_statement, input)
        response = self.model.query(messages)["message"]  # type: ignore
        indices = self.interpret(response)
        if not indices:
            self.logger.warning("No indices found in response, using all indices")
            indices = list(range(len(input)))
        return PreselectorOutput(chosen_idx=indices, response=response, messages=messages)


class Chooser:
    def __init__(self, config: ChooserConfig):
        self.config = config
        self.model = get_model(config.model, ToolConfig(parse_function=ActionParser()))
        self.logger = get_logger("chooser", emoji="🧠")
        # self.summarizer = Summarizer(config.summarizer, self.model) if config.summarizer else None

    def interpret(self, response: str) -> int:
        # Use regex to extract the last number of the response
        try:
            return int(re.findall(r"\d+", response)[-1])
        except Exception as e:
            self.logger.error(f"Error interpreting response: {e}")
            return 0

    def format_submission(self, problem_statement: str, submission: ReviewSubmission) -> str:
        if (
            submission.info.get("submission") is None
            or len(submission.info.get("submission", "")) > self.config.max_len_submission > 0  # type: ignore
        ):
            return "Solution invalid."
        return Template(self.config.submission_template).render(
            **submission.to_format_dict(),
            # summary=self.summarizer.summarize(problem_statement, submission.trajectory) if self.summarizer else "",
        )

    def build_messages(self, problem_statement: str, input: list[ReviewSubmission]) -> list[dict[str, Any]]:
        instance_message = Template(self.config.instance_template).render(
            problem_statement=problem_statement,
            submissions=[self.format_submission(problem_statement, s) for s in input],
        )
        self.logger.debug(f"MODEL INPUT (user)\n{instance_message}")
        return [
            {"role": "system", "content": self.config.system_template},
            {"role": "user", "content": instance_message},
        ]

    def choose(self, problem_statement: str, input: list[ReviewSubmission]) -> ChooserOutput:
        preselector_output = None
        selected_indices = list(range(len(input)))
        n_submitted = sum(s.info.get("exit_status", "") == "submitted" for s in input)
        if n_submitted >= 2:
            self.logger.debug(f"Got {n_submitted} submitted submissions, only using them")
            selected_indices = [i for i, s in enumerate(input) if s.info.get("exit_status", "") == "submitted"]
        else:
            self.logger.debug(f"Got only {n_submitted} submitted submissions, disabling exit status filtering")
        if self.config.preselector and len(selected_indices) > 2:
            preselector = Preselector(self.config.preselector)
            try:
                preselector_output = preselector.choose(problem_statement, [input[i] for i in selected_indices])
            except Exception as e:
                self.logger.critical(f"Preselector failed: {e}", exc_info=True)
                preselector_output = None
            if preselector_output and preselector_output.chosen_idx:
                try:
                    _preselected_indices = [selected_indices[i] for i in preselector_output.chosen_idx]
                except IndexError:
                    _preselected_indices = []
                    self.logger.error("Preselector gave invalid indices, ignoring it.")
                if not _preselected_indices:
                    self.logger.error("Preselector gave no valid indices, ignoring it.")
                else:
                    selected_indices = _preselected_indices
            else:
                self.logger.error("Preselector must have failed, ignoring it.")
        messages = self.build_messages(problem_statement, [input[i] for i in selected_indices])
        chosen_idx = None
        response = ""
        try:
            response = self.model.query(messages)["message"]  # type: ignore
            chosen_idx = self.interpret(response)
        except Exception as e:
            self.logger.critical(f"Chooser failed: {e}", exc_info=True)
            chosen_idx = None
        if chosen_idx is None or not (0 <= chosen_idx < len(selected_indices)):
            self.logger.error(f"Invalid chosen index: {chosen_idx}, using first index")
            chosen_idx = selected_indices[0]
        else:
            chosen_idx = selected_indices[chosen_idx]
        return ChooserOutput(
            chosen_idx=chosen_idx, response=response, preselector_output=preselector_output, messages=messages
        )


class Reviewer(AbstractReviewer):
    def __init__(self, config: ReviewerConfig, model):
        self._config = config
        self._model = model
        self._traj_formatter = TrajectoryFormatter(config=config.traj_formatter)
        self.logger = get_logger("reviewer", emoji="🧑‍⚖️")

    def format_messages(self, instance: ProblemStatement, submission: ReviewSubmission):
        system_message = self._config.system_template
        self.logger.debug(f"MODEL INPUT (system)\n{system_message}")
        ps_format_dict = {
            "problem_statement": instance.get_problem_statement(),
            **instance.get_extra_fields(),
        }
        user_message = Template(self._config.instance_template).render(
            **ps_format_dict,
            **submission.to_format_dict(),
            traj=self._traj_formatter.format_trajectory(submission.trajectory),
        )
        self.logger.debug(f"MODEL INPUT (user)\n{user_message}")
        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]

    def interpret(self, response: str) -> bool | float:
        last_line = response.strip().split("\n")[-1].strip()
        # Find all numbers in the last line and take the last one
        numbers = re.findall(r"-?\d+\.?\d*", last_line)
        if not numbers:
            msg = f"Could not interpret response: {last_line!r}"
            raise ValueError(msg)
        number = float(numbers[-1])
        if self._config.score_range[0] is not None and number < self._config.score_range[0]:
            msg = f"Score {number} is below the minimum score {self._config.score_range[0]}"
            raise ValueError(msg)
        if self._config.score_range[1] is not None and number > self._config.score_range[1]:
            msg = f"Score {number} is above the maximum score {self._config.score_range[1]}"
            raise ValueError(msg)
        return number

    def review(self, instance: ProblemStatement, submission: ReviewSubmission) -> ReviewerResult:
        exit_status = submission.info.get("exit_status")
        messages = []
        penalty = 0.0
        if not exit_status or exit_status.strip() != "submitted":
            penalty = self._config.failure_score_penalty
        messages = self.format_messages(instance, submission)
        if self._config.n_sample > 1:
            _set_cache_control(messages[-1])  # type: ignore
        answers = []
        accepts = []
        for _ in range(self._config.n_sample):
            try:
                answer = self._model.query(messages)["message"]
            except Exception as e:
                self.logger.warning(f"Query failed: {e}", exc_info=True)
                continue
            try:
                score = self.interpret(answer)
            except ValueError as e:
                self.logger.warning(f"Could not interpret response: {answer!r}, got {e}")
                continue
            answers.append(answer)
            accepts.append(score)
        if not accepts:
            answers = ["No valid scores found, failing submission"]
            accepts = [-100.0]
        accept = sum(accepts) / len(accepts) - penalty
        std = np.std(accepts).item()
        if self._config.reduce_by_std > 0:
            accept -= std * self._config.reduce_by_std
        self.logger.info(f"First answer: {answers[0]}")
        self.logger.info(f"Final score: {accept} (penalty: {penalty}, std: {std}), individual: {accepts}")
        return ReviewerResult(accept=accept, outputs=answers, messages=messages)


# todo: Couldn't I just replace the whole thing with Jinja templates?


class TrajectoryFormatter:
    def __init__(
        self,
        config: TrajFormatterConfig,
    ):
        """Formats trajectories for the use in prompts"""
        self._config = config

    def _include_step(self, item: TrajectoryStep) -> bool:
        action = item["action"].strip()
        for f in self._config.filter:
            if action.startswith(f):
                return False
        return True

    def _include_step_output(self, item: TrajectoryStep, i_step: int, n_steps: int) -> bool:
        if self._config.only_show_last_n_output > 0 and i_step < n_steps - self._config.only_show_last_n_output:
            return False
        action = item["action"].strip()
        for f in self._config.output_filter:
            if action.startswith(f):
                return False
        return True

    def _format_trajectory_step(self, step: TrajectoryStep, i_step: int, *, n_steps: int, i_traj: int = 1) -> str:
        step = copy.deepcopy(step)
        if not self._include_step_output(step, i_step, n_steps=n_steps):
            step["observation"] = "[Output omitted]"
        return Template(self._config.item_template).render(
            **step,
            i_step=i_step,
            i_traj=i_traj,
        )

    def format_trajectory(self, trajectory: Trajectory, i_traj: int = 1) -> str:
        traj_messages = [step for step in trajectory if self._include_step(step)]
        return "\n\n".join(
            [
                self._format_trajectory_step(step, i_step, i_traj=i_traj, n_steps=len(traj_messages))
                for i_step, step in enumerate(traj_messages)
            ]
        )


class ChooserRetryLoop(AbstractRetryLoop):
    def __init__(self, config: ChooserRetryLoopConfig, problem_statement: ProblemStatement):
        self._config = config
        self._problem_statement = problem_statement
        self._chooser = Chooser(config.chooser)
        self._submissions: list[ReviewSubmission] = []
        self._n_consec_exit_cost: int = 0
        self.logger = get_logger("chooser_loop", emoji="🔄")
        self._chooser_output: ChooserOutput | None = None

    @property
    def _total_stats(self) -> InstanceStats:
        return sum((s.model_stats for s in self._submissions), start=InstanceStats())

    @property
    def review_model_stats(self) -> InstanceStats:
        return InstanceStats()

    @property
    def _n_attempts(self) -> int:
        return len(self._submissions)

    def on_submit(self, submission: ReviewSubmission) -> None:
        self._submissions.append(submission)

    def retry(self) -> bool:
        stat_str = f"n_samples={self._n_attempts}"
        if self._total_stats.instance_cost > self._config.cost_limit > 0:
            self.logger.info(
                f"Exiting retry loop ({stat_str}): Total attempt cost ({self._total_stats.instance_cost}) "
                f"exceeds cost limit ({self._config.cost_limit})"
            )
            return False

        if self._n_attempts >= self._config.max_attempts > 0:
            self.logger.info(f"Exiting retry loop ({stat_str}): max_attempts={self._config.max_attempts} reached")
            return False

        remaining_budget = self._config.cost_limit - self._total_stats.instance_cost
        if self._config.min_budget_for_new_attempt > 0 and remaining_budget < self._config.min_budget_for_new_attempt:
            msg = (
                f"Exiting retry loop ({stat_str}): Not enough budget left for a new attempt "
                f"({remaining_budget} remaining, {self._config.min_budget_for_new_attempt} required)"
            )
            self.logger.info(msg)
            return False

        return True

    def get_best(self) -> int | None:
        """Important note: This is cached. Only call this at the end."""
        if self._chooser_output is not None:
            return self._chooser_output.chosen_idx
        if len(self._submissions) == 0:
            return None
        self._chooser_output = self._chooser.choose(self._problem_statement.get_problem_statement(), self._submissions)
        return self._chooser_output.chosen_idx


# todo: The model shouldn't be defined here, it should be defined as part of the scorer
class ScoreRetryLoop(AbstractRetryLoop):
    def __init__(
        self,
        config: ScoreRetryLoopConfig,
        problem_statement: ProblemStatement,
    ):
        # This model will not share instance cost with the parent agent
        self._model = get_model(config.model, tools=ToolConfig())
        self._problem_statement = problem_statement
        self._reviewer: AbstractReviewer = config.reviewer_config.get_reviewer(self._model)
        self._config = config
        # Note: These are "cumulative" submissions, i.e., they include all retries
        # up to that point.
        self._submissions: list[ReviewSubmission] = []
        self._reviews: list[ReviewerResult] = []
        #: Number of consecutive exit cost submissions
        self._n_consec_exit_cost: int = 0
        self.logger = get_logger("review_loop", emoji="🔄")

    # Properties
    # ----------

    @property
    def review_model_stats(self) -> InstanceStats:
        return self._model.stats

    @property
    def reviews(self) -> list[ReviewerResult]:
        return self._reviews

    @property
    def _n_attempts(self) -> int:
        return len(self._submissions)

    @property
    def _n_accepted(self) -> int:
        return sum(r.accept >= self._config.accept_score for r in self._reviews)

    @property
    def _total_stats(self) -> InstanceStats:
        return sum((s.model_stats for s in self._submissions), start=InstanceStats()) + self._model.stats

    # -------

    def on_submit(self, submission: ReviewSubmission) -> None:
        self._submissions.append(submission)
        self._review()

    def _review(self) -> float:
        review = self._reviewer.review(self._problem_statement, self._submissions[-1])
        self._reviews.append(review)
        exit_status = self._submissions[-1].info.get("exit_status", "")
        if exit_status and "exit_cost" in exit_status.lower():
            self._n_consec_exit_cost += 1
        else:
            self._n_consec_exit_cost = 0
        return review.accept

    def retry(self) -> bool:
        max_score = max([r.accept for r in self._reviews], default=-100.0)
        stat_str = f"n_samples={self._n_attempts}, max_score={max_score}, n_accepted={self._n_accepted}"

        if self._total_stats.instance_cost > self._config.cost_limit > 0:
            self.logger.info(
                f"Exiting retry loop ({stat_str}): Total attempt cost ({self._total_stats.instance_cost}) "
                f"exceeds cost limit ({self._config.cost_limit})"
            )
            return False

        if self._n_attempts >= self._config.max_attempts > 0:
            self.logger.info(f"Exiting retry loop ({stat_str}): max_attempts={self._config.max_attempts} reached")
            return False

        if self._n_accepted >= self._config.max_accepts > 0:
            self.logger.info(f"Exiting retry loop ({stat_str}): max_accepts={self._config.max_accepts} reached")
            return False

        remaining_budget = self._config.cost_limit - self._total_stats.instance_cost
        if self._config.min_budget_for_new_attempt > 0 and remaining_budget < self._config.min_budget_for_new_attempt:
            msg = (
                f"Exiting retry loop ({stat_str}): Not enough budget left for a new attempt "
                f"({remaining_budget} remaining, {self._config.min_budget_for_new_attempt} required)"
            )
            self.logger.info(msg)
            return False

        return True

    def get_best(self) -> int | None:
        if len(self._reviews) == 0:
            return None
        scores = [r.accept for r in self._reviews]
        self.logger.debug(f"Scores: {scores}")
        max_score = np.max(scores)
        max_indices = [i for i, s in enumerate(scores) if np.isclose(s, max_score)]
        # If there are multiple submissions with the same score, choose the shortest one
        max_indices = sorted(max_indices, key=lambda i: self._submissions[i].model_stats.api_calls or float("inf"))
        chosen_idx = max_indices[0]
        self.logger.info(f"Best submission: {chosen_idx}")
        return chosen_idx


def get_retry_loop_from_config(
    config: RetryLoopConfig, problem_statement: ProblemStatement
) -> ScoreRetryLoop | ChooserRetryLoop:
    return config.get_retry_loop(problem_statement=problem_statement)
