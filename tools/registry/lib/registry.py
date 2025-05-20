import json
import os
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

env_dir = os.environ.get("ENV_DIR", "/root").rstrip("/")


class EnvRegistry:
    """Read and write variables into a file. This is used to persist state between tool
    calls without using environment variables (which are problematic because you cannot
    set them in a subprocess).

    The default file location is `{env_dir}/.swe-agent-env`, though this can be overridden
    by the `env_file` argument or the `SWE_AGENT_ENV_FILE` environment variable.
    """

    def __init__(self, env_file: Optional[Path] = None):
        self._env_file = env_file

    @property
    def env_file(self) -> Path:
        if self._env_file is None:
            env_file = Path(os.environ.get("SWE_AGENT_ENV_FILE", f"{env_dir}/.swe-agent-env"))
        else:
            env_file = self._env_file
        if not env_file.exists():
            env_file.write_text("{}")
        return env_file

    def __getitem__(self, key: str) -> str:
        return json.loads(self.env_file.read_text())[key]

    def get(self, key: str, default_value: Any = None, fallback_to_env: bool = True) -> Any:
        """Get a value from registry:

        Args:
            key: The key to get the value for.
            default_value: The default value to return if the key is not found in the registry.
            fallback_to_env: If True, fallback to environment variables if the key is not found in the registry.
                If there's no environment variable, return the default value.
        """
        if fallback_to_env and key in os.environ:
            default_value = os.environ[key]
        return json.loads(self.env_file.read_text()).get(key, default_value)

    def get_if_none(self, value: Any, key: str, default_value: Any = None) -> Any:
        if value is not None:
            return value
        return self.get(key, default_value)

    def __setitem__(self, key: str, value: Any):
        env = json.loads(self.env_file.read_text())
        env[key] = value
        self.env_file.write_text(json.dumps(env))


registry = EnvRegistry()
