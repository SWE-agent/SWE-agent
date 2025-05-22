import json
import os
from pathlib import Path

import pytest

from sweagent import TOOLS_DIR
from tests.utils import make_python_tool_importable

DEFAULT_TOOLS_DIR = TOOLS_DIR / "windowed"
DEFAULT_TOOLS_BIN = DEFAULT_TOOLS_DIR / "bin"

make_python_tool_importable(DEFAULT_TOOLS_DIR / "lib/windowed_file.py", "windowed_file")
import windowed_file  # type: ignore
from windowed_file import TextNotFound, WindowedFile  # type: ignore


def test_env_file_override(with_tmp_env_file):
    assert Path(os.getenv("SWE_AGENT_ENV_FILE")).name == ".swe-agent-env"  # type: ignore


def create_test_file_with_content(tmp_env_file: Path, content: str) -> WindowedFile:
    test_path = tmp_env_file.parent.joinpath("test.py")
    registry = {
        "CURRENT_FILE": str(test_path),
        "FIRST_LINE": "0",
        "WINDOW": "10",
    }
    tmp_env_file.write_text(json.dumps(registry))
    test_path.write_text(content)
    wf = WindowedFile(exit_on_exception=False)
    wf.offset_multiplier = 1 / 4
    return wf


@pytest.fixture
def windowed_file(with_tmp_env_file) -> WindowedFile:
    content = "\n".join(map(str, range(100)))
    return create_test_file_with_content(with_tmp_env_file, content)


def test_windowed_file(windowed_file):
    wfile = windowed_file
    assert wfile.first_line == 0
    wfile.first_line = 10
    assert wfile.first_line == 10
    assert wfile.window == 10
    assert wfile.n_lines == 100
    a, b = wfile.line_range
    assert b - a == wfile.window - 1
    assert wfile.line_range == (10, 19)
    wfile.print_window()
    wfile.replace_in_window("10", "Hello, world!")
    assert wfile.n_lines == 100
    assert wfile.line_range == (7, 16)
    wfile.first_line = 50
    wfile.print_window()
    wfile.replace_in_window("50", "Hello, world!")
    wfile.print_window()
    # Line 50 is now the 2nd line of the new window
    assert wfile.line_range == (47, 56)
    with pytest.raises(TextNotFound):
        wfile.replace_in_window("asdf", "Hello, world!")


def test_windowed_file_goto(windowed_file):
    wfile = windowed_file
    assert wfile.first_line == 0
    wfile.first_line = 10
    wfile.goto(0, mode="top")
    assert wfile.line_range[0] == 0
    wfile.goto(50, mode="top")
    # first line is 50 - 10//4 = 47
    assert wfile.line_range[0] == 47


def test_windowed_file_scroll(windowed_file):
    wfile = windowed_file
    assert wfile.first_line == 0
    wfile.first_line = 10
    wfile.scroll(10)
    assert wfile.first_line == 20
    wfile.scroll(-10)
    assert wfile.first_line == 10
    wfile.scroll(-100)
    # Can't go lower than the middle of the lowest window
    assert wfile.first_line == 0


# def test_goto_command(windowed_file):
#     wfile = windowed_file
#     assert wfile.current_line == 10
#     assert (DEFAULT_TOOLS_BIN / "goto").exists()

#     # Use sys.executable to get the correct Python interpreter
#     import sys
#     cmd = f"{sys.executable} {DEFAULT_TOOLS_BIN}/goto 50"
#     print(
#         subprocess.check_output(
#             cmd,
#             shell=True,
#             universal_newlines=True,
#             stderr=subprocess.STDOUT,
#             env=os.environ.copy(),  # Ensure we pass the current environment
#         )
#     )
#     assert wfile.current_line == 50


_DEFAULT_WINDOW_OUTPUT = """[File: {path} (100 lines total)]
(10 more lines above)
11:10
12:11
13:12
14:13
15:14
16:15
17:16
18:17
19:18
20:19
(80 more lines below)
"""


def test_print_window(windowed_file, capsys):
    wfile = windowed_file
    wfile.first_line = 10
    wfile.print_window()
    captured = capsys.readouterr()
    print(captured.out)
    expected = _DEFAULT_WINDOW_OUTPUT.format(path=wfile.path.resolve())
    assert captured.out == expected


_DEFAULT_WINDOW_OUTPUT_NEW_FILE = """[File: {path} (1 lines total)]
1:
"""


def test_print_window_new_file(with_tmp_env_file, capsys):
    wfile = create_test_file_with_content(with_tmp_env_file, "\n")
    assert wfile.n_lines == 1
    assert wfile.line_range == (0, 0)
    wfile.print_window()
    captured = capsys.readouterr()
    print(captured.out)
    expected = _DEFAULT_WINDOW_OUTPUT_NEW_FILE.format(path=wfile.path.resolve())
    assert captured.out == expected
