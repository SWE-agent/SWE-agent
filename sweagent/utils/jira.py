import os
import re

from jira import JIRA

from sweagent.utils.config import load_environment_variables

# Load environment variables from config.py
load_environment_variables()

JIRA_ISSUE_URL_PATTERN = re.compile(r"https:\/\/(.*?)\.atlassian\.net\/browse\/(.*?)$")


class InvalidJiraURL(Exception):
    """Raised when a Jira URL is invalid"""


def _is_jira_issue_url(issue_url: str) -> bool:
    """Check if a given string is a Jira issue URL."""
    return JIRA_ISSUE_URL_PATTERN.search(issue_url) is not None


def _parse_jira_issue_url(issue_url: str) -> tuple[str, str]:
    """
    Extracts:
        - Jira instance (subdomain)
        - Issue key
    """
    match = JIRA_ISSUE_URL_PATTERN.search(issue_url)
    if not match:
        raise InvalidJiraURL(f"Invalid Jira issue URL: {issue_url}")
    return match.groups()


def _get_jira_issue_data(issue_url: str) -> dict:
    """Fetch Jira issue details from Jira API."""
    instance, issue_key = _parse_jira_issue_url(issue_url)

    # Get credentials from environment variables loaded by config.py
    jira_token = os.getenv("JIRA_TOKEN", "")
    jira_email = os.getenv("JIRA_EMAIL", "")

    if not jira_token or not jira_email:
        raise ValueError("JIRA_TOKEN or JIRA_EMAIL environment variables are not set.")

    # Connect to Jira
    jira = JIRA(options={"server": f"https://{instance}.atlassian.net"}, basic_auth=(jira_email, jira_token))
    issue = jira.issue(issue_key)

    return {
        "key": issue_key,
        "summary": issue.fields.summary,
        "description": issue.fields.description,
        "status": issue.fields.status.name,
        "assignee": issue.fields.assignee.displayName if issue.fields.assignee else None,
        "url": f"https://{instance}.atlassian.net/browse/{issue_key}",
    }


def _get_problem_statement_from_jira(issue_url: str) -> str:
    """Extract the problem statement from a Jira issue."""
    issue_data = _get_jira_issue_data(issue_url)
    return f"{issue_data['summary']}\n{issue_data['description']}\n"


def _get_associated_commit_urls(issue_url: str) -> list[str]:
    """Find commit URLs that reference the Jira issue."""
    issue_data = _get_jira_issue_data(issue_url)
    issue_key = issue_data["key"]

    # Assume we are scanning commits from a connected repo (this requires extra integration)
    commit_urls = []  # This should be populated from repo scanning logic

    return [commit for commit in commit_urls if issue_key in commit]
