"""Tests for Ollama model integration."""

import pytest

from sweagent.agent.models import OllamaModelConfig, get_model
from sweagent.agent.tools import ToolConfig


def test_ollama_model_config():
    """Test Ollama model configuration."""
    config = OllamaModelConfig(
        name="ollama",
        model_id="llama2",
        api_base="http://localhost:11434",
        temperature=0.0,
        top_p=0.95,
    )
    assert config.name == "ollama"
    assert config.model_id == "llama2"
    assert config.api_base == "http://localhost:11434"


def test_ollama_model_creation():
    """Test Ollama model creation through get_model."""
    config = OllamaModelConfig(
        name="ollama",
        model_id="llama2",
        api_base="http://localhost:11434",
        temperature=0.0,
        top_p=0.95,
    )
    tools = ToolConfig()  # Default tool config
    model = get_model(config, tools)
    assert model is not None
    # Model name should be converted to LiteLLM format
    assert model.args.name == "ollama/llama2"


def test_ollama_model_config_validation():
    """Test Ollama model configuration validation."""
    with pytest.raises(ValueError):
        OllamaModelConfig(
            name="not_ollama",  # Invalid name
            model_id="llama2",
            api_base="http://localhost:11434",
        )

    with pytest.raises(ValueError):
        OllamaModelConfig(
            name="ollama",
            model_id="",  # Empty model_id
            api_base="http://localhost:11434",
        )


def test_ollama_model_from_generic():
    """Test creating Ollama model from generic config."""
    from sweagent.agent.models import GenericAPIModelConfig

    config = GenericAPIModelConfig(
        name="ollama",
        api_base="http://localhost:11434",
        temperature=0.0,
        top_p=0.95,
    )
    tools = ToolConfig()
    model = get_model(config, tools)
    assert model is not None
    assert isinstance(model.args, OllamaModelConfig)
    assert model.args.api_base == "http://localhost:11434"
