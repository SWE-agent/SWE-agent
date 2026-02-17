from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from unittest import mock
from unittest.mock import Mock, patch

import pytest

from sweagent.environment.repo import SWESmithRepoConfig
from sweagent.run.batch_instances import BatchInstance, SWESmithInstances

# ── SWESmithRepoConfig.get_reset_commands ──


class TestSWESmithRepoConfigGetResetCommands:
    def test_no_mirror(self):
        """Falls back to standard git reset commands."""
        repo = SWESmithRepoConfig(repo_name="testbed", base_commit="abc123")
        cmds = repo.get_reset_commands()
        assert any("git checkout" in c and "abc123" in c for c in cmds)
        assert any("git fetch" in c for c in cmds)

    def test_with_mirror_and_token(self):
        """Fetches from mirror URL with token embedded."""
        repo = SWESmithRepoConfig(
            repo_name="testbed",
            base_commit="branch-id",
            mirror_url="https://github.com/org/repo.git",
        )
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_test123"}):
            cmds = repo.get_reset_commands()
        assert any("git fetch" in c and "ghp_test123@github.com/org/repo.git" in c for c in cmds)
        assert any("git checkout FETCH_HEAD" in c for c in cmds)
        assert not any(c == "git fetch" for c in cmds)

    def test_with_mirror_no_token(self):
        """Mirror URL but no token — fetches with bare URL."""
        repo = SWESmithRepoConfig(
            repo_name="testbed",
            base_commit="branch-id",
            mirror_url="https://github.com/org/repo.git",
        )
        with mock.patch.dict("os.environ", {}, clear=True):
            cmds = repo.get_reset_commands()
        assert any("git fetch" in c and "https://github.com/org/repo.git" in c for c in cmds)
        assert not any("@" in c for c in cmds if "git fetch" in c)


# ── SWESmithRepoConfig._get_url_with_token ──


class TestGetUrlWithToken:
    def test_prepends_token(self):
        url = SWESmithRepoConfig._get_url_with_token("https://github.com/org/repo.git", "ghp_abc")
        assert url == "https://ghp_abc@github.com/org/repo.git"

    def test_empty_token(self):
        url = SWESmithRepoConfig._get_url_with_token("https://github.com/org/repo.git", "")
        assert url == "https://github.com/org/repo.git"

    def test_empty_url(self):
        url = SWESmithRepoConfig._get_url_with_token("", "ghp_abc")
        assert url == ""


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

    @patch("sweagent.run.batch_instances._is_repo_private", return_value=False)
    def test_public_repo(self, mock_private, tmp_path):
        path = self._make_instance_file(tmp_path, [self._sample_instance()])
        config = SWESmithInstances(path=path)
        instances = config.get_instance_configs()

        assert len(instances) == 1
        inst = instances[0]
        assert isinstance(inst, BatchInstance)
        assert inst.env.repo.repo_name == "testbed"
        assert inst.env.repo.mirror_url == ""
        assert inst.env.deployment.image == "swebench/swesmith.x86_64.org_1776_repo.abc123"

    @patch("sweagent.run.batch_instances._is_repo_private", return_value=True)
    def test_private_repo(self, mock_private, tmp_path):
        path = self._make_instance_file(tmp_path, [self._sample_instance()])
        config = SWESmithInstances(path=path)

        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_fake"}):
            instances = config.get_instance_configs()

        assert len(instances) == 1
        inst = instances[0]
        assert inst.env.repo.mirror_url == "https://github.com/org/repo.git"

    @patch("sweagent.run.batch_instances._is_repo_private", return_value=True)
    def test_private_repo_no_token_raises(self, mock_private, tmp_path):
        path = self._make_instance_file(tmp_path, [self._sample_instance()])
        config = SWESmithInstances(path=path)

        with mock.patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="GITHUB_TOKEN is not set"):
                config.get_instance_configs()

    @patch("sweagent.run.batch_instances._is_repo_private", return_value=False)
    def test_filter_and_slice(self, mock_private, tmp_path):
        instances_data = [
            self._sample_instance(instance_id="org__repo.abc__test_1"),
            self._sample_instance(instance_id="org__repo.abc__test_2"),
            self._sample_instance(instance_id="org__repo.abc__test_3"),
        ]
        path = self._make_instance_file(tmp_path, instances_data)
        config = SWESmithInstances(path=path, filter=".*test_[12]", slice="0:1")
        instances = config.get_instance_configs()

        assert len(instances) == 1
