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
    _get_gh_issue_data,
)
from sweagent.utils.jira import (
    InvalidJiraURL,
    _get_jira_issue_data,
    _is_jira_issue_url,
)
from sweagent.utils.log import get_logger


def open_pr(*, logger, token, env: SWEEnv, issue_url, trajectory, _dry_run: bool = False) -> None:
    """Create PR to repository on GitHub, regardless of issue source."""

    logger.info(f"GitHub URL: {env.repo.github_url}")  # Always using env.repo.github_url
    logger.info("Opening PR")

    try:
        # Check if the issue is from GitHub or Jira
        if "github.com" in issue_url:
            issue = _get_gh_issue_data(issue_url, token=token)
            issue_id = f"#{issue.number}"
            issue_title = issue.title
        elif _is_jira_issue_url(issue_url):
            issue = _get_jira_issue_data(issue_url)
            issue_id = issue["key"]
            issue_title = issue["summary"]
        else:
            raise ValueError("Unsupported issue URL")

        # Always create PR on GitHub
        branch_name = f"swe-agent-fix-{issue_id.replace('#', '')}-" + str(random.random())[2:10]
        commit_msg = [
            shlex.quote(f"Fix: {issue_title}"),
            shlex.quote(f"Closes {issue_id}"),
        ]
        pr_body = (
            f"This is a PR opened by AI tool [SWE Agent](https://github.com/SWE-agent/SWE-agent/) "
            f"to address issue [{issue_id}]({issue_url}) ({issue_title})."
        )

    except (InvalidGithubURL, InvalidJiraURL) as e:
        raise ValueError("Data path must be a valid issue URL if open_pr is set to True.") from e

    # Git setup and commit process
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
    out = env.communicate(
        input=f"git commit -m {commit_msg[0]} -m {commit_msg[1]} {dry_run_flag}",
        error_msg="Failed to commit changes",
        timeout=10,
        check="raise",
    )
    logger.debug(f"Committed changes: {out}")

    # Always push to the repository from env.repo.github_url
    owner, repo = env.repo.github_url.rstrip("/").split("/")[-2:]  # Extract repo owner and name from URL
    head = branch_name
    remote = "origin"

    dry_run_prefix = "echo " if _dry_run else ""
    out = env.communicate(
        input=f"{dry_run_prefix} git push {remote} {branch_name}",
        error_msg=("Failed to push branch to remote. Please check your token and permissions. "),
        timeout=10,
    )
    logger.debug(f"Pushed commit to {remote=} {branch_name=}: {out}")

    pr_body += "\n\n" + format_trajectory_markdown(trajectory)
    api = GhApi(token=token)

    if not _dry_run:
        args = dict(
            owner=owner,
            repo=repo,
            title=f"SWE-agent[bot] PR to fix: {issue_title}",
            head=head,
            base="main",
            body=pr_body,
            draft=True,
        )
        logger.debug(f"Creating PR with args: {args}")
        pr_info = api.pulls.create(**args)  # type: ignore
        logger.info(f"🎉 PR created as a draft at {pr_info.html_url}. Please review it carefully.")


class OpenPRConfig(BaseModel):
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
            issue_url = (
                self._problem_statement.github_url
                if hasattr(self._problem_statement, "github_url")
                else self._problem_statement.jira_url
            )
            open_pr(
                logger=self.logger,
                token=self._token,
                env=self._env,
                issue_url=issue_url,
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

        issue_url = (
            self._problem_statement.github_url
            if hasattr(self._problem_statement, "github_url")
            else self._problem_statement.jira_url
        )

        try:
            issue = (
                _get_gh_issue_data(issue_url, token=self._token)
                if "github.com" in issue_url
                else _get_jira_issue_data(issue_url)
            )
            if "github.com" in issue_url and issue["state"] != "open":
                self.logger.info(f"Issue is not open (state={issue['state']}). Skipping PR creation.")
                return False
        except (InvalidGithubURL, InvalidJiraURL):
            self.logger.info("Invalid issue URL. Skipping PR creation.")
            return False

        return True


def _remove_triple_backticks(text: str) -> str:
    return "\n".join(line.removeprefix("```") for line in text.splitlines())


def format_trajectory_markdown(trajectory: list[dict[str, str]]):
    """Format a trajectory as a markdown string for use in gh PR description."""
    prefix = [
        "<details>",
        "<summary>Thought process ('trajectory') of SWE-agent (click to expand)</summary>",
        "",
        "",
    ]
    steps = []
    for i, step in enumerate(trajectory):
        step_strs = [
            f"**🧑‍🚒 Response ({i})**: ",
            f"{step['response'].strip()}",
            f"**👀‍ Observation ({i})**:",
            "```",
            f"{_remove_triple_backticks(step['observation']).strip()}",
            "```",
        ]
        steps.append("\n".join(step_strs))
    suffix = ["", "</details>"]
    return "\n".join(prefix) + "\n\n---\n\n".join(steps) + "\n".join(suffix)
