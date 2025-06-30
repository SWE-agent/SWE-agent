from pathlib import Path
from typing import Self

from sweagent.agent.agents import DefaultAgent, ShellAgentConfig
from sweagent.agent.models import HumanModel, HumanModelConfig, get_model
from sweagent.agent.problem_statement import ProblemStatement, ProblemStatementConfig
from sweagent.environment.swe_env import SWEEnv
from sweagent.tools.parsing import ActionOnlyParser
from sweagent.tools.tools import ToolHandler
from sweagent.types import AgentRunResult, StepOutput


class ShellAgent(DefaultAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def from_config(cls, config: ShellAgentConfig) -> Self:
        # To ensure that all models stay completely independent, we deepcopy the
        # model config, because it lives on as a property in the model, tools, etc.
        config = config.model_copy(deep=True)
        model = get_model(config.model, config.tools)
        return cls(
            templates=config.templates,
            tools=ToolHandler(config.tools),
            history_processors=config.history_processors,
            model=model,
            max_requeries=config.max_requeries,
        )

    def human_step_in(self) -> None:
        """Replace the current model with a HumanModel instance.
        This allows for human intervention during agent execution.
        """
        self._original_model = self.model
        self._original_parser = self.tools.config.parse_function

        human_config = HumanModelConfig(name="human", catch_eof=False)
        self.model = get_model(human_config, self.tools.config)
        self.tools.config.parse_function = ActionOnlyParser()

        self.logger.info("Switched to human mode. Agent will now accept human input. Press ^D to switch back.")

    def human_step_out(self) -> None:
        """Switch back to the original model from human mode.
        This is called when ^D is pressed in human mode.
        """
        if not hasattr(self, "_original_model") or self._original_model is None:
            self.logger.info("No previous model to switch back to. Remaining in current mode.")
            return

        self.model = self._original_model
        self.tools.config.parse_function = self._original_parser  # type: ignore
        self._original_model = None
        self._original_parser = None

        self.logger.info("Switched back to AI model mode.")

    def run(
        self,
        env: SWEEnv,
        problem_statement: ProblemStatement | ProblemStatementConfig,
        *,
        output_dir: Path = Path("."),
    ) -> AgentRunResult:
        """Run the agent on a problem instance. This method contains the
        main loop that repeatedly calls `self._step` until the problem is solved.

        Args:
            setup_args: Arguments to pass to the agent's setup method.
            env: The environment to run the agent on.
            traj_dir: Directory to save the trajectory to
            interruptible: Whether the human can jump in by pressing ^C
        """
        self.setup(env=env, problem_statement=problem_statement, output_dir=output_dir)

        # Run action/observation loop
        self._chook.on_run_start()
        step_output = StepOutput()
        while not step_output.done:
            try:
                step_output = self.step()
                self.save_trajectory()
            except KeyboardInterrupt:
                if not isinstance(self.model, HumanModel):
                    self.human_step_in()
                    continue
                raise
            except EOFError:
                # Can only happen if we have a human model, so switch back
                self.logger.info("Detected ^D - switching back to AI mode")
                self.human_step_out()
                continue
            if step_output.done and not isinstance(self.model, HumanModel):
                # Human has to submit the solution
                self.logger.info("Robot is done! Please submit the solution.")
                self.human_step_in()
                step_output.done = False
        self._chook.on_run_done(trajectory=self.trajectory, info=self.info)

        self.logger.info("Trajectory saved to %s", self.traj_path)

        # Here we want to return the "global" information (e.g., submission should
        # be the best submission instead of the last one, etc.), so we get it from the traj file
        data = self.get_trajectory_data()
        return AgentRunResult(info=data["info"], trajectory=data["trajectory"])
