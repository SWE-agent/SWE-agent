import asyncio
import os
from pathlib import Path
from typing import Any, Literal, Protocol

from git import InvalidGitRepositoryError
from git import Repo as GitRepo
from pydantic import BaseModel, ConfigDict, Field
from swerex.deployment.abstract import AbstractDeployment
from swerex.runtime.abstract import Command, UploadRequest
from typing_extensions import Self

from sweagent.utils.github import _parse_gh_repo_url
from sweagent.utils.gitlab import _is_gitlab_repo_url, _parse_gitlab_repo_url
from sweagent.utils.log import get_logger

logger = get_logger("swea-config", emoji="🔧")


class Repo(Protocol):
    """Protocol for repository configurations."""

    base_commit: str
    repo_name: str

    def copy(self, deployment: AbstractDeployment): ...

    def get_reset_commands(self) -> list[str]: ...


def _get_git_reset_commands(base_commit: str) -> list[str]:
    return [
        "git status",
        "git restore .",
        f"git reset --hard {base_commit}",
        "git clean -fdq",
    ]


class PreExistingRepoConfig(BaseModel):
    """Use this to specify a repository that already exists on the deployment.
    This is important because we need to cd to the repo before running the agent.

    Note: The repository must be at the root of the deployment.
    """

    repo_name: str
    """The repo name (the repository must be located at the root of the deployment)."""
    base_commit: str = Field(default="HEAD")
    """The commit to reset the repository to. The default is HEAD,
    i.e., the latest commit. You can also set this to a branch name (e.g., `dev`),
    a tag (e.g., `v0.1.0`), or a commit hash (e.g., `a4464baca1f`).
    SWE-agent will then start from this commit when trying to solve the problem.
    """

    type: Literal["preexisting"] = "preexisting"
    """Discriminator for (de)serialization/CLI. Do not change."""

    model_config = ConfigDict(extra="forbid")

    def copy(self, deployment: AbstractDeployment):
        """Does nothing."""
        pass

    def get_reset_commands(self) -> list[str]:
        """Issued after the copy operation or when the environment is reset."""
        return _get_git_reset_commands(self.base_commit)


class LocalRepoConfig(BaseModel):
    path: Path
    base_commit: str = Field(default="HEAD")
    """The commit to reset the repository to. The default is HEAD,
    i.e., the latest commit. You can also set this to a branch name (e.g., `dev`),
    a tag (e.g., `v0.1.0`), or a commit hash (e.g., `a4464baca1f`).
    SWE-agent will then start from this commit when trying to solve the problem.
    """

    type: Literal["local"] = "local"
    """Discriminator for (de)serialization/CLI. Do not change."""

    model_config = ConfigDict(extra="forbid")

    @property
    def repo_name(self) -> str:
        """Set automatically based on the repository name. Cannot be set."""
        return Path(self.path).resolve().name.replace(" ", "-").replace("'", "")

    # Let's not make this a model validator, because it leads to cryptic errors.
    # Let's just check during copy instead.
    def check_valid_repo(self) -> Self:
        try:
            repo = GitRepo(self.path, search_parent_directories=True)
        except InvalidGitRepositoryError as e:
            msg = f"Could not find git repository at {self.path=}."
            raise ValueError(msg) from e
        if repo.is_dirty() and "PYTEST_CURRENT_TEST" not in os.environ:
            msg = f"Local git repository {self.path} is dirty. Please commit or stash changes."
            raise ValueError(msg)
        return self

    def copy(self, deployment: AbstractDeployment):
        self.check_valid_repo()
        asyncio.run(
            deployment.runtime.upload(UploadRequest(source_path=str(self.path), target_path=f"/{self.repo_name}"))
        )
        r = asyncio.run(deployment.runtime.execute(Command(command=f"chown -R root:root {self.repo_name}", shell=True)))
        if r.exit_code != 0:
            msg = f"Failed to change permissions on copied repository (exit code: {r.exit_code}, stdout: {r.stdout}, stderr: {r.stderr})"
            raise RuntimeError(msg)

    def get_reset_commands(self) -> list[str]:
        """Issued after the copy operation or when the environment is reset."""
        return _get_git_reset_commands(self.base_commit)


