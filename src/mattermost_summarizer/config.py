"""Configuration for mattermost-summarizer using pydantic-settings."""

from pathlib import Path
from typing import Any

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

from mattermost_summarizer.levels import SummaryLevel


class MattermostSummarizerConfig(BaseSettings):
    """Configuration for Mattermost Summarizer.

    Supports TOML as primary config source with MM_ env var override.
    Order of precedence: env var > TOML > defaults.

    Example TOML (mattermost-summarizer.toml):
        [mattermost]
        url = "https://chat.canonical.com"
        token = "your-mattermost-token"

        [llm]
        model = "openai/gpt-4o"
        api_key = "your-llm-api-key"
        base_url = "https://api.openai.com/v1"  # optional

        [github]
        token = "ghp_..."  # optional; raises GitHub API rate limit

        [summarizer]
        default_level = "normal"  # brief, normal, or detailed

    Example env vars:
        MM_MATTERMOST_URL=https://chat.canonical.com
        MM_MATTERMOST_TOKEN=your-token
        MM_LLM_MODEL=openai/gpt-4o
        MM_LLM_API_KEY=your-key
        MM_LLM_BASE_URL=https://api.openai.com/v1
        MM_GITHUB_TOKEN=ghp_...  # optional
        MM_SUMMARIZER_DEFAULT_LEVEL=detailed
    """

    model_config = SettingsConfigDict(
        env_prefix="MM_",
        env_nested_delimiter="_",
        extra="ignore",
    )

    mattermost_url: HttpUrl = Field(description="Mattermost server URL (e.g., https://chat.canonical.com)")
    mattermost_token: SecretStr = Field(description="Mattermost personal access token")
    llm_api_key: SecretStr = Field(description="LLM API key")
    llm_model: str = Field(
        default="openai/gpt-4o",
        description="LLM model (LiteLLM format: provider/model-name)",
    )
    llm_base_url: str | None = Field(
        default=None,
        description="LLM API base URL (None = provider default)",
    )
    github_token: SecretStr | None = Field(
        default=None,
        description="GitHub personal access token (optional; raises rate limit for FetchGitHubIssue)",
    )
    summarizer_default_level: SummaryLevel = Field(
        default=SummaryLevel.NORMAL,
        description="Default summarization level (brief, normal, or detailed)",
    )
    max_reference_depth: int = Field(
        default=3,
        description="Maximum recursion depth for following referenced URLs (0=disabled, default: 3)",
    )
    critic_enabled: bool = Field(
        default=True,
        description="Enable LLM critic for iterative refinement (default: true)",
    )
    critic_threshold: float = Field(
        default=0.7,
        description="Quality threshold (0-1) for accepting summaries (default: 0.7)",
    )
    critic_max_iterations: int = Field(
        default=2,
        description="Maximum critic revision rounds before giving up (default: 2)",
    )
    max_sub_agents: int = Field(
        default=500,
        description="Maximum number of sub-agents that can be spawned during reference following (default: 500)",
    )

    @classmethod
    def from_config(cls, path: Path | str) -> "MattermostSummarizerConfig":
        """Load config from a TOML file.

        Args:
            path: Path to TOML config file

        Returns:
            Config instance with values from TOML (may be overridden by env vars)

        Raises:
            ConfigError: If TOML file cannot be read
        """
        toml_path = Path(path)
        if not toml_path.exists():
            raise FileNotFoundError(f"Config file not found: {toml_path}")

        try:
            import tomli  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports, reportUnusedImport]
        except ImportError:
            import tomllib as tomli  # Python 3.11+

        with open(toml_path, "rb") as f:
            toml_data = tomli.load(f)  # pyright: ignore[reportUnknownVariableType, reportMemberType]  # type: ignore[assignment]

        data: dict[str, Any] = {}

        if "mattermost" in toml_data:
            mm: dict[str, Any] = dict(toml_data["mattermost"])  # pyright: ignore[reportArgumentType]  # type: ignore[misc]
            if "url" in mm:
                data["mattermost_url"] = mm["url"]
            if "token" in mm:
                data["mattermost_token"] = mm["token"]

        if "llm" in toml_data:
            llm: dict[str, Any] = dict(toml_data["llm"])  # pyright: ignore[reportArgumentType]  # type: ignore[misc]
            if "model" in llm:
                data["llm_model"] = llm["model"]
            if "api_key" in llm:
                data["llm_api_key"] = llm["api_key"]
            if "base_url" in llm:
                data["llm_base_url"] = llm["base_url"]

        if "github" in toml_data:
            github: dict[str, Any] = dict(toml_data["github"])  # pyright: ignore[reportArgumentType]  # type: ignore[misc]
            if "token" in github:
                data["github_token"] = github["token"]

        if "summarizer" in toml_data:
            summarizer: dict[str, Any] = dict(toml_data["summarizer"])  # pyright: ignore[reportArgumentType]  # type: ignore[misc]
            if "default_level" in summarizer:
                level_str = summarizer["default_level"]
                if isinstance(level_str, str):
                    data["summarizer_default_level"] = SummaryLevel(level_str.lower())
            if "max_reference_depth" in summarizer:
                data["max_reference_depth"] = int(summarizer["max_reference_depth"])
            if "critic_enabled" in summarizer:
                data["critic_enabled"] = bool(summarizer["critic_enabled"])
            if "critic_threshold" in summarizer:
                data["critic_threshold"] = float(summarizer["critic_threshold"])
            if "critic_max_iterations" in summarizer:
                data["critic_max_iterations"] = int(summarizer["critic_max_iterations"])
            if "max_sub_agents" in summarizer:
                data["max_sub_agents"] = int(summarizer["max_sub_agents"])

        return cls(**data)

    @classmethod
    def from_env(cls) -> "MattermostSummarizerConfig":
        """Load config from environment variables only.

        Returns:
            Config instance from MM_* env vars
        """
        return cls.model_validate({})
