from sweagent.environment.swerex_compat import apply_swerex_compat_patches


def test_docker_deployment_uses_pip_fallback_without_pipx():
    apply_swerex_compat_patches()

    from swerex.deployment.docker import DockerDeployment

    deployment = DockerDeployment(image="python:3.11", python_standalone_dir=None)
    cmd = deployment._get_swerex_start_cmd("test-token")

    assert cmd[0:2] == ["/bin/sh", "-c"]
    shell_cmd = cmd[2]
    assert "python3 -m pip install -q swe-rex" in shell_cmd
    assert "pipx" not in shell_cmd
    assert "swerex-remote --auth-token test-token" in shell_cmd


def test_docker_deployment_keeps_standalone_python_path():
    apply_swerex_compat_patches()

    from swerex.deployment.docker import DockerDeployment

    deployment = DockerDeployment(image="python:3.11", python_standalone_dir="/root")
    cmd = deployment._get_swerex_start_cmd("abc")

    assert cmd[2] == "/root/python3.11/bin/swerex-remote --auth-token abc"
