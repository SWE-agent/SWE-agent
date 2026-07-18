from __future__ import annotations

from pathlib import Path

from sweagent import __version__


def test_version():
    assert __version__.count(".") == 2


def test_tool_install_scripts_do_not_require_pip_executable():
    repo_root = Path(__file__).resolve().parents[1]
    install_scripts = sorted((repo_root / "tools").glob("*/install.sh"))
    assert install_scripts

    offenders = []
    for script in install_scripts:
        for line_number, line in enumerate(script.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("pip install"):
                offenders.append(f"{script.relative_to(repo_root)}:{line_number}")

    assert offenders == []
