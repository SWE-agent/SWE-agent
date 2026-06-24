"""Compatibility patches for SWE-ReX deployment behavior."""


def apply_swerex_compat_patches() -> None:
    """Use pip instead of pipx when bootstrapping swe-rex in containers.

    pipx ensurepath does not update PATH in the same shell session, so the
    fallback startup command in swe-rex 1.4.0 can fail with
    ``swerex-remote: not found`` (SWE-agent#1326).
    """
    from swerex import PACKAGE_NAME, REMOTE_EXECUTABLE_NAME
    from swerex.deployment.docker import DockerDeployment

    def _get_swerex_start_cmd(self, token: str) -> list[str]:
        rex_args = f"--auth-token {token}"
        pip_fallback = f"python3 -m pip install -q {PACKAGE_NAME} && {REMOTE_EXECUTABLE_NAME} {rex_args}"
        if self._config.python_standalone_dir:
            cmd = f"{self._config.python_standalone_dir}/python3.11/bin/{REMOTE_EXECUTABLE_NAME} {rex_args}"
        else:
            cmd = f"{REMOTE_EXECUTABLE_NAME} {rex_args} || ({pip_fallback})"
        return ["/bin/sh", "-c", cmd]

    DockerDeployment._get_swerex_start_cmd = _get_swerex_start_cmd  # type: ignore[method-assign]
