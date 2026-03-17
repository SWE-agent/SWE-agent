"""Tests for MiniMax model integration.

Tests cover:
- Config loading and validation
- Model registry loading
- Temperature constraint handling
- API call with correct parameters (mock)
- Integration test with real MiniMax API (requires MINIMAX_API_KEY)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from sweagent import REPO_ROOT
from sweagent.agent.models import GenericAPIModelConfig, LiteLLMModel, get_model
from sweagent.tools.parsing import Identity
from sweagent.tools.tools import ToolConfig
from sweagent.types import History

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAX_REGISTRY_PATH = str(REPO_ROOT / "config" / "minimax_model_registry.json")


def _make_tool_config() -> ToolConfig:
    return ToolConfig(parse_function=Identity())


def _make_minimax_config(**overrides) -> GenericAPIModelConfig:
    defaults = {
        "name": "openai/MiniMax-M2.5",
        "api_base": "https://api.minimax.io/v1",
        "api_key": SecretStr("test-minimax-key"),
        "temperature": 1.0,
        "top_p": None,
        "per_instance_cost_limit": 0,
        "total_cost_limit": 0,
        "litellm_model_registry": MINIMAX_REGISTRY_PATH,
    }
    defaults.update(overrides)
    return GenericAPIModelConfig(**defaults)


def _make_mock_response(content: str = "Hello from MiniMax") -> MagicMock:
    """Create a minimal mock response matching litellm's ModelResponse shape."""
    choice = MagicMock()
    choice.message.content = content
    choice.message.tool_calls = None
    response = MagicMock()
    response.choices = [choice]
    response.usage.prompt_tokens = 10
    response.usage.completion_tokens = 5
    return response


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------


class TestMiniMaxConfig:
    """Test MiniMax model configuration."""

    def test_config_creation(self):
        """MiniMax config can be created with correct defaults."""
        config = _make_minimax_config()
        assert config.name == "openai/MiniMax-M2.5"
        assert config.api_base == "https://api.minimax.io/v1"
        assert config.temperature == 1.0

    def test_config_highspeed_model(self):
        """Highspeed model variant can be configured."""
        config = _make_minimax_config(name="openai/MiniMax-M2.5-highspeed")
        assert config.name == "openai/MiniMax-M2.5-highspeed"

    def test_api_key_from_env_var(self):
        """API key can reference an environment variable."""
        config = _make_minimax_config(api_key=SecretStr("$MINIMAX_API_KEY"))
        assert config.api_key.get_secret_value() == "$MINIMAX_API_KEY"

    def test_temperature_valid_range(self):
        """Temperature 1.0 is valid for MiniMax (range is (0.0, 1.0])."""
        config = _make_minimax_config(temperature=1.0)
        assert config.temperature == 1.0

    def test_temperature_nonzero(self):
        """Temperature 0.5 is valid for MiniMax."""
        config = _make_minimax_config(temperature=0.5)
        assert config.temperature == 0.5

    def test_domestic_api_base(self):
        """Domestic (mainland China) API base can be configured."""
        config = _make_minimax_config(api_base="https://api.minimaxi.com/v1")
        assert config.api_base == "https://api.minimaxi.com/v1"


