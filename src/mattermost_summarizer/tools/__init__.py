"""Tools package for mattermost-summarizer.

Tool Distribution Architecture (Multi-Agent):

  Orchestrator Agent:
    - delegate: DelegateTool for spawning sub-agents
    - finish: Level-specific finish tool

  Sub-Agent: thread_fetcher
    - fetch_thread: Fetch Mattermost thread
    - get_user: Get user details
    - fetch_channel: Get channel context

  Sub-Agent: bug_researcher
    - fetch_launchpad_bug: Fetch Launchpad bug details

  Sub-Agent: github_researcher
    - fetch_github_issue: Fetch GitHub issue/PR details

  Sub-Agent: file_fetcher
    - fetch_file: Fetch file attachment content

Note: Tools are no longer given to a single agent. Each sub-agent receives
only the tools relevant to its specialty.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from openhands.sdk import Tool
from pydantic import SecretStr

from mattermost_summarizer.levels import (
    BriefFinishTool,
    DetailedFinishTool,
    NormalFinishTool,
    SummaryLevel,
)
from mattermost_summarizer.tools.fetch_channel import get_fetch_channel_tool
from mattermost_summarizer.tools.fetch_file import get_fetch_file_tool
from mattermost_summarizer.tools.fetch_thread import get_fetch_thread_tool
from mattermost_summarizer.tools.get_user import get_get_user_tool

if TYPE_CHECKING:
    from mattermost_summarizer.client import MattermostClient

_RegisterToolFn = Callable[[str, Any], None]


def _get_finish_tool_for_level(level: SummaryLevel) -> Tool:
    """Get the finish tool for the specified level."""
    from mattermost_summarizer.levels.base import SummarizerFinishToolBase

    tool_def: SummarizerFinishToolBase
    if level == SummaryLevel.BRIEF:
        tool_def = BriefFinishTool.create()[0]
    elif level == SummaryLevel.DETAILED:
        tool_def = DetailedFinishTool.create()[0]
    else:
        tool_def = NormalFinishTool.create()[0]
    import openhands.sdk as oh_sdk

    register_tool_fn: _RegisterToolFn = oh_sdk.register_tool  # type: ignore[assignment]
    register_tool_fn("finish", tool_def)
    return Tool(name="finish", params={})


def build_mattermost_tools(
    client: MattermostClient,
    level: SummaryLevel = SummaryLevel.NORMAL,
) -> Sequence[Tool]:
    """Build Mattermost-specific tools for the agent.

    Args:
        client: MattermostClient instance to use for API calls
        level: Summarization level (default: NORMAL)

    Returns:
        Sequence of Tool spec instances (registered with the SDK)
    """
    tools: list[Tool] = [
        get_fetch_thread_tool(client),
        get_get_user_tool(client),
        get_fetch_channel_tool(client),
        get_fetch_file_tool(client),
        _get_finish_tool_for_level(level),
    ]
    return tools


def build_summarizer_tools(
    client: MattermostClient,
    github_token: SecretStr | None = None,
    level: SummaryLevel = SummaryLevel.NORMAL,
) -> Sequence[Tool]:
    """Build all summarizer tools for the agent.

    Args:
        client: MattermostClient instance to use for API calls
        github_token: Optional GitHub token for FetchGitHubIssue tool
        level: Summarization level (default: NORMAL)

    Returns:
        Sequence of Tool spec instances (registered with the SDK)
    """
    from mattermost_summarizer.tools.fetch_github_issue import get_fetch_github_issue_tool
    from mattermost_summarizer.tools.fetch_launchpad_bug import get_fetch_launchpad_bug_tool

    tools: list[Tool] = [
        get_fetch_thread_tool(client),
        get_get_user_tool(client),
        get_fetch_channel_tool(client),
        get_fetch_file_tool(client),
        get_fetch_launchpad_bug_tool(),
        get_fetch_github_issue_tool(github_token),
        _get_finish_tool_for_level(level),
    ]
    return tools


__all__ = [
    "build_mattermost_tools",
    "build_summarizer_tools",
    "get_fetch_file_tool",
    "get_fetch_thread_tool",
    "get_get_user_tool",
    "get_fetch_channel_tool",
]
