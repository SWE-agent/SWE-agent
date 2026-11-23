import shutil
import subprocess
from unittest.mock import MagicMock

import pytest
from rich.markdown import Markdown

from sweagent.run.hooks.apply_patch import SaveApplyPatchHook


@pytest.mark.skipif(shutil.which("sh") is None, reason="Requires a POSIX shell")
@pytest.mark.parametrize("name", ["it's a patch.patch", "patch $HOME.patch", "plain.patch"])
def test_printed_patch_path_can_be_used_in_shell(tmp_path, monkeypatch, name):
    patch_file = tmp_path / name
    patch_file.write_text("example patch\n")
    console = MagicMock()
    monkeypatch.setattr("rich.console.Console", lambda: console)

    SaveApplyPatchHook._print_patch_message(patch_file)
    markdown = next(call.args[0] for call in console.print.call_args_list if isinstance(call.args[0], Markdown))
    assignment = next(line for line in markdown.markup.splitlines() if line.startswith("PATCH_FILE_PATH="))
    result = subprocess.run(
        [shutil.which("sh"), "-c", assignment + '\ncat "${PATCH_FILE_PATH}"'],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == "example patch\n"
