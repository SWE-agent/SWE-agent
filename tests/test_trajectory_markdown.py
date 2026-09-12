from sweagent.run.hooks.open_pr import format_trajectory_markdown


def test_format_trajectory_reserves_truncation_marker_budget():
    first = {"response": "first step", "observation": "first result"}
    second = {"response": "second step " * 100, "observation": "second result"}
    limit = len(format_trajectory_markdown([first]))
    formatted = format_trajectory_markdown([first, second], char_limit=limit)
    assert len(formatted) <= limit
    assert formatted.startswith("<details>")
    assert formatted.endswith("</details>")
    assert "truncated" in formatted


def test_format_trajectory_omits_wrapper_when_budget_cannot_hold_it():
    assert format_trajectory_markdown([], char_limit=0) == ""


def test_format_trajectory_preserves_output_at_exact_limit():
    trajectory = [{"response": "done", "observation": "ok"}]
    full = format_trajectory_markdown(trajectory)
    assert format_trajectory_markdown(trajectory, char_limit=len(full)) == full
