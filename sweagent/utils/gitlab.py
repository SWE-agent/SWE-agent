import re
from typing import Any
from urllib.parse import urlparse

import requests

# Regular expressions for GitLab URLs - support any GitLab instance, not just gitlab.com
GITLAB_ISSUE_URL_PATTERN = re.compile(r"(.*?)\/([^/]+)\/([^/]+)\/\-\/issues\/(\d+)")
# Match both https://gitlab.com/user/repo and git@gitlab.com:user/repo.git formats
GITLAB_REPO_URL_PATTERN = re.compile(r"(?:(https?)://|git@)([^/:]+)(?::|/)([^/]+)/([^/\n]+?)(?:\.git)?$")
GITLAB_MR_URL_PATTERN = re.compile(r"(.*?)\/([^/]+)\/([^/]+)\/\-\/merge_requests\/(\d+)")


class InvalidGitlabURL(Exception):
    """Raised when a GitLab URL is invalid"""


def _is_gitlab_url(data_path: str) -> bool:
    """Check if data_path is an URL pointing to a GitLab instance"""
    parsed_url = urlparse(data_path)
    # Check if hostname contains 'gitlab' or if it's a known GitLab URL pattern
    return (
        "gitlab" in parsed_url.netloc
        or GITLAB_REPO_URL_PATTERN.search(data_path) is not None
        or GITLAB_ISSUE_URL_PATTERN.search(data_path) is not None
        or GITLAB_MR_URL_PATTERN.search(data_path) is not None
    )


def _is_gitlab_repo_url(data_path: str) -> bool:
    """Check if data_path is an URL pointing to a GitLab repository.
    Paths to issues or MRs will also match this pattern.
    """
    return GITLAB_REPO_URL_PATTERN.search(data_path) is not None


def _is_gitlab_issue_url(data_path: str) -> bool:
    """Check if data_path is an URL pointing to a GitLab issue"""
    return GITLAB_ISSUE_URL_PATTERN.search(data_path) is not None


def _is_gitlab_mr_url(data_path: str) -> bool:
    """Check if data_path is an URL pointing to a GitLab merge request"""
    return GITLAB_MR_URL_PATTERN.search(data_path) is not None


def _parse_gitlab_issue_url(issue_url: str) -> tuple[str, str, str, str]:
    """
    Returns:
        gitlab_instance: The GitLab instance URL (e.g., 'https://gitlab.com')
        owner: Repo owner/namespace
        repo: Repo name
        issue number: Issue number as str

    Raises:
        InvalidGitlabURL: If the URL is not a valid GitLab issue URL
    """
    match = GITLAB_ISSUE_URL_PATTERN.search(issue_url)
    if not match:
        msg = f"Invalid GitLab issue URL: {issue_url}"
        raise InvalidGitlabURL(msg)
    res = match.groups()
    assert len(res) == 4
    return tuple(res)  # type: ignore


def _parse_gitlab_repo_url(repo_url: str) -> tuple[str, str, str]:
    """
    Returns:
        gitlab_instance: The GitLab instance hostname (e.g., 'gitlab.com')
        owner: Repo owner/namespace
        repo: Repo name

    Raises:
        InvalidGitlabURL: If the URL is not a valid GitLab repo URL
    """
    match = GITLAB_REPO_URL_PATTERN.search(repo_url)
    if not match:
        msg = f"Invalid GitLab repo URL: {repo_url}"
        raise InvalidGitlabURL(msg)
    res = match.groups()
    assert len(res) == 4  # protocol, instance, owner, repo
    # Return instance, owner, repo (skip the protocol)
    return res[1], res[2], res[3]


def _get_gitlab_api_client(
    gitlab_instance: str, token: str | None = None, token_type: str = "project"
) -> dict[str, Any]:
    """Returns a dictionary with methods to interact with GitLab API

    Args:
        gitlab_instance: The GitLab instance URL or hostname (e.g., 'gitlab.com' or 'https://gitlab.com')
        token: Optional GitLab API token
        token_type: Type of token to use. Options:
            - 'oauth': OAuth2 token (default) - uses Bearer authentication
            - 'private': Private token - uses PRIVATE-TOKEN header
            - 'personal': Personal access token - uses PRIVATE-TOKEN header
            - 'project': Project token - uses PRIVATE-TOKEN header
            - 'group': Group token - uses PRIVATE-TOKEN header
    """
    headers = {}
    if token:
        if token_type.lower() in ["private", "personal", "project", "group"]:
            # Both private tokens and personal access tokens use the PRIVATE-TOKEN header
            headers["PRIVATE-TOKEN"] = token
        else:  # Default to OAuth2 Bearer token
            headers["Authorization"] = f"Bearer {token}"

    # Ensure we have a proper URL for the GitLab instance
    if not gitlab_instance.startswith("http"):
        gitlab_instance = f"https://{gitlab_instance}"

    # Remove trailing slash if present
    gitlab_instance = gitlab_instance.rstrip("/")

    # Simple API client implementation using requests
    # This could be replaced with python-gitlab library for more comprehensive support
    def make_request(method: str, endpoint: str, **kwargs):
        url = f"{gitlab_instance}/api/v4/{endpoint}"
        response = requests.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()

    return {
        "get": lambda endpoint, **kwargs: make_request("GET", endpoint, **kwargs),
        "post": lambda endpoint, **kwargs: make_request("POST", endpoint, **kwargs),
        "put": lambda endpoint, **kwargs: make_request("PUT", endpoint, **kwargs),
        "delete": lambda endpoint, **kwargs: make_request("DELETE", endpoint, **kwargs),
    }


