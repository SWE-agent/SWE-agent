import os
import random
import shlex

from ghapi.all import GhApi
from pydantic import BaseModel

from sweagent.environment.swe_env import SWEEnv
from sweagent.run.hooks.abstract import RunHook
from sweagent.types import AgentRunResult
from sweagent.utils.github import (
    InvalidGithubURL,
    _get_associated_commit_urls,
    _get_gh_issue_data,
    _parse_gh_issue_url,
)
from sweagent.utils.log import get_logger

# NOTE
# THE IMPLEMENTATION DETAILS HERE WILL CHANGE SOON!


# fixme: Bring back the ability to open the PR to a fork
def open_pr(*, logger, token, env: SWEEnv, github_url, trajectory, _dry_run: bool = False) -> None:
    """Create PR to repository

    Args:
        trajectory: Trajectory of actions taken by the agent
        _dry_run: Whether to actually push anything or just simulate it
    """

    issue_url = github_url
    logger.info("Opening PR")
    try:
        issue = _get_gh_issue_data(issue_url, token=token)
    except InvalidGithubURL as e:
        msg = "Data path must be a github issue URL if open_pr is set to True."
        raise ValueError(msg) from e
    branch_name = f"swe-agent-fix-#{issue.number}-" + str(random.random())[2:10]
    env.communicate(
        input="git config user.email 'noemail@swe-agent.com' && git config user.name 'SWE-agent'",
        error_msg="Failed to set git user",
        timeout=10,
        check="raise",
    )
    env.communicate(input="rm -f model.patch", error_msg="Failed to remove model patch", timeout=10, check="raise")
    env.communicate(
        input=f"git checkout -b {branch_name}", error_msg="Failed to switch to new branch", timeout=10, check="raise"
    )
    env.communicate(input="git add .", error_msg="Failed to add commits", timeout=10, check="raise")
    dry_run_flag = "--allow-empty" if _dry_run else ""
    commit_msg = [
        shlex.quote("Fix: {issue.title}"),
        shlex.quote("Closes #{issue.number}"),
    ]
    out = env.communicate(
        input=f"git commit -m {commit_msg[0]} -m  {commit_msg[1]} {dry_run_flag}",
        error_msg="Failed to commit changes",
        timeout=10,
        check="raise",
    )
    logger.debug(f"Committed changes: {out}")

    owner, repo, _ = _parse_gh_issue_url(issue_url)
    # fixme: bring this back
    # If `--repo_path` was specified with a different github URL, then the record will contain
    # the forking user
    forker = owner
    head = branch_name
    remote = "origin"
    if forker != owner:
        head = f"{forker}:{branch_name}"
        token_prefix = ""
        if token:
            token_prefix = f"{token}@"
        fork_url = f"https://{token_prefix}github.com/{forker}/{repo}.git"
        logger.debug(f"Using fork: {fork_url}")
        env.communicate(
            input=f"git remote add fork {fork_url}",
            error_msg="Failed to create new git remote",
            timeout=10,
        )
        remote = "fork"
    dry_run_prefix = "echo " if _dry_run else ""
    out = env.communicate(
        input=f"{dry_run_prefix} git push {remote} {branch_name}",
        error_msg=(
            "Failed to push branch to remote. Please check your token and permissions. "
            "You might want to push to a fork with the push_gh_repo_url option."
        ),
        timeout=10,
    )
    logger.debug(f"Pushed commit to {remote=} {branch_name=}: {out}")
    body = (
        f"This is a PR opened by AI tool [SWE Agent](https://github.com/SWE-agent/SWE-agent/) "
        f"to close [#{issue.number}]({issue_url}) ({issue.title}).\n\nCloses #{issue.number}."
    )
    body += "\n\n" + format_trajectory_markdown(trajectory, char_limit=60_000)
    api = GhApi(token=token)
    if not _dry_run:
        args = dict(
            owner=owner,
            repo=repo,
            title=f"SWE-agent[bot] PR to fix: {issue.title}",
            head=head,
            base="main",
            body=body,
            draft=True,
        )
        logger.debug(f"Creating PR with args: {args}")
        pr_info = api.pulls.create(**args)  # type: ignore
        logger.info(
            f"🎉 PR created as a draft at {pr_info.html_url}. Please review it carefully, push "
            "any required changes onto the branch and then click "
            "'Ready for Review' to bring it to the attention of the maintainers.",
        )


