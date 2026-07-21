from sweagent import TOOLS_DIR
from tests.utils import make_python_tool_importable

make_python_tool_importable(TOOLS_DIR / "windowed_edit_replace" / "bin" / "edit", "windowed_edit_replace_edit")
import windowed_edit_replace_edit  # type: ignore  # noqa: E402


def test_replace_all_argument_parsing():
    """Regression test: `replace_all` used `type=bool`, and `bool("False")` is
    `True`, so an explicit `replace-all=false` replaced every occurrence instead
    of only the one in the displayed window."""
    parse = windowed_edit_replace_edit.get_parser().parse_args
    # Omitted -> default False (replace only within the window).
    assert parse(["s", "r"]).replace_all is False
    # Truthy spellings -> True.
    assert parse(["s", "r", "True"]).replace_all is True
    assert parse(["s", "r", "true"]).replace_all is True
    assert parse(["s", "r", "1"]).replace_all is True
    # Falsy spellings -> False (previously all parsed as True).
    assert parse(["s", "r", "False"]).replace_all is False
    assert parse(["s", "r", "false"]).replace_all is False
    assert parse(["s", "r", "0"]).replace_all is False
