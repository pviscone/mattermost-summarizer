"""Tests for config loading."""

import tempfile

import pytest
from pydantic import HttpUrl, SecretStr, ValidationError

from mattermost_summarizer.config import MattermostSummarizerConfig
from mattermost_summarizer.levels import SummaryLevel


class TestMattermostSummarizerConfig:
    def test_from_env_missing_required(self) -> None:
        with pytest.raises(ValidationError):
            MattermostSummarizerConfig.from_env()

    def test_from_config_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            MattermostSummarizerConfig.from_config("/nonexistent/config.toml")


class TestConfigEnvVarLoading:
    def test_config_defaults(self) -> None:
        config = MattermostSummarizerConfig(
            mattermost_url=HttpUrl("https://chat.example.com"),
            mattermost_token=SecretStr("test-token"),
            llm_api_key=SecretStr("test-key"),
        )
        assert str(config.mattermost_url) == "https://chat.example.com/"
        assert config.llm_model == "openai/gpt-4o"
        assert config.llm_base_url is None
        assert config.max_reference_depth == 3
        assert config.critic_enabled is True
        assert config.critic_threshold == 0.7
        assert config.critic_max_iterations == 2

    def test_config_custom_values(self) -> None:
        config = MattermostSummarizerConfig(
            mattermost_url=HttpUrl("https://mattermost.example.com"),
            mattermost_token=SecretStr("my-secret-token"),
            llm_api_key=SecretStr("llm-secret-key"),
            llm_model="anthropic/claude-3-sonnet",
            llm_base_url="https://api.anthropic.com",
            max_reference_depth=5,
            critic_enabled=False,
            critic_threshold=0.85,
            critic_max_iterations=3,
        )
        assert str(config.mattermost_url) == "https://mattermost.example.com/"
        assert config.llm_model == "anthropic/claude-3-sonnet"
        assert config.llm_base_url == "https://api.anthropic.com"
        assert config.max_reference_depth == 5
        assert config.critic_enabled is False
        assert config.critic_threshold == 0.85
        assert config.critic_max_iterations == 3

    def test_secret_str_not_exposed_in_repr(self) -> None:
        config = MattermostSummarizerConfig(
            mattermost_url=HttpUrl("https://chat.example.com"),
            mattermost_token=SecretStr("secret-token"),
            llm_api_key=SecretStr("llm-key"),
        )
        repr_str = repr(config)
        assert "secret-token" not in repr_str
        assert "llm-key" not in repr_str

    def test_toml_config_with_summarizer_section(self) -> None:
        toml_content = """
[mattermost]
url = "https://chat.example.com"
token = "test-token"

[llm]
model = "openai/gpt-4o"
api_key = "test-key"

[summarizer]
default_level = "detailed"
max_reference_depth = 5
critic_enabled = true
critic_threshold = 0.8
critic_max_iterations = 3
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            f.flush()
            config = MattermostSummarizerConfig.from_config(f.name)

        assert config.summarizer_default_level == SummaryLevel.DETAILED
        assert config.max_reference_depth == 5
        assert config.critic_enabled is True
        assert config.critic_threshold == 0.8
        assert config.critic_max_iterations == 3