class OpenPRConfig(BaseModel):
    # Option to be used with open_pr: Skip action if there are already commits claiming
    # to fix the issue. Please only set this to False if you are sure the commits are
    # not fixes or if this is your own repository!
    skip_if_commits_reference_issue: bool = True


class OpenPRHook(RunHook):
    """This hook opens a PR if the issue is solved and the user has enabled the option."""

    def __init__(self, config: OpenPRConfig):
        self.logger = get_logger("swea-open_pr", emoji="⚡️")
        self._config = config

    def on_init(self, *, run):
        self._env = run.env
        self._token: str = os.getenv("GITHUB_TOKEN", "")
        self._problem_statement = run.problem_statement

    def on_instance_completed(self, result: AgentRunResult):
        if self.should_open_pr(result):
            open_pr(
                logger=self.logger,
                token=self._token,
                env=self._env,
                github_url=self._problem_statement.github_url,
                trajectory=result.trajectory,
            )

    def should_open_pr(self, result: AgentRunResult) -> bool:
        """Does opening a PR make sense?"""
        if not result.info.get("submission"):
            self.logger.info("Not opening PR because no submission was made.")
            return False
        if result.info.get("exit_status") != "submitted":
            self.logger.info(
                "Not opening PR because exit status was %s and not submitted.", result.info.get("exit_status")
            )
            return False
        try:
            issue = _get_gh_issue_data(self._problem_statement.github_url, token=self._token)
        except InvalidGithubURL:
            self.logger.info("Currently only GitHub is supported to open PRs to. Skipping PR creation.")
            return False
        if issue.state != "open":
            self.logger.info(f"Issue is not open (state={issue.state}. Skipping PR creation.")
            return False
        if issue.assignee:
            self.logger.info("Issue is already assigned. Skipping PR creation. Be nice :)")
            return False
        if issue.locked:
            self.logger.info("Issue is locked. Skipping PR creation.")
            return False
        org, repo, issue_number = _parse_gh_issue_url(self._problem_statement.github_url)
        associated_commits = _get_associated_commit_urls(org, repo, issue_number, token=self._token)
        if associated_commits:
            commit_url_strs = ", ".join(associated_commits)
            if self._config.skip_if_commits_reference_issue:
                self.logger.info(f"Issue already has associated commits (see {commit_url_strs}). Skipping PR creation.")
                return False
            else:
                self.logger.warning(
                    "Proceeding with PR creation even though there are already commits "
                    f"({commit_url_strs}) associated with the issue. Please only do this for your own repositories "
                    "or after verifying that the existing commits do not fix the issue.",
                )
        return True


def _remove_triple_backticks(text: str) -> str:
    return "\n".join(line.removeprefix("```") for line in text.splitlines())


def format_trajectory_markdown(trajectory: list[dict[str, str]], char_limit: int | None = None):
    """Format a trajectory as a markdown string for use in gh PR description.

    Args:
        char_limit: If not None, truncate the trajectory to this many characters.
    """
    prefix = [
        "<details>",
        "<summary>Thought process ('trajectory') of SWE-agent (click to expand)</summary>",
        "",
        "",
    ]
    prefix_text = "\n".join(prefix)
    suffix = [
        "",
        "</details>",
    ]
    suffix_text = "\n".join(suffix)

    steps = []
    current_length = len(prefix_text) + len(suffix_text)

    for i, step in enumerate(trajectory):
        step_strs = [
            f"**🧑‍🚒 Response ({i})**: ",
            f"{step['response'].strip()}",
            f"**👀‍ Observation ({i})**:",
            "```",
            f"{_remove_triple_backticks(step['observation']).strip()}",
            "```",
        ]
        step_text = "\n".join(step_strs)

        # Calculate separator length (only needed for steps after the first one)
        separator_length = 0
        if steps:
            separator_length = len("\n\n---\n\n")

        # Check if adding this step would exceed the character limit
        if char_limit is not None and current_length + separator_length + len(step_text) > char_limit:
            if i > 0:
                steps.append("\n\n... (truncated due to length limit)")
            break

        if steps:
            steps.append("\n\n---\n\n")
            current_length += separator_length

        steps.append(step_text)
        current_length += len(step_text)

    return prefix_text + "".join(steps) + suffix_text
