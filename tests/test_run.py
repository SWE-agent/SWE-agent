from __future__ import annotations

import os
import subprocess


def test_run_cli_no_arg_error():
    args = [
        "sweagent",
    ]
    output = subprocess.run(args, check=False, capture_output=True)
    print(output.stdout.decode())
    print(output.stderr.decode())
    assert output.returncode in [1, 2]
    assert "run-batch" in output.stdout.decode()
    assert "run-replay" in output.stdout.decode()
    assert "run" in output.stdout.decode()


def test_run_cli_main_help():
    args = [
        "sweagent",
        "--help",
    ]
    output = subprocess.run(args, check=True, capture_output=True)
    assert "run-batch" in output.stdout.decode()
    assert "run-replay" in output.stdout.decode()
    assert "run" in output.stdout.decode()


def test_run_cli_subcommand_help():
    args = [
        "sweagent",
        "run",
        "--help",
    ]
    output = subprocess.run(args, check=True, capture_output=True)
    assert "--config" in output.stdout.decode()


def test_run_cli_main_help_non_utf8_stdio():
    """--help must not die with UnicodeEncodeError when stdio cannot encode emoji.

    cp1252 stands in for the default encoding of many Windows consoles, where the
    emoji-decorated banner and help text used to crash the CLI before any output.
    """
    args = [
        "sweagent",
        "--help",
    ]
    env = os.environ | {"PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
    output = subprocess.run(args, check=True, capture_output=True, env=env)
    assert "run-batch" in output.stdout.decode("cp1252")
