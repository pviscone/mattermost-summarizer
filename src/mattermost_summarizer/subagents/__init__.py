"""Sub-agent factory functions for mattermost-summarizer multi-agent architecture."""

from __future__ import annotations

from typing import TYPE_CHECKING

from openhands.sdk import LLM, Agent, AgentContext, Tool

if TYPE_CHECKING:
    from mattermost_summarizer.client import MattermostClient

from mattermost_summarizer.subagents.delegate_tool import register_delegate_tool

THREAD_FETCHER_PROMPT = """You are a thread researcher for Mattermost conversations.

Your job:
1. Fetch the specified Mattermost thread using the FetchThread tool
2. FetchThread already resolves user IDs to display names — do NOT call GetUser
   unless you need additional profile details for a specific user.
   If you do call GetUser, you MUST pass the opaque user_id field (e.g. "abc123xyz")
   from the thread data — never pass a display name, @username handle, or
   human-readable name as the user_id.
3. Call FetchChannel only if you need channel purpose/header context beyond what
   FetchThread provides. If calling FetchChannel, use the channel_id field returned
   by FetchThread — do NOT guess a channel name or team name.
4. Scan the thread content for any URLs or references (Mattermost
   permalinks, Launchpad bugs, GitHub issues/PRs, file attachments)
5. Call the finish tool with a text summary that includes:
   - Thread overview (title, channel, participants)
   - Key points from the conversation
   - All URLs/references found in the thread

Be thorough in fetching user names - replace user IDs with actual display names in your summary."""


BUG_RESEARCHER_PROMPT = """You are a bug researcher specializing in Launchpad bugs.

Your job:
1. Fetch the specified Launchpad bug using the FetchLaunchpadBug tool
2. Summarize the bug details including:
   - Title and status
   - Importance/priority
   - Description and comments
   - Any relevant context from the bug
3. Call the finish tool with a formatted text summary of the bug findings."""


GITHUB_RESEARCHER_PROMPT = """You are a GitHub researcher specializing in issues and pull requests.

Your job:
1. Fetch the specified GitHub issue or PR using the FetchGitHubIssue tool
2. Summarize the details including:
   - Title, state, and labels
   - Body/description
   - Assignees
   - Comments and review feedback (for PRs)
   - Merge status (for PRs)
3. Call the finish tool with a formatted text summary of the issue/PR findings."""


FILE_FETCHER_PROMPT = """You are a file researcher for Mattermost file attachments.

Your job:
1. Fetch the specified file using the FetchFile tool
2. If the file is readable text, include its content in your summary
3. If the file is binary or not readable, indicate that clearly
4. Call the finish tool with a summary of the file contents or a "not readable" message."""


def create_thread_fetcher(llm: LLM, client: MattermostClient | None = None) -> Agent:
    """Create a thread_fetcher sub-agent.

    This agent fetches Mattermost threads and extracts key information
    including any URLs or references found in the thread content.

    Args:
        llm: LLM instance to use for the agent
        client: MattermostClient instance for API calls

    Returns:
        Configured Agent for fetching threads
    """
    from mattermost_summarizer.tools.fetch_channel import get_fetch_channel_tool
    from mattermost_summarizer.tools.fetch_thread import get_fetch_thread_tool
    from mattermost_summarizer.tools.get_user import get_get_user_tool

    tools: list[Tool] = [
        get_fetch_thread_tool(client) if client else _get_stub_tool("fetch_thread"),
        get_get_user_tool(client) if client else _get_stub_tool("get_user"),
        get_fetch_channel_tool(client) if client else _get_stub_tool("fetch_channel"),
    ]

    agent = Agent(
        llm=llm,
        tools=tools,
        agent_context=AgentContext(system_message_suffix=THREAD_FETCHER_PROMPT),
        include_default_tools=[],
    )

    return agent


def create_bug_researcher(llm: LLM, client: MattermostClient | None = None) -> Agent:
    """Create a bug_researcher sub-agent.

    This agent fetches Launchpad bug details and summarizes findings.
    The `client` parameter is kept for API compatibility with other factory functions
    but is not used by this agent (bug fetching does not require Mattermost API).

    Args:
        llm: LLM instance to use for the agent
        client: Not used but kept for API compatibility

    Returns:
        Configured Agent for fetching Launchpad bugs
    """
    from mattermost_summarizer.tools.fetch_launchpad_bug import get_fetch_launchpad_bug_tool

    tools: list[Tool] = [
        get_fetch_launchpad_bug_tool(),
    ]

    agent = Agent(
        llm=llm,
        tools=tools,
        agent_context=AgentContext(system_message_suffix=BUG_RESEARCHER_PROMPT),
        include_default_tools=[],
    )

    return agent


def create_github_researcher(llm: LLM, client: MattermostClient | None = None) -> Agent:
    """Create a github_researcher sub-agent.

    This agent fetches GitHub issue or PR details and summarizes findings.

    Args:
        llm: LLM instance to use for the agent
        client: Not used but kept for API compatibility

    Returns:
        Configured Agent for fetching GitHub issues/PRs
    """
    from mattermost_summarizer.tools.fetch_github_issue import get_fetch_github_issue_tool

    tools: list[Tool] = [
        get_fetch_github_issue_tool(),
    ]

    agent = Agent(
        llm=llm,
        tools=tools,
        agent_context=AgentContext(system_message_suffix=GITHUB_RESEARCHER_PROMPT),
        include_default_tools=[],
    )

    return agent


def create_file_fetcher(llm: LLM, client: MattermostClient | None = None) -> Agent:
    """Create a file_fetcher sub-agent.

    This agent fetches Mattermost file attachment content.

    Args:
        llm: LLM instance to use for the agent
        client: MattermostClient instance for API calls

    Returns:
        Configured Agent for fetching file attachments
    """
    from mattermost_summarizer.tools.fetch_file import get_fetch_file_tool

    tools: list[Tool] = [
        get_fetch_file_tool(client) if client else _get_stub_tool("fetch_file"),
    ]

    agent = Agent(
        llm=llm,
        tools=tools,
        agent_context=AgentContext(system_message_suffix=FILE_FETCHER_PROMPT),
        include_default_tools=[],
    )

    return agent


def _get_stub_tool(name: str) -> Tool:
    """Get a stub tool for testing without a client."""
    return Tool(name=name, params={})


def register_subagents(client: MattermostClient | None = None) -> None:
    """Register all sub-agent types with the OpenHands agent registry.

    Also registers the delegate tool.

    Args:
        client: Optional MattermostClient for creating actual tool instances
    """
    from openhands.sdk import register_agent

    register_delegate_tool()

    register_agent(
        "thread_fetcher",
        lambda llm: create_thread_fetcher(llm, client),
        "Fetches Mattermost threads and extracts key information "
        "including any URLs or references found in the thread content.",
    )

    register_agent(
        "bug_researcher",
        lambda llm: create_bug_researcher(llm, client),
        "Fetches Launchpad bug details and summarizes the findings.",
    )

    register_agent(
        "github_researcher",
        lambda llm: create_github_researcher(llm, client),
        "Fetches GitHub issue or PR details and summarizes the findings.",
    )

    register_agent(
        "file_fetcher",
        lambda llm: create_file_fetcher(llm, client),
        "Fetches Mattermost file attachment content and reports its contents.",
    )


__all__ = [
    "create_thread_fetcher",
    "create_bug_researcher",
    "create_github_researcher",
    "create_file_fetcher",
    "register_subagents",
]
