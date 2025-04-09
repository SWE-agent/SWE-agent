import hashlib
import os
import uuid
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from sweagent.utils.github import _get_problem_statement_from_github_issue, _parse_gh_issue_url
from sweagent.utils.gitlab import (
    _get_problem_statement_from_gitlab_issue,
    _is_gitlab_issue_url,
    _parse_gitlab_issue_url,
)
from sweagent.utils.log import get_logger

logger = get_logger("swea-config", emoji="🔧")


class ProblemStatement(Protocol):
    """A problem statement for a task."""

    id: str

    def get_problem_statement(self) -> str: ...

    def get_extra_fields(self) -> dict[str, Any]: ...


class EmptyProblemStatement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Literal["empty"] = "empty"
    """Discriminator for (de)serialization/CLI. Do not change."""

    model_config = ConfigDict(extra="forbid")

    def get_problem_statement(self) -> str:
        return ""

    def get_extra_fields(self) -> dict[str, Any]:
        return {}


class TextProblemStatement(BaseModel):
    text: str

    extra_fields: dict[str, Any] = Field(default_factory=dict)
    """Any additional data to be added to the instance.
    This data will be available when formatting prompt templates.
    """

    type: Literal["text"] = "text"
    """Discriminator for (de)serialization/CLI. Do not change."""

    id: str = None  # type: ignore

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, __context: Any) -> None:
        if self.id is None:
            logger.info("Setting problem statement id to hash of text")
            self.id = hashlib.sha256(self.text.encode()).hexdigest()[:6]

    def get_problem_statement(self) -> str:
        return self.text

    def get_extra_fields(self) -> dict[str, Any]:
        return self.extra_fields

    def __repr__(self) -> str:
        return f"TextProblemStatement(id={self.id}, text={self.text[:30]}...)"

    def __str__(self) -> str:
        return f"id={self.id}, text={self.text[:30]}..."


class FileProblemStatement(BaseModel):
    path: Path

    extra_fields: dict[str, Any] = Field(default_factory=dict)
    """Any additional data to be added to the instance.
    This data will be available when formatting prompt templates.
    """

    type: Literal["text_file"] = "text_file"
    """Discriminator for (de)serialization/CLI. Do not change."""

    id: str = None  # type: ignore

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, __context: Any) -> None:
        if self.id is None:
            logger.info("Setting problem statement id to hash of file contents (path: %s)", self.path)
            self.id = hashlib.sha256(self.get_problem_statement().encode()).hexdigest()[:6]

    def get_problem_statement(self) -> str:
        return self.path.read_text()

    def get_extra_fields(self) -> dict[str, Any]:
        return self.extra_fields


class GithubIssue(BaseModel):
    github_url: str

    extra_fields: dict[str, Any] = Field(default_factory=dict)
    """Any additional data to be added to the instance.
    This data will be available when formatting prompt templates.
    """

    type: Literal["github"] = "github"
    """Discriminator for (de)serialization/CLI. Do not change."""

    id: str = None  # type: ignore

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, __context: Any) -> None:
        if self.id is None:
            logger.info("Setting problem statement based on github issue url")
            owner, repo, issue_number = _parse_gh_issue_url(self.github_url)
            self.id = f"{owner}__{repo}-i{issue_number}"

    def get_problem_statement(self) -> str:
        owner, repo, issue_number = _parse_gh_issue_url(self.github_url)
        return _get_problem_statement_from_github_issue(owner, repo, issue_number, token=os.getenv("GITHUB_TOKEN"))

    def get_extra_fields(self) -> dict[str, Any]:
        return self.extra_fields


class GitlabIssue(BaseModel):
    gitlab_url: str

    extra_fields: dict[str, Any] = Field(default_factory=dict)
    """Any additional data to be added to the instance.
    This data will be available when formatting prompt templates.
    """

    type: Literal["gitlab"] = "gitlab"
    """Discriminator for (de)serialization/CLI. Do not change."""

    id: str = None  # type: ignore

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, __context: Any) -> None:
        if self.id is None:
            logger.info("Setting problem statement based on gitlab issue url")
            gitlab_instance, owner, repo, issue_number = _parse_gitlab_issue_url(self.gitlab_url)
            instance_name = gitlab_instance.replace("https://", "").replace("http://", "").replace(".", "_")
            self.id = f"{instance_name}__{owner}__{repo}-i{issue_number}"

    def get_problem_statement(self) -> str:
        gitlab_instance, owner, repo, issue_number = _parse_gitlab_issue_url(self.gitlab_url)
        token_type = os.getenv("GITLAB_TOKEN_TYPE", "project")
        return _get_problem_statement_from_gitlab_issue(
            gitlab_instance, owner, repo, issue_number, token=os.getenv("GITLAB_TOKEN"), token_type=token_type
        )

    def get_extra_fields(self) -> dict[str, Any]:
        return self.extra_fields


ProblemStatementConfig = TextProblemStatement | GithubIssue | GitlabIssue | EmptyProblemStatement | FileProblemStatement


def problem_statement_from_simplified_input(
    *, input: str, type: Literal["text", "text_file", "github_issue", "gitlab_issue", "issue"]
) -> ProblemStatementConfig:
    """Get a problem statement from an `input` string and a `type`.

    Args:
        input: Url/path/text
        type: The type of problem statement
    """
    if type == "text":
        return TextProblemStatement(text=input)
    elif type == "text_file":
        return FileProblemStatement(path=Path(input))
    elif type == "github_issue":
        return GithubIssue(github_url=input)
    elif type == "gitlab_issue":
        return GitlabIssue(gitlab_url=input)
    elif type == "issue":
        # Auto-detect if it's a GitHub or GitLab issue URL
        if _is_gitlab_issue_url(input):
            return GitlabIssue(gitlab_url=input)
        else:
            # Default to GitHub for backward compatibility
            return GithubIssue(github_url=input)
    else:
        msg = f"Unknown problem statement type: {type}"
        raise ValueError(msg)
