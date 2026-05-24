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
    from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

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

Your job is to coordinate gathering context and producing a summary.

Coordination Flow:
  1. Parse the permalink URL from the user message
  2. Call fetch_reference(url=<permalink>) to fetch the root thread
  3. Read the result. At the end of the result you will find a section like:

       ---
       References found in result:
       Found the following references in the content:

       1. https://github.com/org/repo/issues/123  (GitHub issue/PR) — This PR fixes the memory leak described in the bug report.
       2. https://bugs.launchpad.net/...  (Launchpad bug) — LP bug tracking the upstream crash in open-iscsi.
       3. https://chat.example.com/team/pl/abc123  (Mattermost thread) — Thread discussing the deployment rollback decision.

       Depth: 1/3
       You may call fetch_reference on the above URLs to fetch additional context.

  4. For each reference you judge as relevant, call fetch_reference(url=<url>).
     Relevance criteria: prefer PRs/issues/bugs that are directly mentioned as
     fixes, blockers, or root causes. Skip documentation links and tangential URLs.
     Use the one-sentence description next to each URL to inform your relevance decision.
  5. Repeat step 3-4 with each result until no more references appear or depth limit is reached.
  6. Synthesize all gathered context into a coherent summary.
  7. Call the finish tool with the structured summary.

Important constraints:
  - You MUST follow up on references listed in the "References found in result" section —
    do not skip them unless you have explicitly reasoned that they are irrelevant.
  - The fetch_reference tool handles cycle detection, URL classification, and depth limiting
    transparently. If it returns an error (e.g. "Already followed", "Maximum depth reached",
    "Unsupported URL type") simply skip that URL and continue.
  - When the "References found" section says "Maximum reference depth reached",
    stop following references and proceed to synthesize.
  - If the result contains no "References found" section, there are no followable
    URLs — proceed directly to synthesize and call finish.
  - Depth is tracked per-URL: sibling references found in the same thread all share
    the same depth level, so multiple siblings at depth 1 do NOT exhaust the depth budget."""


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
    max_sub_agents: int = 20,
    critic: CriticBase | None = None,
    tracker: ReferenceTracker | None = None,
) -> Agent:
    """Build an orchestrator agent that delegates to sub-agents.

    Args:
        llm_model: LLM model name (LiteLLM format: provider/model-name)
        llm_api_key: API key for the LLM
        llm_base_url: Base URL for the LLM API (None = provider default)
        level: Summarization level (determines which finish tool to use)
        max_reference_depth: Maximum recursion depth for following references
        max_sub_agents: Maximum number of sub-agents that can be spawned (default: 20)
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

    from mattermost_summarizer.subagents.fetch_reference_tool import FetchReferenceTool

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

    if level == SummaryLevel.BRIEF:
        finish_tool_def: SummarizerFinishToolBase = BriefFinishTool.create()[0]
    elif level == SummaryLevel.DETAILED:
        finish_tool_def = DetailedFinishTool.create()[0]
    else:
        finish_tool_def = NormalFinishTool.create()[0]

    oh_sdk.register_tool("finish", finish_tool_def)  # type: ignore[arg-type]

    from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

    if tracker is None:
        tracker = ReferenceTracker(max_depth=max_reference_depth)
    fetch_ref_tool_def = FetchReferenceTool.create(tracker, max_children=max_sub_agents)[0]
    oh_sdk.register_tool("fetch_reference", fetch_ref_tool_def)  # type: ignore[arg-type]

    tools: list[Tool] = [
        Tool(name="fetch_reference", params={}),
        Tool(name="finish", params={}),
    ]

    agent_kwargs: dict[str, object] = {
        "llm": llm,
        "tools": tools,
        "agent_context": AgentContext(system_message_suffix=ORCHESTRATOR_PROMPT),
        "include_default_tools": [],
        "tool_concurrency_limit": 4,
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
