import json
import os
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from tests.utils import make_python_tool_importable

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"

make_python_tool_importable(TOOLS_DIR / "registry" / "lib" / "registry.py", "registry")
make_python_tool_importable(TOOLS_DIR / "windowed" / "lib" / "windowed_file.py", "windowed_file")
make_python_tool_importable(TOOLS_DIR / "windowed" / "lib" / "flake8_utils.py", "flake8_utils")
make_python_tool_importable(TOOLS_DIR / "windowed_edit_replace" / "bin" / "insert", "insert_tool")

import insert_tool  # type: ignore


class InsertToolTest(unittest.TestCase):
    def test_insert_after_requested_display_line(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            env_file = tmp_path / ".swe-agent-env"
            target_file = tmp_path / "example.py"
            target_file.write_text("1\n2\n3\n4\n5\n6")
            env_file.write_text(
                json.dumps(
                    {
                        "CURRENT_FILE": str(target_file),
                        "FIRST_LINE": "0",
                        "WINDOW": "10",
                    }
                )
            )

            with mock.patch.dict(os.environ, {"SWE_AGENT_ENV_FILE": str(env_file)}, clear=True):
                with mock.patch.object(insert_tool, "flake8", return_value=""):
                    with redirect_stdout(StringIO()):
                        insert_tool.main("inserted", 5)

            assert target_file.read_text() == "1\n2\n3\n4\n5\ninserted\n6"


if __name__ == "__main__":
    unittest.main()
