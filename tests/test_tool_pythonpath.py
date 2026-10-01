import json
import os
import subprocess
import sys

import pytest

from sweagent import TOOLS_DIR


@pytest.mark.parametrize("bundle", ["registry", "windowed"])
@pytest.mark.parametrize("existing", [None, "", "existing libraries"])
def test_tool_install_does_not_add_working_directory_to_pythonpath(bundle, existing, tmp_path):
    # Build helpers run scripts outside the source tree. An empty PYTHONPATH
    # component incorrectly makes that source tree importable by the helper.
    source = tmp_path / "source"
    source.mkdir()
    probe = tmp_path / "probe.py"
    probe.write_text("import json, sys; print(json.dumps(sys.path))")
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    if existing is not None:
        env["PYTHONPATH"] = str(tmp_path / existing) if existing else ""
    result = subprocess.run(
        [
            "bash",
            "-c",
            '_write_env() { :; }; source "$1"; "$2" "$3"',
            "test",
            str(TOOLS_DIR / bundle / "install.sh"),
            sys.executable,
            str(probe),
        ],
        cwd=source,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    paths = json.loads(result.stdout)
    assert str(source) not in paths
    assert str(TOOLS_DIR / bundle / "lib") in paths
    if existing:
        assert str(tmp_path / existing) in paths
