from __future__ import annotations

import base64
import json
import os
import urllib.error
from pathlib import Path
from unittest import mock
from unittest.mock import Mock, patch

import pytest
from pydantic import SecretStr

from sweagent.environment.repo import SWESmithRepoConfig
from sweagent.run.batch_instances import BatchInstance, SWESmithInstances

# ── SWESmithRepoConfig.get_reset_commands ──


class TestSWESmithRepoConfigGetResetCommands:
    def test_no_mirror_no_key(self):
        """Falls back to standard git reset commands."""
        repo = SWESmithRepoConfig(repo_name="testbed", base_commit="abc123")
        cmds = repo.get_reset_commands()
        assert any("git checkout" in c and "abc123" in c for c in cmds)
        assert any("git fetch" in c for c in cmds)

    def test_with_mirror_and_key(self):
        """Injects SSH key and fetches from mirror URL."""
        repo = SWESmithRepoConfig(
            repo_name="testbed",
            base_commit="branch-id",
            mirror_url="git@github.com:org/repo.git",
            ssh_key_b64=SecretStr("c29tZWtleQ=="),
        )
        cmds = repo.get_reset_commands()
        assert any("base64 -d" in c for c in cmds)
        assert any("chmod 600" in c for c in cmds)
        assert any("GIT_SSH_COMMAND" in c for c in cmds)
        assert any("git fetch" in c and "git@github.com:org/repo.git" in c for c in cmds)
        assert any("git checkout FETCH_HEAD" in c for c in cmds)
        assert not any(c == "git fetch" for c in cmds)

    def test_with_mirror_no_key(self):
        """Mirror URL but empty key — still fetches, no SSH setup."""
        repo = SWESmithRepoConfig(
            repo_name="testbed",
            base_commit="branch-id",
            mirror_url="git@github.com:org/repo.git",
            ssh_key_b64=SecretStr(""),
        )
        cmds = repo.get_reset_commands()
        assert not any("base64 -d" in c for c in cmds)
        assert any("git fetch" in c and "git@github.com:org/repo.git" in c for c in cmds)

    def test_secret_not_leaked_in_repr(self):
        """SecretStr should mask the value in repr/str."""
        repo = SWESmithRepoConfig(
            repo_name="testbed",
            ssh_key_b64=SecretStr("supersecret"),
        )
        assert "supersecret" not in repr(repo)
        assert "supersecret" not in str(repo.model_dump())


# ── _is_repo_private ──


class TestIsRepoPrivate:
    def setup_method(self):
        from sweagent.utils.github import _repo_privacy_cache

        _repo_privacy_cache.clear()

    @patch("sweagent.utils.github.urllib.request.urlopen")
    def test_public_repo(self, mock_urlopen):
        mock_resp = Mock()
        mock_resp.read.return_value = json.dumps({"private": False}).encode()
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_resp

        from sweagent.utils.github import _is_repo_private

        assert _is_repo_private("org/repo", "fake-token") is False

    @patch("sweagent.utils.github.urllib.request.urlopen")
    def test_private_repo(self, mock_urlopen):
        mock_resp = Mock()
        mock_resp.read.return_value = json.dumps({"private": True}).encode()
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_resp

        from sweagent.utils.github import _is_repo_private

        assert _is_repo_private("org/repo", "fake-token") is True

    @patch("sweagent.utils.github.urllib.request.urlopen")
    def test_404_assumes_private(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,  # type: ignore
        )

        from sweagent.utils.github import _is_repo_private

        assert _is_repo_private("org/repo", "fake-token") is True

    @patch("sweagent.utils.github.urllib.request.urlopen")
    def test_other_http_error_raises(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="",
            code=500,
            msg="Server Error",
            hdrs=None,
            fp=None,  # type: ignore
        )

        from sweagent.utils.github import _is_repo_private

        with pytest.raises(urllib.error.HTTPError):
            _is_repo_private("org/repo", "fake-token")

    @patch("sweagent.utils.github.urllib.request.urlopen")
    def test_caching(self, mock_urlopen):
        mock_resp = Mock()
        mock_resp.read.return_value = json.dumps({"private": False}).encode()
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_resp

        from sweagent.utils.github import _is_repo_private

        _is_repo_private("org/cached-repo", "token")
        _is_repo_private("org/cached-repo", "token")
        assert mock_urlopen.call_count == 1


# ── _find_and_encode_ssh_key ──


