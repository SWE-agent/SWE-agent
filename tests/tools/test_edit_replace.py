import pytest

from sweagent import TOOLS_DIR
from tests.utils import make_python_tool_importable

EDIT_BIN = TOOLS_DIR / "windowed_edit_replace" / "bin" / "edit"
make_python_tool_importable(EDIT_BIN, "windowed_edit")
import windowed_edit  # type: ignore


@pytest.mark.parametrize(
    ("val", "expected"),
    [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("t", True),
        ("y", True),
        ("false", False),
        ("False", False),
        ("0", False),
        ("no", False),
        ("f", False),
        ("n", False),
        ("", False),
        (True, True),
        (False, False),
    ],
)
def test_str2bool_valid(val, expected):
    assert windowed_edit._str2bool(val) is expected


def test_str2bool_invalid():
    with pytest.raises(windowed_edit.argparse.ArgumentTypeError):
        windowed_edit._str2bool("invalid_bool")


@pytest.mark.parametrize(
    ("args", "expected_replace_all"),
    [
        (["foo", "bar"], False),
        (["foo", "bar", "true"], True),
        (["foo", "bar", "True"], True),
        (["foo", "bar", "1"], True),
        (["foo", "bar", "yes"], True),
        (["foo", "bar", "false"], False),
        (["foo", "bar", "False"], False),
        (["foo", "bar", "0"], False),
        (["foo", "bar", "no"], False),
    ],
)
def test_edit_parser_replace_all(args, expected_replace_all):
    parser = windowed_edit.get_parser()
    parsed = parser.parse_args(args)
    assert parsed.search == "foo"
    assert parsed.replace == "bar"
    assert parsed.replace_all is expected_replace_all


def test_edit_parser_invalid_replace_all():
    parser = windowed_edit.get_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["foo", "bar", "not_a_bool"])