class GithubRepoConfig(BaseModel):
    github_url: str

    base_commit: str = Field(default="HEAD")
    """The commit to reset the repository to. The default is HEAD,
    i.e., the latest commit. You can also set this to a branch name (e.g., `dev`),
    a tag (e.g., `v0.1.0`), or a commit hash (e.g., `a4464baca1f`).
    SWE-agent will then start from this commit when trying to solve the problem.
    """

    clone_timeout: float = 500
    """Timeout for git clone operation."""

    type: Literal["github"] = "github"
    """Discriminator for (de)serialization/CLI. Do not change."""

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, __context: Any) -> None:
        if self.github_url.count("/") == 1:
            self.github_url = f"https://github.com/{self.github_url}"

    @property
    def repo_name(self) -> str:
        org, repo = _parse_gh_repo_url(self.github_url)
        return f"{org}__{repo}"

    def _get_url_with_token(self, token: str) -> str:
        """Prepend github token to URL"""
        if not token:
            return self.github_url
        if "@" in self.github_url:
            logger.warning("Cannot prepend token to URL. '@' found in URL")
            return self.github_url
        _, _, url_no_protocol = self.github_url.partition("://")
        return f"https://{token}@{url_no_protocol}"

    def copy(self, deployment: AbstractDeployment):
        """Clones the repository to the sandbox."""
        base_commit = self.base_commit
        github_token = os.getenv("GITHUB_TOKEN", "")
        url = self._get_url_with_token(github_token)
        asyncio.run(
            deployment.runtime.execute(
                Command(
                    command=" && ".join(
                        (
                            f"mkdir {self.repo_name}",
                            f"cd {self.repo_name}",
                            "git init",
                            f"git remote add origin {url}",
                            f"git fetch --depth 1 origin {base_commit}",
                            "git checkout FETCH_HEAD",
                            "cd ..",
                        )
                    ),
                    timeout=self.clone_timeout,
                    shell=True,
                    check=True,
                )
            ),
        )

    def get_reset_commands(self) -> list[str]:
        """Issued after the copy operation or when the environment is reset."""
        return _get_git_reset_commands(self.base_commit)