class TestMiniMaxModelRegistry:
    """Test MiniMax model cost registry."""

    def test_registry_file_exists(self):
        """Model registry JSON file exists."""
        assert Path(MINIMAX_REGISTRY_PATH).exists()

    def test_registry_valid_json(self):
        """Registry file is valid JSON."""
        with open(MINIMAX_REGISTRY_PATH) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_registry_contains_m25(self):
        """Registry contains MiniMax-M2.5 model."""
        with open(MINIMAX_REGISTRY_PATH) as f:
            data = json.load(f)
        assert "openai/MiniMax-M2.5" in data

    def test_registry_contains_m25_highspeed(self):
        """Registry contains MiniMax-M2.5-highspeed model."""
        with open(MINIMAX_REGISTRY_PATH) as f:
            data = json.load(f)
        assert "openai/MiniMax-M2.5-highspeed" in data

    def test_registry_m25_fields(self):
        """M2.5 registry entry has all required fields."""
        with open(MINIMAX_REGISTRY_PATH) as f:
            data = json.load(f)
        model = data["openai/MiniMax-M2.5"]
        assert model["max_input_tokens"] == 204800
        assert model["max_output_tokens"] == 192000
        assert model["input_cost_per_token"] > 0
        assert model["output_cost_per_token"] > 0
        assert model["litellm_provider"] == "openai"
        assert model["mode"] == "chat"

    def test_registry_m25_highspeed_fields(self):
        """M2.5-highspeed registry entry has all required fields."""
        with open(MINIMAX_REGISTRY_PATH) as f:
            data = json.load(f)
        model = data["openai/MiniMax-M2.5-highspeed"]
        assert model["max_input_tokens"] == 204800
        assert model["max_output_tokens"] == 192000
        assert model["litellm_provider"] == "openai"

    def test_highspeed_costs_higher(self):
        """Highspeed model costs more per token than standard M2.5."""
        with open(MINIMAX_REGISTRY_PATH) as f:
            data = json.load(f)
        m25 = data["openai/MiniMax-M2.5"]
        hs = data["openai/MiniMax-M2.5-highspeed"]
        assert hs["input_cost_per_token"] > m25["input_cost_per_token"]
        assert hs["output_cost_per_token"] > m25["output_cost_per_token"]


class TestMiniMaxConfigYAML:
    """Test MiniMax YAML config file."""

    def test_config_file_exists(self):
        """MiniMax config YAML file exists."""
        assert (REPO_ROOT / "config" / "minimax.yaml").exists()

    def test_config_file_valid_yaml(self):
        """Config file is valid YAML and contains expected structure."""
        import yaml

        with open(REPO_ROOT / "config" / "minimax.yaml") as f:
            data = yaml.safe_load(f)
        assert "agent" in data
        assert "model" in data["agent"]
        model = data["agent"]["model"]
        assert model["name"] == "openai/MiniMax-M2.5"
        assert model["api_base"] == "https://api.minimax.io/v1"
        assert model["temperature"] == 1.0


class TestMiniMaxModelCreation:
    """Test creating MiniMax model instances."""

    def test_get_model_returns_litellm_model(self):
        """get_model returns LiteLLMModel for MiniMax config."""
        config = _make_minimax_config()
        model = get_model(config, _make_tool_config())
        assert isinstance(model, LiteLLMModel)

    def test_model_max_tokens_from_registry(self):
        """Model loads max input/output tokens from registry."""
        config = _make_minimax_config()
        model = get_model(config, _make_tool_config())
        assert isinstance(model, LiteLLMModel)
        assert model.model_max_input_tokens == 204800
        assert model.model_max_output_tokens == 192000

    def test_model_query_mock(self):
        """MiniMax model can query with mocked litellm response."""
        config = _make_minimax_config()
        model = get_model(config, _make_tool_config())
        mock_response = _make_mock_response("MiniMax test response")

        with patch("litellm.completion", return_value=mock_response):
            result = model.query(History([{"role": "user", "content": "Hello"}]))
        assert result["message"] == "MiniMax test response"

    def test_model_passes_correct_api_base(self):
        """Model passes api_base to litellm.completion."""
        config = _make_minimax_config()
        model = get_model(config, _make_tool_config())
        mock_response = _make_mock_response()

        with patch("litellm.completion", return_value=mock_response) as mock_completion:
            model.query(History([{"role": "user", "content": "test"}]))
            call_kwargs = mock_completion.call_args
            assert call_kwargs.kwargs["api_base"] == "https://api.minimax.io/v1"

    def test_model_passes_correct_temperature(self):
        """Model passes temperature=1.0 to litellm.completion."""
        config = _make_minimax_config(temperature=1.0)
        model = get_model(config, _make_tool_config())
        mock_response = _make_mock_response()

        with patch("litellm.completion", return_value=mock_response) as mock_completion:
            model.query(History([{"role": "user", "content": "test"}]))
            call_kwargs = mock_completion.call_args
            assert call_kwargs.kwargs["temperature"] == 1.0

    def test_model_passes_api_key(self):
        """Model passes API key to litellm.completion."""
        config = _make_minimax_config(api_key=SecretStr("sk-test-minimax-key"))
        model = get_model(config, _make_tool_config())
        mock_response = _make_mock_response()

        with patch("litellm.completion", return_value=mock_response) as mock_completion:
            model.query(History([{"role": "user", "content": "test"}]))
            call_kwargs = mock_completion.call_args
            assert call_kwargs.kwargs["api_key"] == "sk-test-minimax-key"

    def test_model_passes_correct_model_name(self):
        """Model passes the correct model name to litellm.completion."""
        config = _make_minimax_config()
        model = get_model(config, _make_tool_config())
        mock_response = _make_mock_response()

        with patch("litellm.completion", return_value=mock_response) as mock_completion:
            model.query(History([{"role": "user", "content": "test"}]))
            call_kwargs = mock_completion.call_args
            assert call_kwargs.kwargs["model"] == "openai/MiniMax-M2.5"


