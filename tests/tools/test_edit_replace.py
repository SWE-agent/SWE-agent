import importlib
from unittest.mock import Mock

import pytest

from sweagent import TOOLS_DIR
from tests.utils import make_python_tool_importable


def test_edit_rejects_empty_search_before_linting(with_tmp_env_file, tmp_path, capsys, monkeypatch):
    make_python_tool_importable(TOOLS_DIR / "windowed_edit_replace/bin/edit", "edit_replace")
    edit = importlib.import_module("edit_replace")
    from registry import registry

    path = tmp_path / "example.py"
    path.write_text("original = 1\n")
    registry["CURRENT_FILE"] = str(path)
    registry["WINDOW"] = "10"
    registry["FIRST_LINE"] = "0"

    lint = Mock()
    monkeypatch.setattr(edit, "flake8", lint)
    with pytest.raises(SystemExit) as error:
        edit.main("", "new", True)
    lint.assert_not_called()
    assert error.value.code == 2
    output = capsys.readouterr().out
    assert "Search text must not be empty" in output
    assert edit.RETRY_WITH_OUTPUT_TOKEN in output
    assert path.read_text() == "original = 1\n"
