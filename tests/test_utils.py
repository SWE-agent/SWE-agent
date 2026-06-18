from __future__ import annotations

import sys
from pathlib import Path

import pytest

from sweagent import REPO_ROOT
from sweagent.utils.config import _convert_path_to_abspath, _convert_paths_to_abspath
from tests.utils import make_python_tool_importable


def test_convert_path_to_abspath():
    assert _convert_path_to_abspath("sadf") == REPO_ROOT / "sadf"
    assert _convert_path_to_abspath("/sadf") == Path("/sadf")


def test_convert_paths_to_abspath():
    assert _convert_paths_to_abspath([Path("sadf"), Path("/sadf")]) == [REPO_ROOT / "sadf", Path("/sadf")]


def test_make_python_tool_importable(tmp_path: Path) -> None:
    test_file = tmp_path / "test_module.py"
    test_file.write_text("test_value = 42\n")
    make_python_tool_importable(test_file)
    assert "test_module" in sys.modules
    assert sys.modules["test_module"].test_value == 42


def test_make_python_tool_importable_custom_name(tmp_path: Path) -> None:
    test_file = tmp_path / "test_module.py"
    test_file.write_text("test_value = 42\n")
    make_python_tool_importable(test_file, "custom_module")
    assert "custom_module" in sys.modules
    assert sys.modules["custom_module"].test_value == 42


def test_make_python_tool_importable_already_imported(tmp_path: Path) -> None:
    test_file = tmp_path / "test_module.py"
    test_file.write_text("test_value = 42\n")
    make_python_tool_importable(test_file, "duplicate_module")
    make_python_tool_importable(test_file, "duplicate_module")
    assert sys.modules["duplicate_module"].test_value == 42


def test_make_python_tool_importable_nonexistent_file() -> None:
    with pytest.raises(ImportError):
        make_python_tool_importable("/tmp/nonexistent_file_for_testing_12345.py")
