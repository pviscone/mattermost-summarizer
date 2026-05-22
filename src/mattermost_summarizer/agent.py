"""Agent factory for mattermost-summarizer."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import litellm
from openhands.sdk import LLM, Agent, Tool
from pydantic import SecretStr

if TYPE_CHECKING:
    from mattermost_summarizer.client import MattermostClient

SYSTEM_PROMPT = """You are a Mattermost conversation summarizer. Your job is to read
conversation threads and produce structured summaries.

When given a Mattermost permalink:
1. Fetch the thread to get all posts
2. Fetch channel context if the thread is unclear without it
3. When you encounter Mattermost permalink URLs in posts, you MAY call FetchThread to get more context
4. When you encounter Launchpad bug URLs (bugs.launchpad.net), you MAY call FetchLaunchpadBug to get bug details
5. When you encounter GitHub issue or PR URLs, you MAY call FetchGitHubIssue to get issue/PR details
6. Produce a summary with:
   - TL;DR: 3-5 bullet points capturing the key outcomes (as a newline-separated string, NOT a list)
   - Key Findings: Important insights (as a list of strings)
   - Narrative: Chronological walkthrough (as a single string)
   - Action items: Decisions and follow-ups (as a list of strings)
   - Participants: List of contributors (as a list of strings)
7. Call the finish tool with your summary

Example finish call:
  summarizer_finish(
    tldr="- First key point\\n- Second key point\\n- Third key point",
    key_findings=["Finding one", "Finding two"],
    narrative="The discussion started when...",
    action_items=["@user to do X"],
    participants=["alice", "bob"]
  )

IMPORTANT: tldr MUST be a single string with bullet points separated by newlines (\\n), NOT a list/array.

IMPORTANT: After calling the finish tool, do NOT output any additional text.
The finish tool call IS your final output. Do not write markdown, summaries,
or any other text after calling it.

Be concise but thorough. Focus on substance, not procedural messages
("thanks!", "agreed", etc.).

IMPORTANT: Always fetch the thread first using the FetchThread tool before
attempting to summarize. The thread data will include user information. Only call
GetUser if you need additional details about a specific user."""


def supports_json_mode(model: str) -> bool:
    """Check if model supports structured output via response_format.

    Uses litellm's get_supported_openai_params to detect if the model
    supports the response_format parameter.
    """
    try:
        params = litellm.get_supported_openai_params(model) or []
        return "response_format" in params
    except Exception:
        return False


def build_summarizer_agent(
    llm_model: str,
    llm_api_key: str,
    llm_base_url: str | None,
    tools: Sequence[Tool],
    enable_json_mode: bool | None = None,
) -> Agent:
    """Build a Mattermost summarizer agent.

    Args:
        llm_model: LLM model name (LiteLLM format: provider/model-name)
        llm_api_key: API key for the LLM
        llm_base_url: Base URL for the LLM API (None = provider default)
        tools: List of Tool spec instances for Mattermost operations
        enable_json_mode: Force enable/disable JSON mode. If None, auto-detect
            based on provider support (OpenAI, Azure, Anthropic, Gemini, etc.)

    Returns:
        Configured Agent instance ready for Conversation
    """
    extra_body: dict[str, object] | None = None
    if enable_json_mode is None:
        enable_json_mode = supports_json_mode(llm_model)
        enable_json_mode = False
    if enable_json_mode:
        extra_body = {"response_format": {"type": "json_object"}}

    llm_kwargs: dict[str, object] = {
        "model": llm_model,
        "api_key": SecretStr(llm_api_key),
    }
    if llm_base_url:
        llm_kwargs["base_url"] = llm_base_url
    if extra_body:
        llm_kwargs["litellm_extra_body"] = extra_body

    if llm_model.startswith("github_copilot/"):
        llm_kwargs["extra_headers"] = {
            "editor-version": "vscode/1.85.1",
            "Copilot-Integration-Id": "vscode-chat",
        }

    llm = LLM(**llm_kwargs)  # type: ignore[arg-type]

    agent = Agent(llm=llm, tools=list(tools), include_default_tools=[])

    return agent


def build_summarizer_agent_with_github(
    llm_model: str,
    llm_api_key: str,
    llm_base_url: str | None,
    client: MattermostClient,
    github_token: SecretStr | None,
) -> Agent:
    """Build a Mattermost summarizer agent with all tools including GitHub.

    Args:
        llm_model: LLM model name (LiteLLM format: provider/model-name)
        llm_api_key: API key for the LLM
        llm_base_url: Base URL for the LLM API (None = provider default)
        client: MattermostClient instance
        github_token: Optional GitHub token for FetchGitHubIssue tool

    Returns:
        Configured Agent instance ready for Conversation
    """
    from mattermost_summarizer.tools import build_summarizer_tools

    tools = build_summarizer_tools(client, github_token)
    return build_summarizer_agent(
        llm_model=llm_model,
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        tools=tools,
    )


__all__ = ["build_summarizer_agent", "build_summarizer_agent_with_github", "SYSTEM_PROMPT", "supports_json_mode"]
