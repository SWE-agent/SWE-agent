"""Tests for Azure model configuration and warnings."""

from sweagent.agent.models import GenericAPIModelConfig, LiteLLMModel
from sweagent.agent.tools import ToolConfig


def test_azure_endpoint_warning(caplog):
    """Test that using Azure endpoint with model argument shows warning."""
    config = GenericAPIModelConfig(
        name="gpt-4", api_base="https://example.azure.openai.azure.com", api_version="2023-05-15"
    )
    tools = ToolConfig()

    _ = LiteLLMModel(config, tools)

    assert any(
        "Using Azure endpoint - the --model CLI argument will be ignored" in record.message for record in caplog.records
    )


def test_non_azure_endpoint_no_warning(caplog):
    """Test that using non-Azure endpoint does not show warning."""
    config = GenericAPIModelConfig(name="gpt-4", api_base="https://api.openai.com/v1")
    tools = ToolConfig()

    _ = LiteLLMModel(config, tools)

    assert not any(
        "Using Azure endpoint - the --model CLI argument will be ignored" in record.message for record in caplog.records
    )
