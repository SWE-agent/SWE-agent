from __future__ import annotations

import os
import sys
from functools import partial
from logging import WARNING, getLogger
from pathlib import Path

import swerex.utils.log as log_swerex
from git import Repo
from packaging import version

from sweagent.utils.log import get_logger

__version__ = "1.0.1"
PYTHON_MINIMUM_VERSION = (3, 11)
SWEREX_MINIMUM_VERSION = "1.2.0"
SWEREX_RECOMMENDED_VERSION = "1.2.1"

# Monkey patch the logger to use our implementation
log_swerex.get_logger = partial(get_logger, emoji="🦖")

# See https://github.com/SWE-agent/SWE-agent/issues/585
getLogger("datasets").setLevel(WARNING)
getLogger("numexpr.utils").setLevel(WARNING)
getLogger("LiteLLM").setLevel(WARNING)

PACKAGE_DIR = Path(__file__).resolve().parent

if sys.version_info < PYTHON_MINIMUM_VERSION:
    msg = (
        f"Python {sys.version_info.major}.{sys.version_info.minor} is not supported. "
        "SWE-agent requires Python 3.11 or higher."
    )
    raise RuntimeError(msg)

assert PACKAGE_DIR.is_dir(), PACKAGE_DIR
REPO_ROOT = PACKAGE_DIR.parent
assert REPO_ROOT.is_dir(), REPO_ROOT
CONFIG_DIR = Path(os.getenv("SWE_AGENT_CONFIG_DIR", PACKAGE_DIR.parent / "config"))
assert CONFIG_DIR.is_dir(), CONFIG_DIR

TOOLS_DIR = Path(os.getenv("SWE_AGENT_TOOLS_DIR", PACKAGE_DIR.parent / "tools"))
assert TOOLS_DIR.is_dir(), TOOLS_DIR

TRAJECTORY_DIR = Path(os.getenv("SWE_AGENT_TRAJECTORY_DIR", PACKAGE_DIR.parent / "trajectories"))
assert TRAJECTORY_DIR.is_dir(), TRAJECTORY_DIR


def get_agent_commit_hash() -> str:
    """Get the commit hash of the current SWE-agent commit.

    If we cannot get the hash, we return an empty string.
    """
    try:
        repo = Repo(REPO_ROOT, search_parent_directories=False)
    except Exception:
        return "unavailable"
    return repo.head.object.hexsha


def get_rex_commit_hash() -> str:
    import swerex

    try:
        repo = Repo(Path(swerex.__file__).resolve().parent.parent.parent, search_parent_directories=False)
    except Exception:
        return "unavailable"
    return repo.head.object.hexsha


def get_rex_version() -> str:
    from swerex import __version__ as rex_version

    return rex_version


def get_agent_version_info() -> str:
    hash = get_agent_commit_hash()
    rex_hash = get_rex_commit_hash()
    rex_version = get_rex_version()
    return f"This is SWE-agent version {__version__} ({hash=}) with SWE-ReX version {rex_version} ({rex_hash=})."


def impose_rex_lower_bound() -> None:
    rex_version = get_rex_version()
    minimal_rex_version = "1.2.0"
    if version.parse(rex_version) < version.parse(minimal_rex_version):
        msg = (
            f"SWE-ReX version {rex_version} is too old. Please update to at least {minimal_rex_version} by "
            "running `pip install --upgrade swe-rex`."
            "You can also rerun `pip install -e .` in this repository to install the latest version."
        )
        raise RuntimeError(msg)
    if version.parse(rex_version) < version.parse(SWEREX_RECOMMENDED_VERSION):
        msg = (
            f"SWE-ReX version {rex_version} is not recommended. Please update to at least {SWEREX_RECOMMENDED_VERSION} by "
            "running `pip install --upgrade swe-rex`."
            "You can also rerun `pip install -e .` in this repository to install the latest version."
        )
        get_logger("swe-agent", emoji="👋").warning(msg)


impose_rex_lower_bound()
get_logger("swe-agent", emoji="👋").info(get_agent_version_info())


__all__ = [
    "PACKAGE_DIR",
    "CONFIG_DIR",
    "get_agent_commit_hash",
    "get_agent_version_info",
    "__version__",
]
