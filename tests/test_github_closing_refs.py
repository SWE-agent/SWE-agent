import pytest

from sweagent.utils.github import _get_associated_commit_urls


@pytest.mark.parametrize(
    ("message", "closes_issue"),
    [
        ("fixes #12", True),
        ("Closes #12.", True),
        ("Subject\n\nFIXES #12\n", True),
        ("fixes #123", False),
        ("closes #120", False),
        ("prefixes #12", False),
        ("mentions #12", False),
    ],
)
def test_associated_commit_requires_exact_closing_reference(monkeypatch, message, closes_issue):
    from types import SimpleNamespace
    from unittest.mock import Mock

    api = Mock()
    api.issues.list_events.return_value = [SimpleNamespace(event="referenced", commit_id="abc")]
    api.repos.get_commit.return_value = SimpleNamespace(
        commit=SimpleNamespace(message=message), html_url="https://github.com/owner/repo/commit/abc"
    )
    monkeypatch.setattr("sweagent.utils.github.GhApi", lambda **kwargs: api)
    result = _get_associated_commit_urls("owner", "repo", "12")
    assert result == (["https://github.com/owner/repo/commit/abc"] if closes_issue else [])
