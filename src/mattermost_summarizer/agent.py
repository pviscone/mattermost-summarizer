"""Agent factory for mattermost-summarizer."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import litellm
from openhands.sdk import LLM, Agent, AgentContext, Tool
from pydantic import SecretStr

if TYPE_CHECKING:
    from openhands.sdk.critic import CriticBase

    from mattermost_summarizer.client import MattermostClient
    from mattermost_summarizer.levels import SummaryLevel

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
  finish(
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


ORCHESTRATOR_PROMPT = """You are the orchestrator for a Mattermost conversation summarization system.

Your job is to coordinate specialized sub-agents to gather context and produce a summary.

 Coordination Flow:
  1. Parse the permalink URL from the user message
  2. Delegate to the thread_fetcher sub-agent to fetch the root thread
  3. Receive the fetched thread content and scan it for references:
     - Mattermost permalinks (thread URLs)
     - Launchpad bug URLs (bugs.launchpad.net/...)
     - GitHub issue/PR URLs (github.com/...)
     - File attachment references
  4. Decide which references are relevant to follow based on the thread context
  5. Delegate to appropriate sub-agents for relevant references:
     - thread_fetcher: for Mattermost thread permalinks
     - bug_researcher: for Launchpad bug URLs
     - github_researcher: for GitHub issue/PR URLs
     - file_fetcher: for Mattermost file attachments
  6. Repeat steps 3-5 up to the maximum reference depth (default: 3)
  7. Synthesize all gathered context into a coherent summary
  8. Call the finish tool with the structured summary

 Important constraints:
 - Do NOT fetch data directly - always delegate to the appropriate sub-agent
 - Track which URLs you have already followed to avoid cycles
 - Only follow references that are relevant to understanding the thread
 - When in doubt, prefer following fewer references rather than more
 - Always delegate the root thread to thread_fetcher first
 - Do NOT follow the same URL twice - keep track of followed URLs

 Reference types and their sub-agents:
 - Mattermost thread URLs (chat.example.com/team/pl/...) → thread_fetcher
 - Launchpad bugs (bugs.launchpad.net/...) → bug_researcher
 - GitHub issues/PRs (github.com/.../issues/..., github.com/.../pull/...) → github_researcher
 - Mattermost file attachments → file_fetcher

 URL Classification Examples:
 - "https://bugs.launchpad.net/ubuntu/+bug/12345" → bug_researcher
 - "https://github.com/canonical/mattermost/issues/789" → github_researcher
 - "https://github.com/canonical/mattermost/pull/456" → github_researcher
 - "https://chat.example.com/team/pl/abc123" → thread_fetcher

 To delegate, you MUST use TWO steps:

  Step 1 - SPAWN: Create sub-agents with specific IDs
    delegate(
      command="spawn",
      ids=["my_agent_id"],
      agent_types=["thread_fetcher"]
    )

  Step 2 - DELEGATE: Send tasks to already-spawned agents
    delegate(
      command="delegate",
      tasks={"my_agent_id": "Your task description here"}
    )

  Example - Complete workflow to fetch a thread:
    1. delegate(command="spawn", ids=["fetcher_1"], agent_types=["thread_fetcher"])
    2. delegate(command="delegate", tasks={"fetcher_1": "Fetch Mattermost thread from permalink: https://chat.example.com/team/pl/abc123"})

  Reference Tracking Tool (track_references):
  Use the track_references tool to programmatically track URLs and avoid cycles.

  Commands:
    track_references(command="classify_text", url="<thread content text>")
      - Extracts and classifies all URLs found in the text
      - Returns list of URLs with their types (mattermost_thread, launchpad_bug, github_issue, etc.)
      - Automatically skips URLs already marked as followed

    track_references(command="mark_followed", url="<url>")
      - Marks a URL as followed to prevent duplicate processing

    track_references(command="is_followed", url="<url>")
      - Checks if a URL has already been followed

    track_references(command="can_follow")
      - Returns whether we can follow another level of references
      - Reports current_depth/max_depth

    track_references(command="increment_depth")
      - Increments depth counter after following a reference

    track_references(command="reset")
      - Resets tracker for a new summary operation

  Example workflow with tracking:
    1. After delegating to thread_fetcher, get the response content
    2. track_references(command="classify_text", url="<thread content>")
    3. For each URL in the response, decide if relevant to follow
    4. Before following: track_references(command="is_followed", url="<url>")
    5. If not followed and can_follow:
       - track_references(command="mark_followed", url="<url>")
       - track_references(command="increment_depth")
       - delegate to appropriate sub-agent
    6. After all references processed, call finish"""


def supports_json_mode(model: str) -> bool:
    """Check if model supports structured output via response_format.

    Uses litellm's get_supported_openai_params to detect if the model
    supports the response_format parameter.
    """
    try:
        params_or_none = litellm.get_supported_openai_params(model)  # type: ignore
        params: list[str] = params_or_none if params_or_none else []  # type: ignore
        return "response_format" in params
    except Exception:
        return False


def build_user_message(
    permalink_url: str,
    post_id: str,
    level: SummaryLevel,
    addendum: str,
) -> str:
    """Build the user message with level-specific addendum.

    Args:
        permalink_url: The Mattermost permalink URL
        post_id: The post ID extracted from the URL
        level: The summarization level
        addendum: Level-specific prompt addendum

    Returns:
        Complete user message with base prompt and level addendum
    """
    return (
        f"Summarize this Mattermost thread: {permalink_url}\nThe post ID is: {post_id}\n\n{SYSTEM_PROMPT}\n\n{addendum}"
    )


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
    level: SummaryLevel,
) -> Agent:
    """Build a Mattermost summarizer agent with all tools including GitHub.

    Args:
        llm_model: LLM model name (LiteLLM format: provider/model-name)
        llm_api_key: API key for the LLM
        llm_base_url: Base URL for the LLM API (None = provider default)
        client: MattermostClient instance
        github_token: Optional GitHub token for FetchGitHubIssue tool
        level: Summarization level

    Returns:
        Configured Agent instance ready for Conversation
    """
    from mattermost_summarizer.levels import BRIEF_ADDENDUM, DETAILED_ADDENDUM, NORMAL_ADDENDUM, SummaryLevel
    from mattermost_summarizer.tools import build_summarizer_tools

    if level == SummaryLevel.BRIEF:
        addendum = BRIEF_ADDENDUM
    elif level == SummaryLevel.DETAILED:
        addendum = DETAILED_ADDENDUM
    else:
        addendum = NORMAL_ADDENDUM

    tools = build_summarizer_tools(client, github_token, level)
    agent = build_summarizer_agent(
        llm_model=llm_model,
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        tools=tools,
    )
    agent._user_message_addendum = addendum  # type: ignore[attr-defined]
    return agent


def build_orchestrator_agent(
    llm_model: str,
    llm_api_key: str,
    llm_base_url: str | None,
    level: SummaryLevel,
    max_reference_depth: int = 3,
    critic: CriticBase | None = None,
) -> Agent:
    """Build an orchestrator agent that delegates to sub-agents.

    Args:
        llm_model: LLM model name (LiteLLM format: provider/model-name)
        llm_api_key: API key for the LLM
        llm_base_url: Base URL for the LLM API (None = provider default)
        level: Summarization level (determines which finish tool to use)
        max_reference_depth: Maximum recursion depth for following references
        critic: Optional critic for iterative refinement

    Returns:
        Configured Agent instance with DelegateTool and finish tool
    """
    import openhands.sdk as oh_sdk

    from mattermost_summarizer.levels import (
        BriefFinishTool,
        DetailedFinishTool,
        NormalFinishTool,
        SummaryLevel,
    )
    from mattermost_summarizer.levels.base import SummarizerFinishToolBase
    from mattermost_summarizer.subagents.delegate_tool import DelegateTool
    from mattermost_summarizer.subagents.reference_tracking_tool import ReferenceTrackingTool

    extra_body: dict[str, object] | None = None
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

    delegate_tool_def = DelegateTool.create()[0]
    oh_sdk.register_tool("delegate", delegate_tool_def)  # type: ignore[arg-type]

    if level == SummaryLevel.BRIEF:
        finish_tool_def: SummarizerFinishToolBase = BriefFinishTool.create()[0]
    elif level == SummaryLevel.DETAILED:
        finish_tool_def = DetailedFinishTool.create()[0]
    else:
        finish_tool_def = NormalFinishTool.create()[0]

    oh_sdk.register_tool("finish", finish_tool_def)  # type: ignore[arg-type]

    from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

    tracker = ReferenceTracker(max_depth=max_reference_depth)
    track_references_tool_def = ReferenceTrackingTool.create(tracker)[0]
    oh_sdk.register_tool("track_references", track_references_tool_def)  # type: ignore[arg-type]

    tools: list[Tool] = [
        Tool(name="delegate", params={}),
        Tool(name="finish", params={}),
        Tool(name="track_references", params={}),
    ]

    agent_kwargs: dict[str, object] = {
        "llm": llm,
        "tools": tools,
        "agent_context": AgentContext(system_message_suffix=ORCHESTRATOR_PROMPT),
        "include_default_tools": [],
    }
    if critic is not None:
        agent_kwargs["critic"] = critic

    agent = Agent(**agent_kwargs)  # type: ignore[arg-type]

    return agent


__all__ = [
    "build_summarizer_agent",
    "build_summarizer_agent_with_github",
    "build_orchestrator_agent",
    "SYSTEM_PROMPT",
    "ORCHESTRATOR_PROMPT",
    "supports_json_mode",
    "build_user_message",
]