class GitlabRepoConfig(BaseModel):
    gitlab_url: str

    base_commit: str = Field(default="HEAD")
    """The commit to reset the repository to. The default is HEAD,
    i.e., the latest commit. You can also set this to a branch name (e.g., `dev`),
    a tag (e.g., `v0.1.0`), or a commit hash (e.g., `a4464baca1f`).
    SWE-agent will then start from this commit when trying to solve the problem.
    """

    clone_timeout: float = 500
    """Timeout for git clone operation."""

    type: Literal["gitlab"] = "gitlab"
    """Discriminator for (de)serialization/CLI. Do not change."""

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, __context: Any) -> None:
        # Handle shorthand notation (owner/repo) by assuming gitlab.com
        # Only convert to HTTPS if it's not an SSH URL (git@...)
        if (
            self.gitlab_url.count("/") == 1
            and not self.gitlab_url.startswith("http")
            and not self.gitlab_url.startswith("git@")
        ):
            self.gitlab_url = f"https://gitlab.com/{self.gitlab_url}"

    @property
    def repo_name(self) -> str:
        # Parse the GitLab URL to get the instance, owner, and repo
        gitlab_instance, org, repo = _parse_gitlab_repo_url(self.gitlab_url)
        # Use a sanitized version of the instance name in the repo name to avoid conflicts
        # with repositories from different GitLab instances
        instance_name = gitlab_instance.replace("https://", "").replace("http://", "").replace(".", "_")
        return f"{instance_name}__{org}__{repo}"

    def _get_url_with_token(self, token: str, token_type: str = "project") -> str:
        """Prepend gitlab token to URL based on token type

        Args:
            token: GitLab token
            token_type: Type of token ('oauth', 'private', or 'personal')

        Returns:
            URL with token included for authentication
        """
        if not token:
            return self.gitlab_url
        if "@" in self.gitlab_url:
            logger.warning("Cannot prepend token to URL. '@' found in URL")
            return self.gitlab_url

        # Get the URL without protocol
        _, _, url_no_protocol = self.gitlab_url.partition("://")

        # For OAuth2 tokens, include them in the URL
        # For private tokens and personal access tokens, they'll be used in headers
        # but we still need to return a URL that git can use
        if token_type.lower() in ["private", "personal"]:
            # For git operations with private tokens, we use the token as username and 'x-oauth-basic' as password
            # This is a common pattern that works with most Git servers
            return f"https://{token}:x-oauth-basic@{url_no_protocol}"
        else:  # Default to OAuth2
            return f"https://oauth2:{token}@{url_no_protocol}"

    def copy(self, deployment: AbstractDeployment):
        """Clones the repository to the sandbox."""
        base_commit = self.base_commit
        gitlab_token = os.getenv("GITLAB_TOKEN", "")
        # Determine token type - default to OAuth2 but check for GITLAB_TOKEN_TYPE env var
        token_type = os.getenv("GITLAB_TOKEN_TYPE", "oauth").lower()
        url = self._get_url_with_token(gitlab_token, token_type)

        # For private/personal tokens, we may need to set git config
        git_config_commands = []
        if token_type in ["private", "personal"] and gitlab_token:
            # For private tokens, configure git to use custom headers
            git_config_commands = [
                f"git config --global http.extraHeader 'PRIVATE-TOKEN: {gitlab_token}'",
            ]

        asyncio.run(
            deployment.runtime.execute(
                Command(
                    command=" && ".join(
                        (
                            f"mkdir {self.repo_name}",
                            f"cd {self.repo_name}",
                            "git init",
                            *git_config_commands,
                            f"git remote add origin {url}",
                            f"git fetch --depth 1 origin {base_commit}",
                            "git checkout FETCH_HEAD",
                            # Clean up any temporary git config we set
                            "git config --global --unset http.extraHeader || true",
                            "cd ..",
                        )
                    ),
                    timeout=self.clone_timeout,
                    shell=True,
                    check=True,
                )
            ),
        )

    def get_reset_commands(self) -> list[str]:
        """Issued after the copy operation or when the environment is reset."""
        return _get_git_reset_commands(self.base_commit)


RepoConfig = LocalRepoConfig | GithubRepoConfig | GitlabRepoConfig | PreExistingRepoConfig


def repo_from_simplified_input(
    *, input: str, base_commit: str = "HEAD", type: Literal["local", "github", "gitlab", "preexisting", "auto"] = "auto"
) -> RepoConfig:
    """Get repo config from a simplified input.

    Args:
        input: Local path, GitHub URL, or GitLab URL
        type: The type of repo. Set to "auto" to automatically detect the type
            (does not work for preexisting repos).
    """
    if type == "local":
        return LocalRepoConfig(path=Path(input), base_commit=base_commit)
    if type == "github":
        return GithubRepoConfig(github_url=input, base_commit=base_commit)
    if type == "gitlab":
        return GitlabRepoConfig(gitlab_url=input, base_commit=base_commit)
    if type == "preexisting":
        return PreExistingRepoConfig(repo_name=input, base_commit=base_commit)
    if type == "auto":
        if input.startswith("https://github.com/") or input.startswith("git@github.com"):
            return GithubRepoConfig(github_url=input, base_commit=base_commit)
        elif (
            input.startswith("https://gitlab.com/") or input.startswith("git@gitlab.com") or _is_gitlab_repo_url(input)
        ):
            return GitlabRepoConfig(gitlab_url=input, base_commit=base_commit)
        else:
            return LocalRepoConfig(path=Path(input), base_commit=base_commit)
    msg = f"Unknown repo type: {type}"
    raise ValueError(msg)