def _get_project_id(
    gitlab_instance: str, owner: str, repo: str, token: str | None = None, token_type: str = "project"
) -> str:
    """Get the GitLab project ID for a repository

    Args:
        gitlab_instance: The GitLab instance URL or hostname
        owner: Repository owner/namespace
        repo: Repository name
        token: Optional GitLab API token
        token_type: Type of token ('oauth', 'private', or 'personal')
    """
    client = _get_gitlab_api_client(gitlab_instance, token, token_type)
    # URL encode the path
    path = f"{owner}/{repo}".replace("/", "%2F")
    project = client["get"](f"projects/{path}")
    return str(project["id"])


def _get_gitlab_issue_data(issue_url: str, *, token: str = "", token_type: str = "project") -> dict[str, Any]:
    """Returns GitLab issue data in the form of a dictionary.
    See https://docs.gitlab.com/ee/api/issues.html#get-issue
    for return format

    Args:
        issue_url: URL of the GitLab issue
        token: GitLab API token
        token_type: Type of token ('oauth', 'private', or 'personal')
    """
    gitlab_instance, owner, repo, issue_number = _parse_gitlab_issue_url(issue_url)
    client = _get_gitlab_api_client(gitlab_instance, token, token_type)
    project_id = _get_project_id(gitlab_instance, owner, repo, token, token_type)
    return client["get"](f"projects/{project_id}/issues/{issue_number}")


def _get_problem_statement_from_gitlab_issue(
    gitlab_instance: str,
    owner: str,
    repo: str,
    issue_number: str,
    *,
    token: str | None = None,
    token_type: str = "project",
) -> str:
    """Return problem statement from GitLab issue

    Args:
        gitlab_instance: The GitLab instance URL or hostname
        owner: Repository owner/namespace
        repo: Repository name
        issue_number: Issue number
        token: Optional GitLab API token
        token_type: Type of token ('oauth', 'private', or 'personal')
    """
    client = _get_gitlab_api_client(gitlab_instance, token, token_type)
    project_id = _get_project_id(gitlab_instance, owner, repo, token, token_type)
    issue = client["get"](f"projects/{project_id}/issues/{issue_number}")
    title = issue.get("title", "")
    description = issue.get("description", "")
    return f"{title}\n{description}\n"


def _get_associated_commit_urls(
    gitlab_instance: str, owner: str, repo: str, issue_number: str, *, token: str = "", token_type: str = "project"
) -> list[str]:
    """Return the URLs of commits that would close an issue.

    Args:
        gitlab_instance: The GitLab instance URL or hostname
        owner: Repository owner/namespace
        repo: Repository name
        issue_number: Issue number
        token: Optional GitLab API token
        token_type: Type of token ('oauth', 'private', or 'personal')
    """
    client = _get_gitlab_api_client(gitlab_instance, token, token_type)
    project_id = _get_project_id(gitlab_instance, owner, repo, token, token_type)

    # First check if there are any merge requests that mention the issue
    mrs = client["get"](f"projects/{project_id}/merge_requests", params={"search": f"#{issue_number}"})

    commit_urls = []
    for mr in mrs:
        # Check if this MR would close the issue
        if (
            f"fixes #{issue_number}" in mr.get("description", "").lower()
            or f"closes #{issue_number}" in mr.get("description", "").lower()
        ):
            # Get the commits for this MR
            mr_commits = client["get"](f"projects/{project_id}/merge_requests/{mr['iid']}/commits")
            for commit in mr_commits:
                commit_urls.append(commit["web_url"])

    return commit_urls


def create_merge_request(
    gitlab_instance: str,
    owner: str,
    repo: str,
    source_branch: str,
    target_branch: str,
    title: str,
    description: str,
    *,
    token: str = "",
    token_type: str = "project",
    draft: bool = True,
) -> dict[str, Any]:
    """Create a merge request in GitLab

    Args:
        gitlab_instance: The GitLab instance URL or hostname
        owner: Repository owner/namespace
        repo: Repository name
        source_branch: The source branch name
        target_branch: The target branch name (usually 'main' or 'master')
        title: The title of the merge request
        description: The description of the merge request
        token: GitLab API token
        token_type: Type of token ('oauth', 'private', or 'personal')
        draft: Whether to create the merge request as a draft

    Returns:
        The created merge request data
    """
    client = _get_gitlab_api_client(gitlab_instance, token, token_type)
    project_id = _get_project_id(gitlab_instance, owner, repo, token, token_type)

    # Create the merge request
    mr_data = {
        "source_branch": source_branch,
        "target_branch": target_branch,
        "title": title,
        "description": description,
    }

    # Set as draft if requested
    if draft:
        # In GitLab, prefixing the title with 'Draft: ' or 'WIP: ' makes it a draft MR
        if not mr_data["title"].startswith("Draft: ") and not mr_data["title"].startswith("WIP: "):
            mr_data["title"] = f"Draft: {mr_data['title']}"

    # Create the merge request
    return client["post"](f"projects/{project_id}/merge_requests", json=mr_data)