class TestFindAndEncodeSshKey:
    def test_env_var_key(self, tmp_path):
        key_file = tmp_path / "my_key"
        key_file.write_text("my-ssh-key-content")
        expected = base64.b64encode(b"my-ssh-key-content").decode()

        with mock.patch.dict("os.environ", {"GITHUB_USER_SSH_KEY": str(key_file)}):
            from sweagent.utils.github import _find_and_encode_ssh_key

            assert _find_and_encode_ssh_key() == expected

    def test_default_ssh_key(self, tmp_path):
        ssh_dir = tmp_path / ".ssh"
        ssh_dir.mkdir()
        key_file = ssh_dir / "id_ed25519"
        key_file.write_text("ed25519-key")
        expected = base64.b64encode(b"ed25519-key").decode()

        env = {k: v for k, v in os.environ.items() if k != "GITHUB_USER_SSH_KEY"}
        with (
            mock.patch.dict("os.environ", env, clear=True),
            mock.patch("pathlib.Path.home", return_value=tmp_path),
        ):
            from sweagent.utils.github import _find_and_encode_ssh_key

            assert _find_and_encode_ssh_key() == expected

    def test_no_key_found(self, tmp_path):
        with (
            mock.patch.dict("os.environ", {}, clear=True),
            mock.patch("pathlib.Path.home", return_value=tmp_path),
        ):
            from sweagent.utils.github import _find_and_encode_ssh_key

            assert _find_and_encode_ssh_key() == ""


# ── SWESmithInstances.get_instance_configs ──


class TestSWESmithInstancesGetInstanceConfigs:
    @staticmethod
    def _make_instance_file(tmp_path: Path, instances: list[dict]) -> Path:
        p = tmp_path / "instances.json"
        p.write_text(json.dumps(instances))
        return p

    @staticmethod
    def _sample_instance(instance_id: str = "org__repo.abc123__test_1", repo: str = "org/repo") -> dict:
        return {
            "instance_id": instance_id,
            "image_name": "swebench/swesmith.x86_64.org_1776_repo.abc123",
            "repo": repo,
            "problem_statement": "Fix the bug",
            "FAIL_TO_PASS": ["test_foo.py::test_bar"],
        }

    @patch("sweagent.run.batch_instances._find_and_encode_ssh_key", return_value="")
    @patch("sweagent.run.batch_instances._is_repo_private", return_value=False)
    def test_public_repo(self, mock_private, mock_ssh, tmp_path):
        path = self._make_instance_file(tmp_path, [self._sample_instance()])
        config = SWESmithInstances(path=path)
        instances = config.get_instance_configs()

        assert len(instances) == 1
        inst = instances[0]
        assert isinstance(inst, BatchInstance)
        assert inst.env.repo.repo_name == "testbed"
        assert inst.env.repo.mirror_url == ""
        assert inst.env.deployment.image == "swebench/swesmith.x86_64.org_1776_repo.abc123"

    @patch("sweagent.run.batch_instances._find_and_encode_ssh_key", return_value="c29tZWtleQ==")
    @patch("sweagent.run.batch_instances._is_repo_private", return_value=True)
    def test_private_repo(self, mock_private, mock_ssh, tmp_path):
        path = self._make_instance_file(tmp_path, [self._sample_instance()])
        config = SWESmithInstances(path=path)
        instances = config.get_instance_configs()

        assert len(instances) == 1
        inst = instances[0]
        assert inst.env.repo.mirror_url == "git@github.com:org/repo.git"
        assert inst.env.repo.ssh_key_b64.get_secret_value() == "c29tZWtleQ=="

    @patch("sweagent.run.batch_instances._find_and_encode_ssh_key", return_value="")
    @patch("sweagent.run.batch_instances._is_repo_private", return_value=True)
    def test_private_repo_no_key_raises(self, mock_private, mock_ssh, tmp_path):
        path = self._make_instance_file(tmp_path, [self._sample_instance()])
        config = SWESmithInstances(path=path)

        with pytest.raises(ValueError, match="no SSH key found"):
            config.get_instance_configs()

    @patch("sweagent.run.batch_instances._find_and_encode_ssh_key", return_value="")
    @patch("sweagent.run.batch_instances._is_repo_private", return_value=False)
    def test_filter_and_slice(self, mock_private, mock_ssh, tmp_path):
        instances_data = [
            self._sample_instance(instance_id="org__repo.abc__test_1"),
            self._sample_instance(instance_id="org__repo.abc__test_2"),
            self._sample_instance(instance_id="org__repo.abc__test_3"),
        ]
        path = self._make_instance_file(tmp_path, instances_data)
        config = SWESmithInstances(path=path, filter=".*test_[12]", slice="0:1")
        instances = config.get_instance_configs()

        assert len(instances) == 1
