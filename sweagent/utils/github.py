import json
import re
import urllib.error
import urllib.request

from ghapi.all import GhApi

from sweagent.utils.log import get_logger

_logger = get_logger("swea-github", emoji="🔧")

_repo_privacy_cache: dict[str, bool] = {}

GITHUB_ISSUE_URL_PATTERN = re.compile(r"github\.com\/(.*?)\/(.*?)\/issues\/(\d+)")


class InvalidGithubURL(Exception):
    """Raised when a github URL is invalid"""


GITHUB_REPO_URL_PATTERN = re.compile(r".*[/@]?github\.com\/([^/]+)\/([^/]+)")


def _is_github_repo_url(data_path: str) -> bool:
    """Check if data_path is an URL pointing to a github repository.
    Paths to issues or PRs will also match this pattern.
    """
    return GITHUB_REPO_URL_PATTERN.search(data_path) is not None


def _is_github_issue_url(data_path: str) -> bool:
    """Check if data_path is an URL pointing to a github issue"""
    return GITHUB_ISSUE_URL_PATTERN.search(data_path) is not None


def _get_commit(api: GhApi, owner: str, repo: str, ref: str | None = None):
    """Get commit object from github api

    Args:
        api (GhApi):
        owner (str): Repo owner, e.g., "SWE-agent"
        repo (str): Repo, e.g., "SWE-agent"
        ref (str, optional): Branch, tag or commit hash

    Returns:
        _type_: _description_
    """
    if ref:
        return api.repos.get_commit(owner, repo, ref)  # type: ignore
    return api.repos.list_commits(owner, repo)[0]  # type: ignore


def _parse_gh_issue_url(issue_url: str) -> tuple[str, str, str]:
    """
    Returns:
        owner: Repo owner
        repo: Repo name
        issue number: Issue number as str

    Raises:
        InvalidGithubURL: If the URL is not a valid github issue URL
    """
    match = GITHUB_ISSUE_URL_PATTERN.search(issue_url)
    if not match:
        msg = f"Invalid GitHub issue URL: {issue_url}"
        raise InvalidGithubURL(msg)
    res = match.groups()
    assert len(res) == 3
    return tuple(res)  # type: ignore


def _parse_gh_repo_url(repo_url: str) -> tuple[str, str]:
    """
    Returns:
        owner: Repo owner/org
        repo: Repo name

    Raises:
        InvalidGithubURL: If the URL is not a valid github repo URL
    """
    match = GITHUB_REPO_URL_PATTERN.search(repo_url)
    if not match:
        msg = f"Invalid GitHub issue URL: {repo_url}"
        raise InvalidGithubURL(msg)
    res = match.groups()
    assert len(res) == 2
    return tuple(res)  # type: ignore


def _get_gh_issue_data(issue_url: str, *, token: str = ""):
    """Returns github issue data in the form of a dictionary.
    See https://docs.github.com/en/rest/issues/issues?apiVersion=2022-11-28#get-an-issue
    for return format
    """
    owner, repo, issue_number = _parse_gh_issue_url(issue_url)
    api = GhApi(token=token)
    return api.issues.get(owner, repo, issue_number)  # type: ignore


def _get_problem_statement_from_github_issue(
    owner: str, repo: str, issue_number: str, *, token: str | None = ""
) -> str:
    """Return problem statement from github issue"""
    api = GhApi(token=token)
    issue = api.issues.get(owner, repo, issue_number)  # type: ignore
    title = issue.title if issue.title else ""
    body = issue.body if issue.body else ""
    return f"{title}\n{body}\n"


def _get_associated_commit_urls(org: str, repo: str, issue_number: str, *, token: str = "") -> list[str]:
    """Return the URLs of commits that would close an issue."""
    api = GhApi(token=token)
    # Strangely the "pull_request" field of api.issues.get is often not set
    # so we have to go through the events to check if there's a commit
    events = api.issues.list_events(org, repo, issue_number)  # type: ignore
    commit_urls = []
    for event in events:
        if event.event != "referenced":
            continue
        if not event.commit_id:
            continue
        commit = api.repos.get_commit(org, repo, event.commit_id)  # type: ignore
        message = commit.commit.message
        if f"fixes #{issue_number}" in message.lower() or f"closes #{issue_number}" in message.lower():
            commit_urls.append(commit.html_url)
    return commit_urls


def _is_repo_private(owner_repo: str, token: str) -> bool:
    """Check if a GitHub repository is private via the GitHub API.

    Returns True if the repo is private or if a 404 is returned (GitHub returns
    404 for private repos when the token lacks access).  Any other HTTP or
    network error is raised so callers can handle it explicitly.
    """
    if owner_repo in _repo_privacy_cache:
        return _repo_privacy_cache[owner_repo]
    url = f"https://api.github.com/repos/{owner_repo}"
    headers = {"User-Agent": "sweagent"}
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            private = data.get("private", False)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            _logger.warning("Repo '%s' returned 404 — assuming private", owner_repo)
            private = True
        else:
            raise
    _repo_privacy_cache[owner_repo] = private
    return private
