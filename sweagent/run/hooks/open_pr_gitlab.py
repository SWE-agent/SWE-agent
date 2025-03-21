import os
import random
import shlex
from urllib.parse import urlparse

from pydantic import BaseModel

from sweagent.environment.swe_env import SWEEnv
from sweagent.run.hooks.abstract import RunHook
from sweagent.types import AgentRunResult
from sweagent.utils.gitlab import (
    InvalidGitlabURL,
    _get_associated_commit_urls,
    _get_gitlab_issue_data,
    _is_gitlab_issue_url,
    _parse_gitlab_issue_url,
    create_merge_request,
)
from sweagent.utils.log import get_logger

# NOTE
# THE IMPLEMENTATION DETAILS HERE WILL CHANGE SOON!


# fixme: Bring back the ability to open the MR to a fork
def open_mr(
    *, logger, token, token_type: str = "project", env: SWEEnv, gitlab_url, trajectory, _dry_run: bool = False
) -> None:
    """Create Merge Request to GitLab repository

    Args:
        trajectory: Trajectory of actions taken by the agent
        token: GitLab API token
        token_type: Type of token ('oauth2', 'private', or 'personal').
                   - 'oauth2': OAuth 2.0 tokens (format varies)
                   - 'private'/'personal'/'project'/'group': Personal/Project/Group access tokens (start with 'glpat')
        env: SWE environment
        gitlab_url: GitLab issue URL
        _dry_run: Whether to actually push anything or just simulate it
    """

    issue_url = gitlab_url
    logger.info(f"Opening GitLab MR using {token_type} token type")
    try:
        issue = _get_gitlab_issue_data(issue_url, token=token, token_type=token_type)
    except InvalidGitlabURL as e:
        msg = "Data path must be a GitLab issue URL if open_mr is set to True."
        raise ValueError(msg) from e

    issue_number = issue.get("iid", "")
    issue_title = issue.get("title", "")

    branch_name = f"swe-agent-fix-#{issue_number}-" + str(random.random())[2:10]
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
        shlex.quote(f"Fix: {issue_title}"),
        shlex.quote(f"Closes #{issue_number}"),
    ]
    out = env.communicate(
        input=f"git commit -m {commit_msg[0]} -m {commit_msg[1]} {dry_run_flag}",
        error_msg="Failed to commit changes",
        timeout=10,
        check="raise",
    )
    logger.debug(f"Committed changes: {out}")

    gitlab_instance, owner, repo, _ = _parse_gitlab_issue_url(issue_url)
    # Default to origin remote
    remote = "origin"

    # Handle token for push URL if needed
    if token:
        # Ensure we have a proper URL for the GitLab instance
        if not gitlab_instance.startswith("http"):
            gitlab_instance = f"https://{gitlab_instance}"

        # Remove trailing slash if present
        gitlab_instance = gitlab_instance.rstrip("/")

        # Parse the URL to get the hostname
        parsed_url = urlparse(gitlab_instance)
        hostname = parsed_url.netloc

        # Set up git configuration based on token type
        if token_type.lower() in ["private", "personal", "project", "group"]:
            # For private/personal/project/group tokens (glpat*), set the PRIVATE-TOKEN header
            fork_url = f"https://oauth2:{token}@{hostname}/{owner}/{repo}.git"
            # Also configure git to use the PRIVATE-TOKEN header
            env.communicate(
                input=f"git config --global http.extraHeader 'PRIVATE-TOKEN: {token}'",
                error_msg="Failed to set git config for private token",
                timeout=10,
            )
        else:  # Default to OAuth2
            # For OAuth2 tokens, use the standard oauth2:token format
            fork_url = f"https://oauth2:{token}@{hostname}/{owner}/{repo}.git"

        env.communicate(
            input=f"git remote set-url origin {fork_url}",
            error_msg="Failed to update git remote",
            timeout=10,
        )

    # Push the branch
    dry_run_prefix = "echo " if _dry_run else ""
    out = env.communicate(
        input=f"{dry_run_prefix} git push {remote} {branch_name}",
        error_msg=("Failed to push branch to remote. Please check your token and permissions."),
        timeout=10,
    )

    # Clean up any git config we set for private tokens
    if token and token_type.lower() in ["private", "personal", "project", "group"]:
        env.communicate(
            input="git config --global --unset http.extraHeader || true",
            error_msg="Failed to clean up git config",
            timeout=10,
        )
    logger.debug(f"Pushed commit to {remote=} {branch_name=}: {out}")

    # Create the merge request description
    body = (
        f"This is a Merge Request opened by AI tool [SWE Agent](https://github.com/SWE-agent/SWE-agent/) "
        f"to close [#{issue_number}]({issue_url}) ({issue_title}).\n\nCloses #{issue_number}."
    )
    body += "\n\n" + format_trajectory_markdown(trajectory)

    # Create the merge request via the GitLab API
    if not _dry_run:
        try:
            mr_info = create_merge_request(
                gitlab_instance=gitlab_instance,
                owner=owner,
                repo=repo,
                source_branch=branch_name,
                target_branch="main",  # Default to main, could be configurable in the future
                title=f"SWE-agent[bot] MR to fix: {issue_title}",
                description=body,
                token=token,
                token_type=token_type,
                draft=True,
            )
            logger.info(
                f"🎉 Merge Request created as a draft at {mr_info.get('web_url')}. Please review it carefully, push "
                "any required changes onto the branch and then click "
                "'Mark as ready' to bring it to the attention of the maintainers.",
            )
        except Exception as e:
            logger.error(f"Failed to create GitLab merge request: {e}")