# ---------------------------------------------------------------------------
# Integration Tests (require MINIMAX_API_KEY)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("MINIMAX_API_KEY"),
    reason="MINIMAX_API_KEY not set; skipping integration test",
)
class TestMiniMaxIntegration:
    """Integration tests that call the real MiniMax API."""

    def test_simple_query(self):
        """Send a simple query to MiniMax API and get a response."""
        config = GenericAPIModelConfig(
            name="openai/MiniMax-M2.5",
            api_base="https://api.minimax.io/v1",
            api_key=SecretStr(os.environ["MINIMAX_API_KEY"]),
            temperature=1.0,
            top_p=None,
            per_instance_cost_limit=0,
            total_cost_limit=0,
            litellm_model_registry=MINIMAX_REGISTRY_PATH,
        )
        model = get_model(config, _make_tool_config())
        result = model.query(History([{"role": "user", "content": "Say 'hello' and nothing else."}]))
        assert "message" in result
        assert len(result["message"]) > 0

    def test_highspeed_model_query(self):
        """Send a query to MiniMax-M2.5-highspeed and get a response."""
        config = GenericAPIModelConfig(
            name="openai/MiniMax-M2.5-highspeed",
            api_base="https://api.minimax.io/v1",
            api_key=SecretStr(os.environ["MINIMAX_API_KEY"]),
            temperature=1.0,
            top_p=None,
            per_instance_cost_limit=0,
            total_cost_limit=0,
            litellm_model_registry=MINIMAX_REGISTRY_PATH,
        )
        model = get_model(config, _make_tool_config())
        result = model.query(History([{"role": "user", "content": "What is 2 + 2? Answer with just the number."}]))
        assert "message" in result
        assert "4" in result["message"]

    def test_multi_turn_conversation(self):
        """MiniMax handles multi-turn conversation correctly."""
        config = GenericAPIModelConfig(
            name="openai/MiniMax-M2.5",
            api_base="https://api.minimax.io/v1",
            api_key=SecretStr(os.environ["MINIMAX_API_KEY"]),
            temperature=1.0,
            top_p=None,
            per_instance_cost_limit=0,
            total_cost_limit=0,
            litellm_model_registry=MINIMAX_REGISTRY_PATH,
        )
        model = get_model(config, _make_tool_config())
        result = model.query(
            History(
                [
                    {"role": "system", "content": "You are a helpful assistant. Answer concisely."},
                    {"role": "user", "content": "What is the capital of France?"},
                ]
            )
        )
        assert "message" in result
        assert "Paris" in result["message"]
