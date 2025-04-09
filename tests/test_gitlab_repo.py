import os
from unittest import mock

from sweagent.environment.repo import (
    GitlabRepoConfig,
    repo_from_simplified_input,
)


class TestGitlabRepoConfig:
    """Test GitLab repository configuration"""

    def test_gitlab_repo_config_init(self):
        """Test GitlabRepoConfig initialization"""
        # Test with full URL
        config = GitlabRepoConfig(gitlab_url="https://gitlab.com/user/repo")
        assert config.gitlab_url == "https://gitlab.com/user/repo"
        assert config.base_commit == "HEAD"
        assert config.type == "gitlab"

        # Test with shorthand notation
        config = GitlabRepoConfig(gitlab_url="user/repo")
        assert config.gitlab_url == "https://gitlab.com/user/repo"

        # Test with custom base commit
        config = GitlabRepoConfig(gitlab_url="user/repo", base_commit="main")
        assert config.base_commit == "main"

        # Test with custom GitLab instance
        config = GitlabRepoConfig(gitlab_url="https://gitlab.example.com/user/repo")
        assert config.gitlab_url == "https://gitlab.example.com/user/repo"

    def test_repo_name_property(self):
        """Test repo_name property"""
        # Test with gitlab.com
        config = GitlabRepoConfig(gitlab_url="https://gitlab.com/user/repo")
        assert config.repo_name == "gitlab_com__user__repo"

        # Test with custom GitLab instance
        config = GitlabRepoConfig(gitlab_url="https://gitlab.example.com/user/repo")
        assert config.repo_name == "gitlab_example_com__user__repo"

    def test_get_url_with_token_oauth(self):
        """Test _get_url_with_token method with OAuth token"""
        config = GitlabRepoConfig(gitlab_url="https://gitlab.com/user/repo")
        url = config._get_url_with_token("test_token", "oauth")
        assert url == "https://oauth2:test_token@gitlab.com/user/repo"

    def test_get_url_with_token_private(self):
        """Test _get_url_with_token method with private token"""
        config = GitlabRepoConfig(gitlab_url="https://gitlab.com/user/repo")
        url = config._get_url_with_token("test_token", "private")
        assert url == "https://test_token:x-oauth-basic@gitlab.com/user/repo"

    def test_get_url_with_token_personal(self):
        """Test _get_url_with_token method with personal access token"""
        config = GitlabRepoConfig(gitlab_url="https://gitlab.com/user/repo")
        url = config._get_url_with_token("test_token", "personal")
        assert url == "https://test_token:x-oauth-basic@gitlab.com/user/repo"

    def test_get_reset_commands(self):
        """Test get_reset_commands method"""
        config = GitlabRepoConfig(gitlab_url="https://gitlab.com/user/repo")
        commands = config.get_reset_commands()
        assert len(commands) == 4
        assert commands[0] == "git status"
        assert commands[1] == "git restore ."
        assert commands[2] == "git reset --hard HEAD"
        assert commands[3] == "git clean -fdq"

        # Test with custom base commit
        config = GitlabRepoConfig(gitlab_url="https://gitlab.com/user/repo", base_commit="main")
        commands = config.get_reset_commands()
        assert commands[2] == "git reset --hard main"


class TestRepoFromSimplifiedInput:
    """Test repo_from_simplified_input function with GitLab URLs"""

    def test_explicit_gitlab_type(self):
        """Test with explicit gitlab type"""
        config = repo_from_simplified_input(input="https://gitlab.com/user/repo", type="gitlab")
        assert isinstance(config, GitlabRepoConfig)
        assert config.gitlab_url == "https://gitlab.com/user/repo"

        # Test with shorthand notation
        config = repo_from_simplified_input(input="user/repo", type="gitlab")
        assert isinstance(config, GitlabRepoConfig)
        assert config.gitlab_url == "https://gitlab.com/user/repo"

        # Test with custom GitLab instance
        config = repo_from_simplified_input(input="https://gitlab.example.com/user/repo", type="gitlab")
        assert isinstance(config, GitlabRepoConfig)
        assert config.gitlab_url == "https://gitlab.example.com/user/repo"

    def test_auto_detect_gitlab(self):
        """Test auto detection of GitLab URLs"""
        # Test with gitlab.com URL
        config = repo_from_simplified_input(input="https://gitlab.com/user/repo", type="auto")
        assert isinstance(config, GitlabRepoConfig)
        assert config.gitlab_url == "https://gitlab.com/user/repo"

        # Test with custom GitLab instance
        config = repo_from_simplified_input(input="https://gitlab.example.com/user/repo", type="auto")
        assert isinstance(config, GitlabRepoConfig)
        assert config.gitlab_url == "https://gitlab.example.com/user/repo"

        # Test with SSH URL
        config = repo_from_simplified_input(input="git@gitlab.com:user/repo.git", type="auto")
        assert isinstance(config, GitlabRepoConfig)
        assert config.gitlab_url == "git@gitlab.com:user/repo.git"


@mock.patch.dict(os.environ, {"GITLAB_TOKEN": "test_token", "GITLAB_TOKEN_TYPE": "private"})
class TestGitlabRepoConfigWithToken:
    """Test GitLab repository configuration with token"""

    @mock.patch("sweagent.environment.repo.asyncio.run")
    def test_copy_with_private_token(self, mock_run):
        """Test copy method with private token"""
        config = GitlabRepoConfig(gitlab_url="https://gitlab.com/user/repo")

        # Create a more detailed mock to capture the command string
        mock_command = mock.MagicMock()
        mock_deployment = mock.MagicMock()
        mock_runtime = mock.MagicMock()
        mock_deployment.runtime = mock_runtime

        # Set up the mock chain to capture the command string
        def side_effect(command):
            # Store the command string for later assertion
            # The Command object has a 'command' attribute, not 'args'
            mock_command.command_string = command.command
            return mock.MagicMock()

        mock_runtime.execute.side_effect = side_effect

        # Call copy method
        config.copy(mock_deployment)

        # Verify asyncio.run was called
        mock_run.assert_called_once()

        # Get the command string from our mock
        command_string = mock_command.command_string

        # Check that the command includes setting the PRIVATE-TOKEN header
        assert "git config --global http.extraHeader" in command_string
        assert "PRIVATE-TOKEN: test_token" in command_string

        # Check that the command includes unsetting the header afterward
        assert "git config --global --unset http.extraHeader" in command_string