class OpenMRConfig(BaseModel):
    # Option to be used with open_mr: Skip action if there are already commits claiming
    # to fix the issue. Please only set this to False if you are sure the commits are
    # not fixes or if this is your own repository!
    skip_if_commits_reference_issue: bool = True
    # Default target branch for MRs (if not specified, defaults to 'main')
    target_branch: str = "main"


class OpenMRHook(RunHook):
    """This hook opens a GitLab Merge Request if the issue is solved and the user has enabled the option."""

    def __init__(self, config: OpenMRConfig):
        self.logger = get_logger("swea-open_mr", emoji="⚡️")
        self._config = config

    def on_init(self, *, run):
        self._env = run.env
        self._gitlab_token: str = os.getenv("GITLAB_TOKEN", "")
        self._gitlab_token_type: str = os.getenv("GITLAB_TOKEN_TYPE", "project").lower()
        self._problem_statement = run.problem_statement

    def on_instance_completed(self, result: AgentRunResult):
        if self.should_open_mr(result):
            # Get the GitLab issue URL from the problem statement
            if hasattr(self._problem_statement, "gitlab_url"):
                issue_url = self._problem_statement.gitlab_url
                open_mr(
                    logger=self.logger,
                    token=self._gitlab_token,
                    token_type=self._gitlab_token_type,
                    env=self._env,
                    gitlab_url=issue_url,
                    trajectory=result.trajectory,
                )
            else:
                # No GitLab issue URL found, can't open MR
                self.logger.warning("No GitLab issue URL found in problem statement, can't open MR")

    def should_open_mr(self, result: AgentRunResult) -> bool:
        """Does opening a Merge Request make sense?"""
        if not result.info.get("submission"):
            self.logger.info("Not opening MR because no submission was made.")
            return False
        if result.info.get("exit_status") != "submitted":
            self.logger.info(
                "Not opening MR because exit status was %s and not submitted.", result.info.get("exit_status")
            )
            return False

        # Get the GitLab issue URL from the problem statement
        if hasattr(self._problem_statement, "gitlab_url"):
            issue_url = self._problem_statement.gitlab_url
        else:
            # No GitLab issue URL found, can't open MR
            self.logger.warning("No GitLab issue URL found in problem statement, can't open MR")
            return False

        # Verify it's a valid GitLab issue URL
        if not _is_gitlab_issue_url(issue_url):
            self.logger.info("Invalid GitLab issue URL. Skipping MR creation.")
            return False

        try:
            # Get the GitLab issue data
            issue = _get_gitlab_issue_data(issue_url, token=self._gitlab_token, token_type=self._gitlab_token_type)
            # Debug log the issue data
            self.logger.debug(f"GitLab issue data: {issue}")

            # Check if the issue is open - GitLab uses 'opened' for open issues
            # Make sure to use the exact string comparison
            issue_state = issue.get("state", "")
            if issue_state != "opened":
                self.logger.info(f"GitLab issue is not open (state='{issue_state}'). Skipping MR creation.")
                return False
            if issue.get("assignee"):
                self.logger.info("GitLab issue is already assigned. Skipping MR creation. Be nice :)")
                return False
            if issue.get("discussion_locked"):
                self.logger.info("GitLab issue is locked. Skipping MR creation.")
                return False

            gitlab_instance, owner, repo, issue_number = _parse_gitlab_issue_url(issue_url)
            associated_commits = _get_associated_commit_urls(
                gitlab_instance,
                owner,
                repo,
                issue_number,
                token=self._gitlab_token,
                token_type=self._gitlab_token_type,
            )
            if associated_commits:
                commit_url_strs = ", ".join(associated_commits)
                if self._config.skip_if_commits_reference_issue:
                    self.logger.info(
                        f"GitLab issue already has associated commits (see {commit_url_strs}). Skipping MR creation."
                    )
                    return False
                else:
                    self.logger.warning(
                        "Proceeding with MR creation even though there are already commits "
                        f"({commit_url_strs}) associated with the issue. Please only do this for your own repositories "
                        "or after verifying that the existing commits do not fix the issue.",
                    )
            return True
        except InvalidGitlabURL:
            self.logger.info("Invalid GitLab URL.")
            return False


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
    suffix = [
        "",
        "</details>",
    ]
    return "\n".join(prefix) + "\n\n---\n\n".join(steps) + "\n".join(suffix)
